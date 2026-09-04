#!/bin/bash

# Web2API CLI Client Helper
# Sends a prompt to the local Gemini Web2API server and prints the JSON response.
# Requires the server to already be running via ./start.sh serve.

# Combine all command-line arguments into a single prompt string
PROMPT="$*"

if [ -z "$PROMPT" ]; then
    echo "Usage: $0 <your prompt query>"
    echo "Example: $0 What is the capital of France?"
    exit 1
fi

# POST the prompt to the local /api/chat endpoint
RESPONSE=$(curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$PROMPT\"}")

# Pretty-print using python's json tool (or jq if installed)
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
