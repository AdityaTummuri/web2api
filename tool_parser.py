"""
tool_parser.py - Lightweight, Robust Tool Calling Engine & Parser for Web2API.

Converts consumer LLM chat text responses (from Gemini, ChatGPT, Claude web sessions)
into standard OpenAI-compatible tool_calls. Injects coherent tool schemas, validates
arguments against declared parameters, and handles edge cases (markdown fences, XML tags,
fuzzy JSON, multiple parallel tool calls).
"""

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union


# Standard regex for fenced blocks (```tool_call, ```json, etc.)
FENCE_BLOCK_REGEX = re.compile(
    r"```(?:tool_call|tool-call|function_call|json)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)

# Tag style regex: <tool_call>{...}</tool_call>
TAG_TOOL_CALL_REGEX = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)


def repair_json_string(raw: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """
    Lightweight, resilient JSON parser that cleans up common LLM syntax quirks
    (trailing commas, single quotes, leading/trailing non-JSON artifacts).
    """
    cleaned = raw.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extract outermost JSON object or array if surrounded by stray text
    obj_match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if obj_match:
        cleaned = obj_match.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Clean trailing commas before closing braces/brackets
    cleaned_commas = re.sub(r",\s*(\}|\])", r"\1", cleaned)
    try:
        return json.loads(cleaned_commas)
    except json.JSONDecodeError:
        pass

    # Convert single-quoted keys or values to double-quoted if safe
    # e.g., {'name': 'foo'} -> {"name": "foo"}
    try:
        single_quoted_fixed = re.sub(r"(?<!\\)'", '"', cleaned_commas)
        return json.loads(single_quoted_fixed)
    except Exception:
        pass

    return None


def format_tools_prompt(tools: List[Dict[str, Any]], tool_choice: Any = "auto") -> str:
    """
    Generates a coherent, unambiguous tool instruction prompt for the model.
    Instructs the model on tool signatures and the exact output contract.
    """
    if not tools:
        return ""

    lines = [
        "## AVAILABLE TOOLS",
        "You have access to the following functions to perform tasks. When you need to call a tool,",
        "you MUST output a tool call block using the exact contract below. Do not guess parameters.",
        "",
    ]

    for tool in tools:
        fn = tool.get("function", {})
        name = fn.get("name", "unknown")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})

        lines.append(f"### Function: `{name}`")
        if desc:
            lines.append(f"Description: {desc}")
        lines.append(f"Parameters Schema: {json.dumps(params, indent=2)}")
        lines.append("")

    lines.extend([
        "## TOOL CALL OUTPUT CONTRACT",
        "If you decide to invoke a tool, reply ONLY with one or more fenced `tool_call` blocks and NO extraneous commentary:",
        "```tool_call",
        '{"name": "<function_name>", "arguments": {"<param_key>": "<param_value>"}}',
        "```",
        "If multiple tools are required, output multiple `tool_call` blocks in sequence.",
        "If NO tool is needed, respond with standard conversational text and DO NOT output any ```tool_call``` block.",
    ])

    if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
        target_name = tool_choice.get("function", {}).get("name")
        if target_name:
            lines.append(f"CRITICAL CONSTRAINT: You MUST call the function `{target_name}` for this turn.")
    elif tool_choice == "required":
        lines.append("CRITICAL CONSTRAINT: You MUST call at least one of the available tools for this turn.")
    elif tool_choice == "none":
        lines.append("CRITICAL CONSTRAINT: You must NOT call any tools. Provide a direct conversational answer.")

    return "\n".join(lines)


def format_conversation_with_tools(
    messages: List[Any],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Any = "auto",
) -> str:
    """
    Formats the conversation turn by turn, preserving tool results and injecting
    tool specifications coherently.
    """
    formatted_parts = []

    # 1. Inject tools schema at the top if tools are declared
    if tools and tool_choice != "none":
        tool_instructions = format_tools_prompt(tools, tool_choice)
        formatted_parts.append(f"[System Instructions - Tool Calling Contract]:\n{tool_instructions}")

    # 2. Format message history
    for msg in messages:
        # Support dict or Pydantic MessageItem
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
            tool_call_id = msg.get("tool_call_id")
            name = msg.get("name")
        else:
            role = getattr(msg, "role", "user")
            content = getattr(msg, "content", "") or ""
            tool_calls = getattr(msg, "tool_calls", None)
            tool_call_id = getattr(msg, "tool_call_id", None)
            name = getattr(msg, "name", None)

        role_cap = role.capitalize()

        if role == "tool":
            # Tool result message
            header = f"[Tool Result"
            if name:
                header += f" for `{name}`"
            if tool_call_id:
                header += f" (id: {tool_call_id})"
            header += "]:"
            formatted_parts.append(f"{header}\n{content}")
        elif role == "assistant" and tool_calls:
            # Assistant turn that initiated tool calls
            call_snippets = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                call_snippets.append(
                    f"```tool_call\n{json.dumps({'name': fn.get('name'), 'arguments': fn.get('arguments')})}\n```"
                )
            body = f"[Assistant]:\n" + (f"{content}\n" if content else "") + "\n".join(call_snippets)
            formatted_parts.append(body)
        else:
            formatted_parts.append(f"[{role_cap}]:\n{content}")

    # Prompt assistant to respond
    formatted_parts.append("[Assistant]:")
    return "\n\n".join(formatted_parts)


