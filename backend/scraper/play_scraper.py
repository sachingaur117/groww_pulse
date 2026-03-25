"""
play_scraper.py — Google Play Store Review Scraper for Groww

Usage (CLI):
    python backend/scraper/play_scraper.py --days 7
    python backend/scraper/play_scraper.py --days 30 --app-id com.nextbillion.groww

Output:
    data/reviews_YYYY-MM-DD.csv
"""

import argparse
import os
import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from google_play_scraper import Sort, reviews

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_APP_ID = os.getenv("GROWW_APP_ID", "com.nextbillion.groww")
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BATCH_SIZE = 200  # reviews per API page

def is_valid_review(text: str) -> bool:
    """Filter out short, unhelpful, or PII-containing reviews."""
    if not text:
        return False
    text = text.strip()
    if len(text) <= 6:
        return False
    if len(text.split()) <= 2:
        return False
    # PII Checks
    if re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text): # Email
        return False
    if re.search(r"\b\d{10}\b", text): # 10-digit Phone Number (India)
        return False
    return True


# ── Core Scrape Function ──────────────────────────────────────────────────────

def scrape_reviews(days: int = 7, app_id: str = DEFAULT_APP_ID) -> dict:
    """
    Scrape Google Play reviews for the last `days` days.

    Returns:
        dict with keys: csv_path, row_count, date_range
    """
    cutoff_dt = datetime.now(tz=timezone.utc) - timedelta(days=days)
    print(f"\n🔍 Scraping reviews for '{app_id}' from the last {days} day(s)...")
    print(f"   Cutoff date : {cutoff_dt.strftime('%Y-%m-%d %H:%M UTC')}")

    all_reviews = []
    seen_ids = set()
    continuation_token = None
    page = 0

    while True:
        page += 1
        batch, continuation_token = reviews(
            app_id,
            lang="en",
            country="in",
            sort=Sort.NEWEST,
            count=BATCH_SIZE,
            continuation_token=continuation_token,
        )

        if not batch:
            break

        # Filter to date window and deduplicate
        stop_early = False
        for r in batch:
            review_time = r["at"]
            # Make timezone-aware if needed
            if review_time.tzinfo is None:
                review_time = review_time.replace(tzinfo=timezone.utc)

            if review_time < cutoff_dt:
                stop_early = True
                break  # Reviews are sorted newest-first; stop here

            rid = r["reviewId"]
            if rid in seen_ids:
                continue
            
            review_text = (r["content"] or "").strip()
            if not is_valid_review(review_text):
                continue

            seen_ids.add(rid)

            all_reviews.append({
                "review_id":       rid,
                "timestamp":       review_time.isoformat(),
                "date":            review_time.strftime("%Y-%m-%d"),
                "rating":          r["score"],
                "review_text":     review_text,
                "thumbs_up_count": r.get("thumbsUpCount", 0),
                "reviewer_name":   (r.get("userName") or "Anonymous").strip(),
            })

        print(f"   Page {page:>3} | Collected so far: {len(all_reviews):>5} reviews", end="\r")

        if stop_early or continuation_token is None:
            break

    print()  # newline after the \r progress line

    if not all_reviews:
        print("⚠️  No reviews found for the specified period.")
        return {"csv_path": None, "row_count": 0, "date_range": {}}

    # ── Build DataFrame ───────────────────────────────────────────────────────
    df = pd.DataFrame(all_reviews)
    df.sort_values("timestamp", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ── Save CSV ──────────────────────────────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    csv_filename = f"reviews_{today_str}.csv"
    csv_path = DATA_DIR / csv_filename
    df.to_csv(csv_path, index=False, encoding="utf-8")

    # ── Summary ───────────────────────────────────────────────────────────────
    date_range = {
        "from": df["date"].min(),
        "to":   df["date"].max(),
    }
    avg_rating = round(df["rating"].mean(), 2)

    print(f"\n✅ Scraped   : {len(df)} reviews")
    print(f"   Date range : {date_range['from']} → {date_range['to']}")
    print(f"   Avg rating : {avg_rating} ⭐")
    print(f"   Saved to   : {csv_path}")

    return {
        "csv_path":   str(csv_path),
        "csv_filename": csv_filename,
        "row_count":  len(df),
        "avg_rating": avg_rating,
        "date_range": date_range,
    }


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape Google Play Store reviews for the Groww app."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("DEFAULT_DAYS", "7")),
        help="Number of past days to scrape (default: 7)",
    )
    parser.add_argument(
        "--app-id",
        type=str,
        default=DEFAULT_APP_ID,
        help=f"Google Play app ID (default: {DEFAULT_APP_ID})",
    )
    args = parser.parse_args()

    if args.days < 1 or args.days > 365:
        print("❌ --days must be between 1 and 365.")
        sys.exit(1)

    result = scrape_reviews(days=args.days, app_id=args.app_id)
    if result["row_count"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
