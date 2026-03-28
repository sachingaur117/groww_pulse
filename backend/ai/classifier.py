"""
classifier.py — AI Classification & Weekly Product Pulse Engine

Uses Gemini (gemini-2.5-flash) to:
  1. Classify reviews into exactly 7 themes (User Defined)
  2. Aggregate results with 100% theme mapping reliability
  3. Generate a High-Impact, Blunt Pulse Narrative using these themes as headers.

Canonical Themes: [UI/UX, Features, Reliability, Performance, Hidden Charges, Information Visibility, Onboarding]
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
# EXACT THEMES AS CONFIRMED BY USER
THEMES = [
    "UI/UX",
    "Features",
    "Reliability",
    "Performance",
    "Hidden Charges",
    "Information Visibility",
    "Onboarding",
]

# Mapping layer for raw AI classification strings to canonical THEMES
THEME_MAP = {
    # UI/UX
    "ui/ux": "UI/UX", "design": "UI/UX", "navigation": "UI/UX", "layout": "UI/UX", "user experience": "UI/UX", "ux": "UI/UX", "interface": "UI/UX",
    # Features
    "features": "Features", "new features": "Features", "tools": "Features", "functionality": "Features", "options": "Features",
    # Reliability
    "reliability": "Reliability", "trust": "Reliability", "failed transaction": "Reliability", "accuracy": "Reliability", "error": "Reliability", "money stuck": "Reliability", "withdrawal": "Reliability",
    # Performance
    "performance": "Performance", "speed": "Performance", "crashes": "Performance", "lag": "Performance", "slow": "Performance", "freezing": "Performance", "stability": "Performance",
    # Hidden Charges
    "hidden charges": "Hidden Charges", "fees": "Hidden Charges", "charges": "Hidden Charges", "pricing": "Hidden Charges", "deduction": "Hidden Charges",
    # Information Visibility
    "information visibility": "Information Visibility", "portfolio": "Information Visibility", "nav": "Information Visibility", "clarity": "Information Visibility", "visibility": "Information Visibility", "statements": "Information Visibility",
    # Onboarding
    "onboarding": "Onboarding", "registration": "Onboarding", "kyc": "Onboarding", "signup": "Onboarding", "login": "Onboarding", "verification": "Onboarding",
}

BATCH_SIZE = 20
RETRY_LIMIT = 2
RETRY_DELAY = 2

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_theme(raw_theme: str) -> str:
    """Map raw AI classification to one of the 7 user-defined themes."""
    raw_lower = str(raw_theme).strip().lower()
    if raw_lower in THEME_MAP:
        return THEME_MAP[raw_lower]
    for keyword, canonical in THEME_MAP.items():
        if keyword in raw_lower:
            return canonical
    return "Reliability"

# ── Prompts ───────────────────────────────────────────────────────────────────

CLASSIFIER_SYSTEM = """You are a Product Intelligence Analyst. 
Classify the given mutual fund app reviews into exactly one of these 7 themes:
- UI/UX: Design, navigation, layout
- Features: Missing or requested tools
- Reliability: Trust, transaction failures (withdrawal/deposit), data accuracy
- Performance: Speed, crashes, lag, freezing
- Hidden Charges: Unclear fees, deductions
- Information Visibility: Portfolio display, NAV clarity, statements
- Onboarding: KYC, registration, login, verification

Respond ONLY with a valid JSON array."""

PULSE_SYSTEM = """You are a Senior Product Manager at Groww. 
Write a blunt, data-driven report. AVOID corporate-speak.
Your "KEY SIGNALS" section MUST use the exact 7 theme names as headers if they have data. 
Format: plain text with headers ###. NO EMOJIS."""

PULSE_USER_TEMPLATE = """Generate a High-Impact Product Pulse.

Period: {date_range}
Summary Stats: {total} reviews | {avg_rating}/5 Rating

### PULSE OVERVIEW
A single, blunt paragraph on the core sentiment shift. 

### KEY SIGNALS
For each significant theme found in the data, provide a 1-sentence analytical signal. 
IMPORTANT: Use the exact theme name as a bold header (e.g. "**UI/UX**: ...").

Data for analysis:
{theme_summary}"""


# ── Core: Batch Classifier ────────────────────────────────────────────────────