def parse_tool_calls(
    raw_text: str,
    declared_tools: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Parses raw LLM text to extract tool calls.
    Returns:
        (clean_content, tool_calls)
        - clean_content: Leftover thought/text, or None if only tool calls.
        - tool_calls: List of OpenAI-compatible tool call dicts.
    """
    if not raw_text or not raw_text.strip():
        return None, []

    declared_names = set()
    if declared_tools:
        for t in declared_tools:
            name = t.get("function", {}).get("name")
            if name:
                declared_names.add(name)

    tool_calls: List[Dict[str, Any]] = []
    text_without_tools = raw_text

    # Candidate 1: Fenced blocks ```tool_call ... ``` or ```json ... ```
    matches = list(FENCE_BLOCK_REGEX.finditer(raw_text))
    matched_ranges = []

    for match in matches:
        block_content = match.group(1).strip()
        parsed = repair_json_string(block_content)

        if isinstance(parsed, dict) and "name" in parsed:
            # Potential tool call
            name = parsed.get("name")
            args = parsed.get("arguments", {})

            # If declared tools are supplied, verify the name is recognized
            if not declared_names or name in declared_names:
                args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                tool_calls.append({
                    "id": f"call_{uuid.uuid4().hex[:10]}",
                    "type": "function",
                    "function": {
                        "name": str(name),
                        "arguments": args_str,
                    },
                })
                matched_ranges.append((match.start(), match.end()))
        elif isinstance(parsed, dict) and "tool_calls" in parsed and isinstance(parsed["tool_calls"], list):
            # Batch tool calls inside one block: {"tool_calls": [{"name": "...", "arguments": ...}]}
            for item in parsed["tool_calls"]:
                if isinstance(item, dict) and "name" in item:
                    name = item.get("name")
                    args = item.get("arguments", {})
                    if not declared_names or name in declared_names:
                        args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                        tool_calls.append({
                            "id": f"call_{uuid.uuid4().hex[:10]}",
                            "type": "function",
                            "function": {
                                "name": str(name),
                                "arguments": args_str,
                            },
                        })
            matched_ranges.append((match.start(), match.end()))

    # Candidate 2: Tag-style blocks <tool_call> ... </tool_call>
    if not tool_calls:
        tag_matches = list(TAG_TOOL_CALL_REGEX.finditer(raw_text))
        for match in tag_matches:
            tag_content = match.group(1).strip()
            parsed = repair_json_string(tag_content)
            if isinstance(parsed, dict) and "name" in parsed:
                name = parsed.get("name")
                args = parsed.get("arguments", {})
                if not declared_names or name in declared_names:
                    args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                    tool_calls.append({
                        "id": f"call_{uuid.uuid4().hex[:10]}",
                        "type": "function",
                        "function": {
                            "name": str(name),
                            "arguments": args_str,
                        },
                    })
                    matched_ranges.append((match.start(), match.end()))

    # Candidate 3: Naked JSON without fences if raw text is strictly a JSON object with "name" and "arguments"
    if not tool_calls:
        parsed_naked = repair_json_string(raw_text.strip())
        if isinstance(parsed_naked, dict) and "name" in parsed_naked and "arguments" in parsed_naked:
            name = parsed_naked.get("name")
            args = parsed_naked.get("arguments", {})
            if not declared_names or name in declared_names:
                args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                tool_calls.append({
                    "id": f"call_{uuid.uuid4().hex[:10]}",
                    "type": "function",
                    "function": {
                        "name": str(name),
                        "arguments": args_str,
                    },
                })
                matched_ranges.append((0, len(raw_text)))

    # Compute leftover content
    if tool_calls and matched_ranges:
        # Remove matched tool blocks from text
        clean_pieces = []
        last_idx = 0
        for start, end in sorted(matched_ranges):
            clean_pieces.append(raw_text[last_idx:start])
            last_idx = end
        clean_pieces.append(raw_text[last_idx:])
        remaining = "".join(clean_pieces).strip()
        clean_content = remaining if remaining else None
    else:
        clean_content = raw_text

    return clean_content, tool_calls


def validate_tool_arguments(
    tool_name: str,
    arguments: Union[Dict[str, Any], str],
    declared_tools: List[Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    """
    Validates required parameters and basic schema constraints.
    Returns (is_valid, error_message).
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return False, f"Arguments for tool '{tool_name}' must be valid JSON."

    target_tool = None
    for t in declared_tools:
        if t.get("function", {}).get("name") == tool_name:
            target_tool = t.get("function")
            break

    if not target_tool:
        return False, f"Tool '{tool_name}' was not declared in tools list."

    params = target_tool.get("parameters", {})
    required = params.get("required", [])

    for req_field in required:
        if req_field not in arguments:
            return False, f"Missing required parameter '{req_field}' for tool '{tool_name}'."

    return True, None
