from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]


def gemini_available() -> bool:
    return bool(GEMINI_API_KEY)


def _call_gemini(model: str, prompt: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 450,
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

    with urllib.request.urlopen(
        request,
        timeout=35,
    ) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError("Gemini returned no analysis.")

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
        raise RuntimeError("Gemini returned an empty response.")

    return text


def analyze_stock_with_gemini(stock_data: dict) -> str:
    if not GEMINI_API_KEY:
        return "Gemini is not connected."

    prompt = f"""
You are an AI analyst inside Tadawul V1,
a Saudi stock paper-trading research application.

Analyze only the supplied technical data.

Rules:
- Do not change the system BUY/WATCH/AVOID signal.
- Do not create a new trading signal.
- Do not recommend real-money trading.
- Be concise and practical.
- Maximum 140 words.
- Focus on trend, momentum, confirmation and risk.

Stock data:
{json.dumps(stock_data, ensure_ascii=False, default=str)}

Return exactly:

AI View: Positive / Neutral / Cautious

Trend:
...

Signal quality:
...

Strengths:
• ...
• ...

Risks:
• ...
• ...

Watch next:
...

Bottom line:
...
""".strip()

    last_error = ""

    for model in MODELS:
        for attempt in range(2):
            try:
                return _call_gemini(
                    model,
                    prompt,
                )

            except urllib.error.HTTPError as e:
                details = e.read().decode(
                    "utf-8",
                    errors="ignore",
                )

                last_error = (
                    f"{model}: HTTP {e.code} "
                    f"{details[:180]}"
                )

                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(2 + attempt * 2)
                    continue

                return f"Gemini API error: {last_error}"

            except Exception as e:
                last_error = f"{model}: {e}"
                time.sleep(1)

    return (
        "Gemini is temporarily unavailable after automatic retries. "
        f"Last error: {last_error}"
    )
