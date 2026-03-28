"""
classifier.py — AI Classification & Weekly Product Pulse Engine

Uses Gemini (gemini-2.5-flash) to:
  1. Classify each review into one of 7 themes with sentiment + confidence
  2. Aggregate results by theme (Strict Canonical Mapping)
  3. Generate the narrative Weekly Product Pulse report (High Impact)

Usage (importable):
    from backend.ai.classifier import classify_reviews, pulse_engine
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── Gemini setup ──────────────────────────────────────────────────────────────
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

# ── Constants ─────────────────────────────────────────────────────────────────
THEMES = [
    "UI/UX",
    "Performance",
    "Hidden Charges",
    "Onboarding",
    "Features",
    "Information Visibility",
    "Reliability",
]

# Mapping layer for raw AI classification strings to canonical THEMES
THEME_MAP = {
    "ui/ux": "UI/UX", "design": "UI/UX", "navigation": "UI/UX", "layout": "UI/UX", "user experience": "UI/UX", "ux": "UI/UX",
    "performance": "Performance", "speed": "Performance", "crashes": "Performance", "lag": "Performance", "slow": "Performance",
    "hidden charges": "Hidden Charges", "fees": "Hidden Charges", "charges": "Hidden Charges", "pricing": "Hidden Charges",
    "onboarding": "Onboarding", "registration": "Onboarding", "kyc": "Onboarding", "signup": "Onboarding",
    "features": "Features", "new features": "Features", "tools": "Features", "functionality": "Features",
    "information visibility": "Information Visibility", "portfolio": "Information Visibility", "nav": "Information Visibility", "clarity": "Information Visibility", "visibility": "Information Visibility",
    "reliability": "Reliability", "trust": "Reliability", "failed transaction": "Reliability", "accuracy": "Reliability",
}

BATCH_SIZE = 20          # reviews per Gemini call
RETRY_LIMIT = 3          # retries on transient failure
RETRY_DELAY = 4          # seconds between retries

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_theme(raw_theme: str) -> str:
    """Map raw AI classification to one of the 7 canonical themes."""
    raw_lower = str(raw_theme).strip().lower()
    # 1. Direct match in map
    if raw_lower in THEME_MAP:
        return THEME_MAP[raw_lower]
    # 2. Loose keyword match
    for keyword, canonical in THEME_MAP.items():
        if keyword in raw_lower:
            return canonical
    # 3. Default fallback
    return "Reliability"

# ── Prompts ───────────────────────────────────────────────────────────────────

CLASSIFIER_SYSTEM = """You are a Product Intelligence Analyst. 
Classify the given mutual fund app reviews into exactly one of these 7 themes:
- UI/UX: Design, navigation, layout
- Performance: Speed, crashes, loading
- Hidden Charges: Unclear fees, deductions
- Onboarding: KYC, registration, login
- Features: Missing or requested tools
- Information Visibility: Portfolio display, NAV clarity, statements
- Reliability: Trust, transaction failures, data accuracy

Respond ONLY with a valid JSON array. Each element:
{
  "review_id": "<id>",
  "theme": "<UI/UX|Performance|Hidden Charges|Onboarding|Features|Information Visibility|Reliability>",
  "sentiment": "<positive|negative|neutral>",
  "confidence": <float>
}"""

PULSE_SYSTEM = """You are a Senior Product Manager at Groww writing a punchy, data-driven Weekly Product Pulse report.
AVOID generic corporate-speak or filler like "standard of user satisfaction" or "proactive stance."
Focus on SHARP, action-oriented signals. Be direct. Use numbers. Identify exactly what is breaking or winning.
Format: plain text with headers ###. NO EMOJIS."""

PULSE_USER_TEMPLATE = """Generate a high-impact Product Pulse report for the Groww app.

Period: {date_range}
Total reviews analyzed: {total}
Average rating: {avg_rating} / 5

### PULSE OVERVIEW
A 1-paragraph summary of the core sentiment shift and the #1 most talked about issue. Be blunt.

### KEY SIGNALS
List 3 specific, data-backed findings. (e.g., "Performance mentions up 12% due to login lag").

IMPORTANT: NO per-theme breakdown here. Keep it to these 2 sections."""


# ── Core: Batch Classifier ────────────────────────────────────────────────────

def _parse_json_from_response(text: str) -> list:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def classify_batch(batch: list[dict], client) -> list[dict]:
    reviews_for_prompt = [
        {"review_id": r["review_id"], "review_text": r["review_text"]}
        for r in batch
    ]
    prompt = f"Classify {len(batch)} reviews:\n\n{json.dumps(reviews_for_prompt, ensure_ascii=False, indent=2)}"

    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            response = client.generate_content(
                [CLASSIFIER_SYSTEM, prompt],
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            return _parse_json_from_response(response.text)
        except Exception as exc:
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY * attempt)
            else:
                return [{"review_id": r["review_id"], "theme": "Reliability", "sentiment": "neutral", "confidence": 0.0} for r in batch]