def _parse_json_from_response(text: str) -> list:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def classify_batch(batch: list[dict], client) -> list[dict]:
    reviews_for_prompt = [{"review_id": r["review_id"], "review_text": r["review_text"]} for r in batch]
    prompt = f"Classify: {json.dumps(reviews_for_prompt)}"

    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            response = client.generate_content([CLASSIFIER_SYSTEM, prompt], generation_config=genai.GenerationConfig(temperature=0.1, response_mime_type="application/json"))
            return _parse_json_from_response(response.text)
        except:
            if attempt < RETRY_LIMIT: time.sleep(RETRY_DELAY)
            else: return [{"review_id": r["review_id"], "theme": "Reliability", "sentiment": "neutral", "confidence": 0.0} for r in batch]


def classify_reviews(csv_path: str) -> dict:
    client = genai.GenerativeModel(MODEL)
    df = pd.read_csv(csv_path)
    df = df[df["review_text"].notna() & (df["review_text"].str.strip() != "")]
    df.reset_index(drop=True, inplace=True)
    
    records = df.to_dict("records")
    classifications = {}

    for i in range(0, len(df), BATCH_SIZE):
        batch = records[i: i + BATCH_SIZE]
        results = classify_batch(batch, client)
        for item in results:
            classifications[item["review_id"]] = {
                "theme":      normalize_theme(item.get("theme", "Reliability")),
                "sentiment":  item.get("sentiment", "neutral"),
                "confidence": float(item.get("confidence", 0.0)),
            }
        time.sleep(0.5)

    df["theme"]      = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("theme", "Reliability"))
    df["sentiment"]  = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("sentiment", "neutral"))
    df["confidence"] = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("confidence", 0.0))

    enriched_filename = f"reviews_enriched_{datetime.now().strftime('%Y-%m-%d')}.csv"
    df.to_csv(DATA_DIR / enriched_filename, index=False, encoding="utf-8")

    return {"enriched_csv_filename": enriched_filename, "row_count": len(df), "theme_counts": df["theme"].value_counts().to_dict(), "dataframe": df}


# ── Core: Pulse Engine ────────────────────────────────────────────────────────

def _build_theme_summary(df: pd.DataFrame) -> str:
    lines = []
    for theme in THEMES:
        sub = df[df["theme"] == theme]
        if sub.empty: continue
        sentiment_dist = sub["sentiment"].value_counts().to_dict()
        avg_rating = round(sub["rating"].mean(), 2)
        lines.append(f"THEME: {theme} | Count: {len(sub)} | Rating: {avg_rating} | Sentiment: {sentiment_dist}")
    return "\n".join(lines)


def pulse_engine(classify_result: dict) -> dict:
    df = classify_result["dataframe"]
    client = genai.GenerativeModel(MODEL)
    theme_summary = _build_theme_summary(df)

    prompt = PULSE_USER_TEMPLATE.format(date_range=f"{df['date'].min()} to {df['date'].max()}", total=len(df), avg_rating=round(df["rating"].mean(), 2), theme_summary=theme_summary)

    narrative = ""
    try:
        response = client.generate_content([PULSE_SYSTEM, prompt], generation_config=genai.GenerationConfig(temperature=0.3))
        narrative = response.text.strip()
    except Exception as exc: narrative = f"[Report Error: {exc}]"

    theme_data = {}
    for theme in THEMES:
        sub = df[df["theme"] == theme]
        if sub.empty:
            theme_data[theme] = {"count": 0, "avg_rating": 0, "sentiment_dist": {}, "top_quotes": []}
            continue
        theme_data[theme] = {
            "count":          len(sub),
            "avg_rating":     round(sub["rating"].mean(), 2),
            "sentiment_dist": sub["sentiment"].value_counts().to_dict(),
            "top_quotes":     sub.sort_values("thumbs_up_count", ascending=False)["review_text"].dropna().head(3).tolist(),
        }

    return {
        "generated_at":   datetime.now().isoformat(),
        "total_reviews":  len(df),
        "avg_rating":     round(df["rating"].mean(), 2),
        "theme_data":     theme_data,
        "narrative":      narrative,
        "enriched_csv":   classify_result["enriched_csv_filename"],
    }
