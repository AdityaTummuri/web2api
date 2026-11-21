"""
Unit tests for tool_parser.py (Tool Calling & Emulation Engine)
"""

import unittest
import json

from tool_parser import (
    repair_json_string,
    format_tools_prompt,
    format_conversation_with_tools,
    parse_tool_calls,
    validate_tool_arguments,
)


class TestToolParser(unittest.TestCase):

    def setUp(self):
        self.sample_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Fetch current weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"},
                            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_database",
                    "description": "Query internal database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    def test_format_tools_prompt(self):
        prompt = format_tools_prompt(self.sample_tools, tool_choice="auto")
        self.assertIn("AVAILABLE TOOLS", prompt)
        self.assertIn("`get_weather`", prompt)
        self.assertIn("`search_database`", prompt)
        self.assertIn("TOOL CALL OUTPUT CONTRACT", prompt)
        self.assertIn("```tool_call", prompt)

    def test_format_tools_prompt_required_and_specific(self):
        prompt_req = format_tools_prompt(self.sample_tools, tool_choice="required")
        self.assertIn("MUST call at least one of the available tools", prompt_req)

        prompt_specific = format_tools_prompt(
            self.sample_tools,
            tool_choice={"type": "function", "function": {"name": "get_weather"}}
        )
        self.assertIn("MUST call the function `get_weather`", prompt_specific)

    def test_format_conversation_with_tools(self):
        messages = [
            {"role": "user", "content": "What is the weather in Tokyo?"},
            {
                "role": "assistant",
                "content": "Let me check that for you.",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": {"location": "Tokyo"}}
                    }
                ]
            },
            {"role": "tool", "name": "get_weather", "tool_call_id": "call_123", "content": '{"temp": 18, "unit": "C"}'}
        ]

        formatted = format_conversation_with_tools(messages, self.sample_tools)
        self.assertIn("[System Instructions - Tool Calling Contract]", formatted)
        self.assertIn("[User]:\nWhat is the weather in Tokyo?", formatted)
        self.assertIn("[Tool Result for `get_weather` (id: call_123)]:", formatted)
        self.assertIn('{"temp": 18, "unit": "C"}', formatted)
        self.assertTrue(formatted.endswith("[Assistant]:"))

    def test_repair_json_string(self):
        # Trailing comma
        bad_json = '{"name": "get_weather", "arguments": {"location": "Paris",},}'
        repaired = repair_json_string(bad_json)
        self.assertIsNotNone(repaired)
        self.assertEqual(repaired["name"], "get_weather")
        self.assertEqual(repaired["arguments"]["location"], "Paris")

        # Single quotes
        single_quoted = "{'name': 'search_database', 'arguments': {'query': 'users'}}"
        repaired2 = repair_json_string(single_quoted)
        self.assertIsNotNone(repaired2)
        self.assertEqual(repaired2["name"], "search_database")

    def test_parse_tool_calls_fenced(self):
        raw_output = """
I will check the weather for Tokyo.
```tool_call
{
  "name": "get_weather",
  "arguments": {
    "location": "Tokyo",
    "unit": "celsius"
  }
}
```
        """
        content, calls = parse_tool_calls(raw_output, self.sample_tools)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "get_weather")
        args = json.loads(calls[0]["function"]["arguments"])
        self.assertEqual(args["location"], "Tokyo")
        self.assertEqual(content, "I will check the weather for Tokyo.")

    def test_parse_tool_calls_tag_style(self):
        raw_output = '<tool_call>{"name": "search_database", "arguments": {"query": "SELECT * FROM items"}}</tool_call>'
        content, calls = parse_tool_calls(raw_output, self.sample_tools)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "search_database")
        self.assertIsNone(content)

    def test_parse_tool_calls_multiple_parallel(self):
        raw_output = """
```tool_call
{"name": "get_weather", "arguments": {"location": "London"}}
```
```tool_call
{"name": "get_weather", "arguments": {"location": "New York"}}
```
        """
        content, calls = parse_tool_calls(raw_output, self.sample_tools)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["function"]["name"], "get_weather")
        self.assertEqual(calls[1]["function"]["name"], "get_weather")
        args0 = json.loads(calls[0]["function"]["arguments"])
        args1 = json.loads(calls[1]["function"]["arguments"])
        self.assertEqual(args0["location"], "London")
        self.assertEqual(args1["location"], "New York")

    def test_parse_tool_calls_no_tools(self):
        raw_output = "The capital of France is Paris. Have a great day!"
        content, calls = parse_tool_calls(raw_output, self.sample_tools)
        self.assertEqual(len(calls), 0)
        self.assertEqual(content, raw_output)

    def test_validate_tool_arguments(self):
        # Valid
        is_valid, err = validate_tool_arguments("get_weather", {"location": "Berlin"}, self.sample_tools)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

        # Missing required parameter
        is_valid, err = validate_tool_arguments("get_weather", {"unit": "celsius"}, self.sample_tools)
        self.assertFalse(is_valid)
        self.assertIn("Missing required parameter 'location'", err)

        # Undeclared tool
        is_valid, err = validate_tool_arguments("non_existent_tool", {}, self.sample_tools)
        self.assertFalse(is_valid)
        self.assertIn("was not declared", err)


if __name__ == "__main__":
    unittest.main()
