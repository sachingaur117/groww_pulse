"""
classifier.py — AI Classification & Weekly Product Pulse Engine

Uses Gemini (gemini-2.0-flash) to:
  1. Classify each review into one of 7 themes with sentiment + confidence
  2. Aggregate results by theme
  3. Generate the narrative Weekly Product Pulse report

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

BATCH_SIZE = 20          # reviews per Gemini call
RETRY_LIMIT = 3          # retries on transient failure
RETRY_DELAY = 4          # seconds between retries

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# ── Prompts ───────────────────────────────────────────────────────────────────

CLASSIFIER_SYSTEM = """You are a Product Intelligence Analyst specializing in mobile app reviews for a mutual fund / investment platform.

You will be given a JSON array of reviews. For each review, classify it into exactly one of these 7 themes:
- UI/UX: App design, navigation, layout issues or praise
- Performance: Crashes, slow loading, freezes, battery drain
- Hidden Charges: Unexpected fees, unclear deductions, fee confusion
- Onboarding: KYC, registration, first-time setup experience
- Features: Missing, broken, or requested product features
- Information Visibility: Portfolio display, NAV clarity, statement access, transparency
- Reliability: Failed transactions, incorrect data, trust issues, money not credited

Also classify the sentiment as: positive | negative | neutral
And provide a confidence score between 0.0 and 1.0.

Respond ONLY with a valid JSON array. No markdown, no explanation. Each element:
{
  "review_id": "<id>",
  "theme": "<theme>",
  "sentiment": "<positive|negative|neutral>",
  "confidence": <float>
}"""

CLASSIFIER_USER_TEMPLATE = """Classify these {n} reviews:

{reviews_json}"""


PULSE_SYSTEM = """You are a Senior Product Manager at Groww writing an internal Weekly Product Pulse report for leadership.
You will receive aggregated data about app reviews segmented by theme.
Write a professional, enterprise-grade narrative report. Be direct, authoritative, and data-driven. Use numbers and percentages where appropriate.
Format: plain text with clear section headers using ###. No markdown tables.
IMPORTANT: DO NOT USE ANY EMOJIS in the report. The tone must be strictly professional and suitable for executive review."""

PULSE_USER_TEMPLATE = """Generate an executive Weekly Product Pulse report for the Groww app.

Period: {date_range}
Total reviews analyzed: {total}
Average rating: {avg_rating} / 5

Aggregated Data for context (DO NOT write these as a list in the narrative):
{theme_summary}

Write the report in exactly two sections:

### EXECUTIVE OVERVIEW
A 2-paragraph high-level summary of product health. The first paragraph should cover key themes and sentiment. The second paragraph should interpret the data and provide strategic context for leadership.

### OVERALL SIGNAL
A final 3-sentence summary highlighting the most critical fix required this week and any notable green flags.

