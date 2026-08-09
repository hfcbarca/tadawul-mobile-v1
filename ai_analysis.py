from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"


def gemini_available() -> bool:
    return bool(GEMINI_API_KEY)


def analyze_stock_with_gemini(stock_data: dict) -> str:
    if not GEMINI_API_KEY:
        return "Gemini is not connected. GEMINI_API_KEY is missing."

    prompt = f"""
You are an AI research assistant inside a Saudi stock paper-trading tool.

IMPORTANT RULES:
- Do NOT change the system's BUY/WATCH/AVOID signal.
- Do NOT issue a new buy or sell recommendation.
- Analyze only the supplied technical data.
- Keep the response concise and practical.
- Mention the strongest positives, main risks, and what should be watched next.
- This is a paper-trading research tool, not real-money execution.

Stock data:
{json.dumps(stock_data, ensure_ascii=False, default=str)}

Return the analysis in this format:

Summary:
...

Strengths:
...

Risks:
...

Watch next:
...
""".strip()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500,
        },
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))

        candidates = result.get("candidates", [])

        if not candidates:
            return "Gemini returned no analysis."

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
        )

        text_parts = [
            part.get("text", "")
            for part in parts
            if part.get("text")
        ]

        if not text_parts:
            return "Gemini returned an empty response."

        return "\n".join(text_parts).strip()

    except urllib.error.HTTPError as e:
        details = e.read().decode("utf-8", errors="ignore")
        return f"Gemini API error ({e.code}): {details[:300]}"

    except Exception as e:
        return f"Gemini connection error: {e}"
