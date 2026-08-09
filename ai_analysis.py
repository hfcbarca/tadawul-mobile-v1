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


def _call_gemini(model: str, stock_data: dict) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )

    prompt = f"""
You are the AI analysis layer inside Tadawul V1,
a Saudi stock paper-trading research application.

Analyze ONLY the supplied technical data.

Important rules:
- Do NOT change the existing BUY/WATCH/AVOID signal.
- Do NOT create a new trading signal.
- Do NOT recommend real-money trading.
- Be concise, specific and practical.
- Base every conclusion on the supplied data.
- Keep every text field short.

Stock data:
{json.dumps(stock_data, ensure_ascii=False, default=str)}

Return a JSON object with exactly these fields:

{{
  "ai_view": "Positive, Neutral, or Cautious",
  "trend": "one short sentence",
  "signal_quality": "one short sentence",
  "strength_1": "short point",
  "strength_2": "short point",
  "risk_1": "short point",
  "risk_2": "short point",
  "watch_next": "one specific technical condition to monitor",
  "bottom_line": "one short conclusion"
}}

Return JSON only.
""".strip()

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt,
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 1200,
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
        timeout=40,
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

    raw_text = "".join(
        part.get("text", "")
        for part in parts
        if part.get("text")
    ).strip()

    if not raw_text:
        raise RuntimeError("Gemini returned an empty response.")

    raw_text = (
        raw_text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    analysis = json.loads(raw_text)

    ai_view = analysis.get("ai_view", "Neutral")
    trend = analysis.get("trend", "Not available.")
    signal_quality = analysis.get(
        "signal_quality",
        "Not available.",
    )

    strength_1 = analysis.get(
        "strength_1",
        "Not available.",
    )
    strength_2 = analysis.get(
        "strength_2",
        "Not available.",
    )

    risk_1 = analysis.get(
        "risk_1",
        "Not available.",
    )
    risk_2 = analysis.get(
        "risk_2",
        "Not available.",
    )

    watch_next = analysis.get(
        "watch_next",
        "Not available.",
    )

    bottom_line = analysis.get(
        "bottom_line",
        "Not available.",
    )

    return f"""AI View: {ai_view}

Trend:
{trend}

Signal quality:
{signal_quality}

Strengths:
• {strength_1}
• {strength_2}

Risks:
• {risk_1}
• {risk_2}

Watch next:
{watch_next}

Bottom line:
{bottom_line}"""


def analyze_stock_with_gemini(stock_data: dict) -> str:
    if not GEMINI_API_KEY:
        return "Gemini is not connected."

    last_error = ""

    for model in MODELS:
        for attempt in range(2):
            try:
                return _call_gemini(
                    model,
                    stock_data,
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

                if e.code in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    time.sleep(2 + attempt * 2)
                    continue

                return (
                    "Gemini API error: "
                    f"{last_error}"
                )

            except json.JSONDecodeError:
                last_error = (
                    f"{model}: invalid JSON response"
                )
                time.sleep(1)
                continue

            except Exception as e:
                last_error = f"{model}: {e}"
                time.sleep(1)

    return (
        "Gemini is temporarily unavailable after "
        "automatic retries. "
        f"Last error: {last_error}"
    )
