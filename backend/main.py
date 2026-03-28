"""
main.py — FastAPI backend for the GenAI Product Manager Dashboard (Groww)

Phase 1 endpoints:
    GET /health
    GET /scrape?days=7

Phase 2 endpoints:
    POST /analyze?csv_filename=reviews_2026-03-19.csv
"""

import sys
import os
import json
import time
from pathlib import Path

# Allow importing from backend package regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from pydantic import BaseModel

from backend.scraper.play_scraper import scrape_reviews
from backend.ai.classifier import classify_reviews, pulse_engine
from backend.ai.fee_explainer import generate_fee_explanation, FEE_SOURCES
from backend.mcp.gdocs_tool import append_to_doc
from backend.mcp.gmail_tool import create_draft

class ExportData(BaseModel):
    pulse_report: dict
    fee_report: dict
    custom_recipients: str = ""
    custom_export_password: str = ""

# ── App Init ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GenAI Product Pulse API",
    description="Backend for the Groww Review Pulse Dashboard",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tightened in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Phase 1 Endpoints ─────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    """Simple health check."""
    return {"status": "ok", "service": "GenAI Product Pulse API"}


@app.get("/scrape", tags=["Phase 1 — Data Ingestion"])
def scrape(
    days: int = Query(
        default=7,
        ge=1,
        le=365,
        description="Number of past days to scrape reviews for",
    ),
    app_id: str = Query(
        default=os.getenv("GROWW_APP_ID", "com.nextbillion.groww"),
        description="Google Play app ID",
    ),
):
    """
    Scrape Google Play Store reviews for the last `days` days.

    Returns metadata about the scraped CSV file.
    """
    try:
        result = scrape_reviews(days=days, app_id=app_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scraper error: {str(exc)}")

    if result["row_count"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No reviews found for the last {days} day(s).",
        )

    return {
        "status":       "success",
        "csv_path":     result["csv_path"],
        "csv_filename": result["csv_filename"],
        "row_count":    result["row_count"],
        "avg_rating":   result["avg_rating"],
        "date_range":   result["date_range"],
        "days_scraped": days,
    }


# ── Phase 2 Endpoints ─────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


CACHE_EXPIRY_MINUTES = int(os.getenv("CACHE_EXPIRY_MINUTES", "60"))

@app.post("/analyze", tags=["Phase 2 — AI Classification"])
def analyze(
    csv_filename: str = Query(
        description="CSV filename from /scrape (e.g. reviews_2026-03-19.csv)"
    ),
):
    """
    Classify reviews + generate Weekly Product Pulse.
    """
    csv_path = DATA_DIR / csv_filename
    if not csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"CSV not found: {csv_filename}. Run /scrape first.",
        )

    try:
        classify_result = classify_reviews(str(csv_path))
        report = pulse_engine(classify_result)
    except KeyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variable: {exc}. Is GEMINI_API_KEY set?",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(exc)}")

    # Remove the internal DataFrame before serialising
    report.pop("dataframe", None)
    classify_result.pop("dataframe", None)

    # Save to cache
    latest_pulse_path = DATA_DIR / "latest_pulse.json"
    with open(latest_pulse_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return {
        "status":      "success",
        "pulse_report": report,
    }


@app.get("/dashboard-data", tags=["Dashboard"])
def get_dashboard_data(
    days: int = Query(default=7, ge=1, le=365),
    app_id: str = Query(default=os.getenv("GROWW_APP_ID", "com.nextbillion.groww")),
):
    """
    Get the latest Product Pulse Report. 
    Uses cached data if it's less than CACHE_EXPIRY_MINUTES old.
    Otherwise, scrapes and analyzes fresh data.
    """
    latest_pulse_path = DATA_DIR / "latest_pulse.json"
    
    if latest_pulse_path.exists():
        file_age_seconds = time.time() - os.path.getmtime(latest_pulse_path)
        if file_age_seconds < (CACHE_EXPIRY_MINUTES * 60):
            try:
                with open(latest_pulse_path, "r", encoding="utf-8") as f:
                    report = json.load(f)
                return {
                    "status": "success",
                    "cached": True,
                    "pulse_report": report,
                }
            except Exception:
                pass # Fallback to refresh if cache is corrupted

    # Cache missed or expired -> Refresh data
    try:
        scrape_res = scrape_reviews(days=days, app_id=app_id)
        if scrape_res["row_count"] == 0:
            raise HTTPException(status_code=404, detail="No reviews found to analyze.")
            
        classify_result = classify_reviews(str(scrape_res["csv_path"]))
        report = pulse_engine(classify_result)
        
        report.pop("dataframe", None)
        
        with open(latest_pulse_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            
        return {
            "status": "success",
            "cached": False,
            "pulse_report": report,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generating dashboard data: {str(exc)}")



# ── Phase 3 Endpoints ─────────────────────────────────────────────────────────

@app.post("/fee-explain", tags=["Phase 3 — Fee Explainer"])
def fee_explain(
    fee_type: str = Query(
        description=f"Fee type from dropdown. Must be one of: {list(FEE_SOURCES.keys())}"
    )
):
    """
    Generate a 6-bullet explanation for a selected mutual fund fee structure.
    Returns: {"bullets": [...], "source_url": "...", "last_checked": "..."}
    """
    try:
        explanation = generate_fee_explanation(fee_type)
        return {"status": "success", "data": explanation}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating explanation: {str(exc)}"
        )


# ── Phase 5 Endpoints ─────────────────────────────────────────────────────────

def _build_export_text(data: ExportData) -> str:
    """Helper to combine the pulse narrative and the fee explainer into one text body."""
    text = data.pulse_report.get("narrative", "")
    text += "\n\n" + "-"*40 + "\n"
    text += f"### Fee Structure Explainer: {data.fee_report.get('fee_type', '')}\n"
    for bullet in data.fee_report.get("bullets", []):
        text += f"- {bullet}\n"
    text += f"\nSource verification: {data.fee_report.get('source_url', '')} (As of {data.fee_report.get('last_checked', '')})"
    return text


@app.post("/export-doc", tags=["Phase 5 — Google Docs Export"])
def export_doc(data: ExportData):
    try:
        doc_id = os.getenv("GOOGLE_DOC_ID")
        if not doc_id:
            raise ValueError("GOOGLE_DOC_ID not set in .env")
            
        title = "Groww App: Weekly Product Pulse"
        narrative = _build_export_text(data)

        result = append_to_doc(doc_id, title, narrative)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/export-email", tags=["Phase 5 — Gmail Export"])
def export_email(data: ExportData):
    try:
        # 1. Determine recipients
        default_recipient = os.getenv("GMAIL_DRAFT_RECIPIENT")
        
        if data.custom_recipients and data.custom_recipients.strip():
            # Auth Check for custom recipients
            required_pass = os.getenv("CUSTOM_EXPORT_PASSWORD")
            if not required_pass:
                raise HTTPException(status_code=500, detail="Server Error: CUSTOM_EXPORT_PASSWORD not configured.")
            
            if data.custom_export_password != required_pass:
                raise HTTPException(status_code=401, detail="Unauthorized: Incorrect Custom Export Password.")
            
            recipient = data.custom_recipients
        else:
            # No custom recipient -> Use default (no password required)
            recipient = default_recipient
            if not recipient:
                raise ValueError("GMAIL_DRAFT_RECIPIENT not set in .env")

        # 2. Prepare email
        subject = os.getenv("GMAIL_DRAFT_SUBJECT", "Weekly Product Pulse — Groww")
        body = _build_export_text(data)

        # 3. Export
        result = create_draft(recipient, subject, body)
        return result
    except HTTPException as he:
        raise he
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Serve Frontend (Phase 4) ──────────────────────────────────────────────────────
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(str(frontend_dir / "index.html"))
