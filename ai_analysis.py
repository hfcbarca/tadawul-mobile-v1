from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.6-flash"


def gemini_available() -> bool:
    return bool(GEMINI_API_KEY)


def analyze_stock_with_gemini(stock_data: dict) -> str:
    if not GEMINI_API_KEY:
        return "Gemini is not connected."

    prompt = f"""
You are an AI analyst inside a Saudi stock paper-trading application.

Analyze ONLY the supplied technical data.

Important:
- Do not change the system's existing BUY/WATCH/AVOID classification.
- Do not create a new trading signal.
- Do not recommend real-money trading.
- Be concise but useful.
- Maximum about 120 words.
- Give a practical assessment, not a generic explanation.

Stock data:
{json.dumps(stock_data, ensure_ascii=False, default=str)}

Respond exactly in this format:

AI View: [Positive / Neutral / Cautious]

Trend:
[one short sentence]

Signal quality:
[one short sentence explaining whether the technical data supports or weakens the existing setup]

Main strengths:
[maximum 2 points]

Main risks:
[maximum 2 points]

Watch next:
[one specific technical condition or level to monitor]

Bottom line:
[one short sentence]
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
            "temperature": 0.15,
            "maxOutputTokens": 350,
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
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

        candidates = result.get("candidates", [])

        if not candidates:
            return "Gemini returned no analysis."

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
        )

        text = "\n".join(
            part.get("text", "")
            for part in parts
            if part.get("text")
        ).strip()

        if not text:
            return "Gemini returned an empty response."

        return text

    except urllib.error.HTTPError as e:
        details = e.read().decode(
            "utf-8",
            errors="ignore",
        )
        return (
            f"Gemini API error ({e.code}): "
            f"{details[:300]}"
        )

    except Exception as e:
        return f"Gemini connection error: {e}"
