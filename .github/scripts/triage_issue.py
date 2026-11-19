#!/usr/bin/env python3
"""Classify an issue as clear or requiring clarification using the OpenAI API."""

import json
import os
import sys
import urllib.request


def main():
    issue = json.load(sys.stdin)
    prompt = {
        "issue": issue,
        "rules": [
            "Decide whether a competent engineer can implement the issue without asking a question.",
            "Ask only questions whose answers change the implementation, acceptance criteria, or safety.",
            "Treat existing repository behavior as context, not as permission to invent requirements.",
            "Return JSON only with status clear or needs_clarification, questions, and summary.",
            "Use at most five concise questions.",
        ],
        "schema": {
            "status": "clear | needs_clarification",
            "questions": ["string"],
            "summary": "string",
        },
    }
    body = json.dumps({
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": "You are a requirements triage assistant."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }).encode()
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.loads(response.read())
    result = json.loads(payload["choices"][0]["message"]["content"])
    status = result.get("status")
    if status not in {"clear", "needs_clarification"}:
        raise ValueError("AI returned an invalid triage status")
    result["questions"] = [str(q).strip() for q in result.get("questions", []) if str(q).strip()][:5]
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
