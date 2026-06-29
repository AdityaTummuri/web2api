#!/bin/bash

# Web2API CLI Client Helper
PROMPT="$*"

if [ -z "$PROMPT" ]; then
    echo "Usage: $0 <your prompt query>"
    echo "Example: $0 What is the capital of France?"
    exit 1
fi

RESPONSE=$(curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$PROMPT\"}")

# Pretty-print using python's json tool (or jq if installed)
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
