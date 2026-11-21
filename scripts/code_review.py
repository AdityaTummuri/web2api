#!/usr/bin/env python3
"""
scripts/code_review.py - AI-Powered Professional Code Review Engine
Performs comprehensive multi-dimensional code reviews on source files or git diffs
using Web2API (supporting Gemini Deep Research, Claude 3.5 Sonnet, and GPT-4o).
"""

import os
import sys
import argparse
import time
from typing import Optional
from openai import OpenAI

DEFAULT_BASE_URL = os.getenv("WEB2API_BASE", "http://127.0.0.1:8000/v1")
DEFAULT_API_KEY = os.getenv("WEB2API_API_KEY", "sk-w2a-research-8e2b5c19fa7048361092a4f6de8a3b57")

REVIEW_SYSTEM_PROMPT = """You are a Principal Software Architect and Staff Security Engineer conducting a rigorous, professional code review.
Analyze the provided code thoroughly. Do not give shallow praise. Be precise, objective, and actionable.

Structure your review into the following exact sections:

## 1. Executive Summary & Architecture
- High-level architecture, design pattern adherence, and design trade-offs.
- Modularity, decoupling, and maintainability score (1-10).

## 2. Critical Bugs & Logic Flaws
- Edge cases where the code crashes, enters infinite loops, or returns incorrect data.
- State mutation issues, unhandled exceptions, and null pointer / None dereferences.

## 3. Security & Input Sanitization
- Vulnerability scan: injection, unvalidated deserialization, unauthenticated paths.
- Information leakage, timing attacks, or credential handling.

## 4. Concurrency, Async & Resource Leaks
- Race conditions, deadlock potential, unclosed sockets/file descriptors.
- Async correctness: unawaited coroutines, blocking calls inside async loops.

## 5. Performance & Algorithmic Complexity
- Time and space complexity (Big-O analysis).
- Inefficient operations, redundant allocations, or bottlenecks.

## 6. Actionable Improvements & Suggested Diffs
- Concrete code diffs showing exactly how to fix the identified issues.
"""


def review_code(
    file_path: Optional[str] = None,
    diff_text: Optional[str] = None,
    model: str = "gemini-deep-research",
    base_url: str = DEFAULT_BASE_URL,
    api_key: str = DEFAULT_API_KEY,
    output_path: Optional[str] = None
) -> str:
    client = OpenAI(base_url=base_url, api_key=api_key)

    if file_path:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            code_content = f.read()
        target_name = os.path.basename(file_path)
        prompt_content = f"Please conduct a comprehensive code review on the file `{target_name}`:\n\n```python\n{code_content}\n```"
    elif diff_text:
        target_name = "Git Working Tree Diff"
        prompt_content = f"Please conduct a comprehensive code review on the following git changes:\n\n```diff\n{diff_text}\n```"
    else:
        raise ValueError("Either file_path or diff_text must be provided.")

    print(f"\n[REVIEW] Initiating Code Review for: {target_name}")
    print(f"[REVIEW] Model: {model} | Server: {base_url}")
    print("[REVIEW] Analyzing code across Architecture, Security, Concurrency, and Performance...\n")

    start_time = time.time()

    # Call OpenAI endpoint with streaming output for real-time progress
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_content}
        ],
        stream=True
    )

    full_report = []
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            sys.stdout.write(delta)
            sys.stdout.flush()
            full_report.append(delta)

    elapsed = time.time() - start_time
    report_text = "".join(full_report)
    print(f"\n\n[REVIEW] Review completed in {elapsed:.2f} seconds ({len(report_text)} characters).\n")

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"[REVIEW] Report saved to: {output_path}")

    return report_text


def main():
    parser = argparse.ArgumentParser(description="Web2API AI Code Review Utility")
    parser.add_argument("file", nargs="?", help="Path to code file to review")
    parser.add_argument("--diff", action="store_true", help="Review current uncommitted git diff")
    parser.add_argument("--model", default="gemini-deep-research", help="AI Model to use (default: gemini-deep-research)")
    parser.add_argument("--output", "-o", help="Output Markdown report file path")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Web2API base URL")

    args = parser.parse_args()

    if args.diff:
        import subprocess
        diff_out = subprocess.check_output(["git", "diff", "HEAD"]).decode("utf-8")
        if not diff_out.strip():
            print("[INFO] No uncommitted git diff found. Exiting.")
            sys.exit(0)
        review_code(diff_text=diff_out, model=args.model, base_url=args.base_url, output_path=args.output)
    elif args.file:
        review_code(file_path=args.file, model=args.model, base_url=args.base_url, output_path=args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
