import sys
import os
import json
from pathlib import Path

# Fix python import path to see backend package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.scraper.play_scraper import scrape_reviews
from backend.ai.classifier import classify_reviews, pulse_engine

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def main():
    print("🚀 Starting Weekly Review Pulse Generation...")
    try:
        # 1. Scrape the last 7 days
        scrape_res = scrape_reviews(days=7)
        if scrape_res["row_count"] == 0:
            print("No reviews found for last 7 days.")
            sys.exit(0)
        
        # 2. Add AI analysis
        classify_res = classify_reviews(str(scrape_res["csv_path"]))
        report = pulse_engine(classify_res)
        
        # 3. Save JSON Report locally
        report.pop("dataframe", None)
        latest_pulse_path = DATA_DIR / "latest_pulse.json"
        with open(latest_pulse_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            
        print("✅ Successfully generated Pulse Report:")
        print("--------------------------------------------------")
        print(report["narrative"])
        print("--------------------------------------------------")
        
        # Optional: Export to Google Docs or Draft Gmail via your MCP tools:
        # from backend.mcp.gmail_tool import create_draft
        # create_draft(
        #     recipient=os.getenv("GMAIL_DRAFT_RECIPIENT", "product-team@groww.in"),
        #     subject="Weekly Product Pulse — Groww",
        #     body=report["narrative"]
        # )

    except Exception as e:
        print(f"❌ Error during weekly job: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