IMPORTANT: Focus ONLY on these two sections. Do not provide a per-theme breakdown in this text report, as it will be handled by our structured UI cards."""


# ── Core: Batch Classifier ────────────────────────────────────────────────────

def _parse_json_from_response(text: str) -> list:
    """Extract JSON array from Gemini response, tolerating markdown fences."""
    text = text.strip()
    # Strip ```json ... ``` fences if present
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def classify_batch(batch: list[dict], client) -> list[dict]:
    """Send one batch of reviews to Gemini for classification."""
    reviews_for_prompt = [
        {"review_id": r["review_id"], "review_text": r["review_text"]}
        for r in batch
    ]
    prompt = CLASSIFIER_USER_TEMPLATE.format(
        n=len(batch),
        reviews_json=json.dumps(reviews_for_prompt, ensure_ascii=False, indent=2),
    )

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
                print(f"\n⚠️  Batch failed after {RETRY_LIMIT} retries: {exc}")
                # Return neutral fallback for each review in the batch
                return [
                    {
                        "review_id": r["review_id"],
                        "theme": "Reliability",
                        "sentiment": "neutral",
                        "confidence": 0.0,
                    }
                    for r in batch
                ]


def classify_reviews(csv_path: str) -> dict:
    """
    Classify all reviews in a CSV. Adds theme/sentiment/confidence columns.

    Returns:
        dict with enriched_csv_path, enriched_csv_filename, row_count, theme_counts
    """
    client = genai.GenerativeModel(MODEL)
    df = pd.read_csv(csv_path)

    # Drop rows with empty review text
    df = df[df["review_text"].notna() & (df["review_text"].str.strip() != "")]
    df.reset_index(drop=True, inplace=True)
    total = len(df)
    print(f"\n🤖 Classifying {total} reviews using Gemini ({MODEL})...")

    # ── Batch processing ──────────────────────────────────────────────────────
    records = df.to_dict("records")
    classifications: dict[str, dict] = {}  # review_id → {theme, sentiment, confidence}

    for i in range(0, total, BATCH_SIZE):
        batch = records[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"   Batch {batch_num}/{total_batches} ({len(batch)} reviews)...", end="\r")

        results = classify_batch(batch, client)

        for item in results:
            classifications[item["review_id"]] = {
                "theme":      item.get("theme", "Reliability"),
                "sentiment":  item.get("sentiment", "neutral"),
                "confidence": float(item.get("confidence", 0.0)),
            }

        # Brief pause to stay within Gemini rate limits
        time.sleep(1)

    print(f"\n✅ Classification complete for {len(classifications)} reviews.")

    # ── Merge back to DataFrame ───────────────────────────────────────────────
    df["theme"]      = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("theme", "Reliability"))
    df["sentiment"]  = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("sentiment", "neutral"))
    df["confidence"] = df["review_id"].map(lambda rid: classifications.get(rid, {}).get("confidence", 0.0))

    # ── Save enriched CSV ─────────────────────────────────────────────────────
    today_str = datetime.now().strftime("%Y-%m-%d")
    enriched_filename = f"reviews_enriched_{today_str}.csv"
    enriched_path = DATA_DIR / enriched_filename
    df.to_csv(enriched_path, index=False, encoding="utf-8")

    theme_counts = df["theme"].value_counts().to_dict()
    print(f"   Saved to: {enriched_path}")

    return {
        "enriched_csv_path":     str(enriched_path),
        "enriched_csv_filename": enriched_filename,
        "row_count":             len(df),
        "theme_counts":          theme_counts,
        "dataframe":             df,          # passed internally to pulse_engine
    }


# ── Core: Pulse Engine ────────────────────────────────────────────────────────

def _build_theme_summary(df: pd.DataFrame) -> str:
    """Summarise each theme for the pulse prompt."""
    lines = []
    for theme in THEMES:
        sub = df[df["theme"] == theme]
        if sub.empty:
            continue
        count = len(sub)
        sentiment_dist = sub["sentiment"].value_counts().to_dict()
        dominant = max(sentiment_dist, key=sentiment_dist.get)
        avg_rating = round(sub["rating"].mean(), 2)
        # Top 2 quotes (shortest, most legible)
        quotes = (
            sub["review_text"]
            .dropna()
            .str.strip()
            .loc[sub["review_text"].str.len() > 10]
            .sort_values(key=lambda s: s.str.len())
            .head(2)
            .tolist()
        )
        quote_str = " | ".join(f'"{q[:120]}"' for q in quotes)
        lines.append(
            f"[{theme}] — {count} reviews | Avg rating: {avg_rating} | "
            f"Dominant sentiment: {dominant} | Sentiments: {sentiment_dist}\n"
            f"  Sample quotes: {quote_str}"
        )
    return "\n\n".join(lines)


def pulse_engine(classify_result: dict) -> dict:
    """
    Generate the Weekly Product Pulse narrative using Gemini.

    Args:
        classify_result: return value from classify_reviews()

    Returns:
        pulse_report dict with narrative and structured per-theme data
    """
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

    print("\n📊 Generating Weekly Product Pulse narrative...")

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

    # ── Per-theme structured data ─────────────────────────────────────────────
    theme_data = {}
    for theme in THEMES:
        sub = df[df["theme"] == theme]
        if sub.empty:
            theme_data[theme] = {
                "count": 0, "avg_rating": None,
                "sentiment_dist": {}, "top_quotes": [],
            }
            continue
        sentiment_dist = sub["sentiment"].value_counts().to_dict()
        top_quotes = (
            sub.sort_values("thumbs_up_count", ascending=False)["review_text"]
            .dropna()
            .head(3)
            .tolist()
        )
        theme_data[theme] = {
            "count":          len(sub),
            "avg_rating":     round(sub["rating"].mean(), 2),
            "sentiment_dist": sentiment_dist,
            "top_quotes":     top_quotes,
        }

    pulse_report = {
        "generated_at":   datetime.now().isoformat(),
        "date_range":     {"from": df["date"].min(), "to": df["date"].max()},
        "total_reviews":  len(df),
        "avg_rating":     avg_rating,
        "theme_counts":   classify_result["theme_counts"],
        "theme_data":     theme_data,
        "narrative":      narrative,
        "enriched_csv":   classify_result["enriched_csv_filename"],
    }

    print("✅ Pulse report generated.")
    return pulse_report
