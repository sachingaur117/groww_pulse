"""
fee_explainer.py — Phase 3: Fee Explainer Logic

Generates neutral, factual, 6-bullet explanations for mutual fund fees.
Returns JSON with bullets, a predefined realistic source URL, and last checked date.
"""

import json
import os
from datetime import datetime

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

# Factual source mappings (simulating a database/config lookup)
FEE_SOURCES = {
    "Exit Load": "https://www.amfiindia.com/investor-corner/knowledge-center/exit-load.html",
    "Expense Ratio / AMC Fee": "https://www.sebi.gov.in/legal/circulars/oct-2018/total-expense-ratio-ter-and-performance-disclosure-for-mutual-funds_40769.html",
    "STT (Securities Transaction Tax)": "https://incometaxindia.gov.in/Pages/acts/securities-transaction-tax.aspx",
    "Stamp Duty": "https://www.amfiindia.com/investor-corner/knowledge-center/stamp-duty-on-mutual-fund.html",
    "Capital Gains Tax (STCG/LTCG)": "https://incometaxindia.gov.in/tutorials/15-%20stcg.pdf",
    "TDS on Dividends": "https://incometaxindia.gov.in/tutorials/24.%20tds%20on%20dividend.pdf",
}

FEE_SYSTEM_PROMPT = """You are a SEBI-registered financial content writer.
Provide a strictly factual, neutral, and non-advisory explanation for the requested mutual fund fee or tax.

You MUST format your response as exactly 3 concise, factual bullet points. Each bullet must be a single, short sentence.
1. What it is
2. How it's calculated
3. Key impact / when it applies

Output plain text list with 6 items. Do not use markdown bullet symbols (- or •), prefix each with the number like "1. What it is: ...".
"""


def generate_fee_explanation(fee_type: str) -> dict:
    """
    Generate a 6-bullet explanation for a valid fee type using Gemini.
    """
    if fee_type not in FEE_SOURCES:
        raise ValueError(f"Unknown fee type: {fee_type}")

    client = genai.GenerativeModel(MODEL)
    prompt = f"Explain this fee: {fee_type}"

    response = client.generate_content(
        [FEE_SYSTEM_PROMPT, prompt],
        generation_config=genai.GenerationConfig(temperature=0.1)
    )

    text = response.text.strip()
    
    # Parse the text into a clean list of 6 strings
    bullets = []
    for line in text.split('\n'):
        line = line.strip()
        # Accept lines that start with a number followed by a dot
        if line and line[0].isdigit() and ('. ' in line[:4] or ') ' in line[:4]):
            bullets.append(line)

    # Fallback if the model hallucinated the format
    if len(bullets) < 4:
        # Just split by newline if numbering failed
        bullets = [b.strip() for b in text.split('\n') if b.strip()][:6]

    return {
        "fee_type": fee_type,
        "bullets": bullets,
        "source_url": FEE_SOURCES[fee_type],
        "last_checked": datetime.now().strftime("%Y-%m-%d"),
    }
