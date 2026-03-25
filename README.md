# GenAI Product Manager Dashboard — Groww

A multi-phase AI-powered dashboard to analyze Google Play Store reviews for the Groww investment app and generate a Weekly Product Pulse report.

---

## Stack

| Layer | Tech |
|---|---|
| Scraper | `google-play-scraper` (Python) |
| AI | Gemini (`gemini-2.0-flash`) via `google-generativeai` |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (Groww-inspired) |
| Integrations | MCP — Google Docs + Gmail |

---

## Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Data Ingestion & Scraper | ✅ Done |
| 2 | AI Classification & Pulse Engine | ⏳ Pending |
| 3 | Fee Explainer Logic | ⏳ Pending |
| 4 | UI Development | ⏳ Pending |
| 5 | MCP Integration (Docs + Gmail) | ⏳ Pending |

---

## Setup

```bash
# 1. Clone & enter project
cd Nextleap_reviews_pulse

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY and Google OAuth credentials
```

---

## Phase 1 — Running the Scraper

### CLI
```bash
# Scrape last 7 days (default)
python backend/scraper/play_scraper.py --days 7

# Scrape last 30 days
python backend/scraper/play_scraper.py --days 30
```

Output: `data/reviews_YYYY-MM-DD.csv`

### API Server
```bash
uvicorn backend.main:app --reload --port 8000
```

Endpoints:
- `GET /health` — Health check
- `GET /scrape?days=7` — Run scraper, returns JSON with CSV metadata
- `GET /docs` — FastAPI interactive docs (Swagger UI)

---

## Project Structure

```
Nextleap_reviews_pulse/
├── backend/
│   ├── scraper/
│   │   ├── __init__.py
│   │   └── play_scraper.py
│   ├── ai/                    # Phase 2 & 3
│   ├── mcp/                   # Phase 5
│   ├── __init__.py
│   └── main.py
├── frontend/                  # Phase 4
├── data/                      # CSV outputs
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```
