#!/usr/bin/env python3
"""
test_openai_client.py - Official OpenAI SDK Conformance Test for Web2API
Demonstrates standard OpenAI Python SDK connectivity against the local Web2API bridge.
"""

import sys
import time
from openai import OpenAI

# API configuration from api.txt
BASE_URL = "http://127.0.0.1:8000/v1"
API_KEY = "sk-w2a-dev-a7d4e1f9b3c820564917a2e8df3c9041"


def main():
    print("=" * 70)
    print("       Web2API Official OpenAI Python SDK Conformance Test")
    print("=" * 70)
    print(f"Connecting to: {BASE_URL}")
    print(f"Using API Key: {API_KEY[:16]}...")
    print("-" * 70)

    # Initialize standard OpenAI client
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    # 1. Test Models Listing
    print("\n[TEST 1] Listing models via client.models.list()...")
    try:
        models = client.models.list()
        model_ids = [m.id for m in models.data]
        print(f"✓ Found {len(model_ids)} models:")
        for mid in model_ids:
            print(f"  • {mid}")
        assert "gemini-pro" in model_ids
        assert "gemini-deep-research" in model_ids
        print("✓ Model catalog verified!")
    except Exception as e:
        print(f"✗ Models listing failed: {e}")
        return False

    # 2. Test Non-Streaming Chat Completion
    print("\n[TEST 2] Testing standard non-streaming chat completion...")
    try:
        start = time.time()
        response = client.chat.completions.create(
            model="gemini-pro",
            messages=[
                {"role": "user", "content": "Reply with exactly: PONG_SUCCESS"}
            ]
        )
        elapsed = time.time() - start
        content = response.choices[0].message.content
        print(f"✓ Received response in {elapsed:.2f}s:")
        print(f"  \"{content}\"")
        print(f"  Finish reason: {response.choices[0].finish_reason}")
    except Exception as e:
        print(f"✗ Non-streaming completion failed: {e}")
        return False

    # 3. Test Real-Time Streaming Chat Completion
    print("\n[TEST 3] Testing real-time streaming (stream=True)...")
    try:
        start = time.time()
        stream = client.chat.completions.create(
            model="gemini-pro",
            messages=[
                {"role": "user", "content": "Count from 1 to 5 with commas"}
            ],
            stream=True
        )
        print("✓ Stream output: ", end="", flush=True)
        chunks = 0
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
                chunks += 1
        elapsed = time.time() - start
        print(f"\n✓ Stream completed ({chunks} chunks in {elapsed:.2f}s)!")
    except Exception as e:
        print(f"✗ Streaming completion failed: {e}")
        return False

    # 4. Test Tool Calling / Function Calling
    print("\n[TEST 4] Testing OpenAI Tool Calling / Function Calling...")
    try:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_stock_quote",
                    "description": "Fetch real-time stock quote for a ticker symbol",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticker": {"type": "string", "description": "Stock ticker symbol e.g. AAPL"}
                        },
                        "required": ["ticker"]
                    }
                }
            }
        ]
        tool_res = client.chat.completions.create(
            model="gemini-pro",
            messages=[
                {"role": "user", "content": "Check the price for NVDA stock"}
            ],
            tools=tools,
            tool_choice="auto"
        )
        choice = tool_res.choices[0]
        print(f"✓ Finish reason: {choice.finish_reason}")
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                print(f"  Tool ID: {tc.id}")
                print(f"  Function: {tc.function.name}")
                print(f"  Arguments: {tc.function.arguments}")
            print("✓ Tool calling successfully parsed and returned!")
        else:
            print(f"  Content: {choice.message.content}")
    except Exception as e:
        print(f"✗ Tool calling failed: {e}")
        return False

    # 5. Test Deep Research Mode
    print("\n[TEST 5] Testing Gemini Deep Research Mode...")
    try:
        start = time.time()
        dr_res = client.chat.completions.create(
            model="gemini-deep-research",
            messages=[
                {"role": "user", "content": "Synthesize the evolution of Python type hints from PEP 484 to PEP 695"}
            ]
        )
        elapsed = time.time() - start
        print(f"✓ Deep Research response ({elapsed:.2f}s, length: {len(dr_res.choices[0].message.content)} chars):")
        print(f"  {dr_res.choices[0].message.content[:250]}...\n")
    except Exception as e:
        print(f"✗ Deep Research failed: {e}")
        return False

    print("=" * 70)
    print("       ALL OFFICIAL OPENAI CLIENT TESTS PASSED SUCCESSFULLY! ")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