def classify_reviews(csv_path: str) -> dict:
    client = genai.GenerativeModel(MODEL)
    df = pd.read_csv(csv_path)

    df = df[df["review_text"].notna() & (df["review_text"].str.strip() != "")]
    df.reset_index(drop=True, inplace=True)
    total = len(df)
    print(f"\n🤖 Classifying {total} reviews...")

    records = df.to_dict("records")
    classifications: dict[str, dict] = {}

    for i in range(0, total, BATCH_SIZE):
        batch = records[i: i + BATCH_SIZE]
        results = classify_batch(batch, client)
        for item in results:
            classifications[item["review_id"]] = {
                "theme":      normalize_theme(item.get("theme", "Reliability")),
                "sentiment":  item.get("sentiment", "neutral"),
                "confidence": float(item.get("confidence", 0.0)),
            }
        time.sleep(1)

    df["theme"]      = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("theme", "Reliability"))
    df["sentiment"]  = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("sentiment", "neutral"))
    df["confidence"] = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("confidence", 0.0))

    today_str = datetime.now().strftime("%Y-%m-%d")
    enriched_filename = f"reviews_enriched_{today_str}.csv"
    enriched_path = DATA_DIR / enriched_filename
    df.to_csv(enriched_path, index=False, encoding="utf-8")

    return {
        "enriched_csv_filename": enriched_filename,
        "row_count":             len(df),
        "theme_counts":          df["theme"].value_counts().to_dict(),
        "dataframe":             df,
    }


# ── Core: Pulse Engine ────────────────────────────────────────────────────────

def _build_theme_summary(df: pd.DataFrame) -> str:
    lines = []
    for theme in THEMES:
        sub = df[df["theme"] == theme]
        if sub.empty:
            continue
        count = len(sub)
        sentiment_dist = sub["sentiment"].value_counts().to_dict()
        dominant = max(sentiment_dist, key=sentiment_dist.get)
        avg_rating = round(sub["rating"].mean(), 2)
        quotes = (
            sub["review_text"]
            .dropna().str.strip()
            .loc[sub["review_text"].str.len() > 10]
            .sort_values(key=lambda s: s.str.len())
            .head(2).tolist()
        )
        quote_str = " | ".join(f'"{q[:120]}"' for q in quotes)
        lines.append(f"[{theme}] — {count} reviews | {avg_rating}★ | {dominant} sentiment | Quotes: {quote_str}")
    return "\n\n".join(lines)


def pulse_engine(classify_result: dict) -> dict:
    df: pd.DataFrame = classify_result["dataframe"]
    client = genai.GenerativeModel(MODEL)

    date_range = f"{df['date'].min()} → {df['date'].max()}"
    avg_rating = round(df["rating"].mean(), 2)
    theme_summary = _build_theme_summary(df)

    prompt = PULSE_USER_TEMPLATE.format(
        date_range=date_range,
        total=len(df),
        avg_rating=avg_rating,
        theme_summary=theme_summary,
    )

    narrative = ""
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            response = client.generate_content(
                [PULSE_SYSTEM, prompt],
                generation_config=genai.GenerationConfig(temperature=0.4),
            )
            narrative = response.text.strip()
            break
        except Exception as exc:
            if attempt < RETRY_LIMIT:
                time.sleep(RETRY_DELAY * attempt)
            else:
                narrative = f"[Pulse generation failed: {exc}]"

    theme_data = {}
    for theme in THEMES:
        sub = df[df["theme"] == theme]
        if sub.empty:
            theme_data[theme] = {"count": 0, "avg_rating": None, "sentiment_dist": {}, "top_quotes": []}
            continue
        theme_data[theme] = {
            "count":          len(sub),
            "avg_rating":     round(sub["rating"].mean(), 2),
            "sentiment_dist": sub["sentiment"].value_counts().to_dict(),
            "top_quotes":     sub.sort_values("thumbs_up_count", ascending=False)["review_text"].dropna().head(3).tolist(),
        }

    return {
        "generated_at":   datetime.now().isoformat(),
        "date_range":     {"from": df["date"].min(), "to": df["date"].max()},
        "total_reviews":  len(df),
        "avg_rating":     avg_rating,
        "theme_counts":   classify_result["theme_counts"],
        "theme_data":     theme_data,
        "narrative":      narrative,
        "enriched_csv":   classify_result["enriched_csv_filename"],
    }
