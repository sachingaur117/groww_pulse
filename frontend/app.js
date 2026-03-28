// app.js — Phase 4 Frontend Logic (V2 Enterprise)

const BASE_URL = ""; // Empty string for relative pathing on Render/Localhost

// DOM Elements
const daysInput = document.getElementById('days-input');
const daysVal = document.getElementById('days-val'); // Slider display
const feeSelect = document.getElementById('fee-select');
const runBtn = document.getElementById('run-btn');
const statusBar = document.getElementById('status-bar');

const themeToggle = document.getElementById('theme-toggle');
const themeIcon = document.getElementById('theme-icon');
const body = document.body;

const narrativeCard = document.getElementById('narrative-card');
const themesGrid = document.getElementById('themes-grid');
const pulseMeta = document.getElementById('pulse-meta');
const feeCard = document.getElementById('fee-card');

const gdocBtn = document.getElementById('export-gdoc-btn');
const gmailBtn = document.getElementById('export-gmail-btn');

const customRecipientsInput = document.getElementById('custom-recipients');
const modalPasswordInput = document.getElementById('modal-password');
const modalPasswordGroup = document.getElementById('modal-password-group');

// State holding exportable data
let lastPulseReport = null;
let lastFeeReport = null;

// ── UTILS ────────────────────────────────────────────────────────────────────
function setStatus(msg, isError = false) {
    statusBar.textContent = msg;
    statusBar.classList.remove('hidden');
    statusBar.style.borderLeftColor = isError ? 'var(--accent)' : 'var(--primary)';
}

function parseNarrativeMarkdown(text) {
    // Basic Markdown H3 parsing for the UI
    return text.replace(/### (.*?)\n/g, '<h3>$1</h3>\n');
}

// ── MAIN ANALYSIS FLOW ───────────────────────────────────────────────────────
runBtn.addEventListener('click', async () => {
    const days = daysInput.value;
    const feeType = feeSelect.value;

    runBtn.disabled = true;
    gdocBtn.disabled = true;
    gmailBtn.disabled = true;

    try {
        // Step 1: Scrape
        setStatus(`Scraping reviews for the last ${days} day(s)...`);
        const scrapeRes = await fetch(`${BASE_URL}/scrape?days=${days}`);
        const scrapeData = await scrapeRes.json();
        
        if (!scrapeRes.ok) throw new Error(scrapeData.detail || 'Scraping failed');

        const { csv_filename, row_count } = scrapeData;
        
        // Step 2 & 3 in parallel: AI Analysis & Fee Explainer
        setStatus(`Scraped ${row_count} reviews. Running Gemini analysis...`);
        
        const [analyzeRes, feeRes] = await Promise.all([
            fetch(`${BASE_URL}/analyze?csv_filename=${csv_filename}`, { method: 'POST' }),
            fetch(`${BASE_URL}/fee-explain?fee_type=${encodeURIComponent(feeType)}`, { method: 'POST' })
        ]);

        const analyzeData = await analyzeRes.json();
        const feeData = await feeRes.json();

        if (!analyzeRes.ok) throw new Error(analyzeData.detail || 'Analysis failed');
        if (!feeRes.ok) throw new Error(feeData.detail || 'Fee explanation failed');

        // Render UI
        renderPulse(analyzeData.pulse_report);
        renderFee(feeData.data);
        
        // Enable exports
        lastPulseReport = analyzeData.pulse_report;
        lastFeeReport = feeData.data;
        gdocBtn.disabled = false;
        gmailBtn.disabled = false;

        setStatus(`Analysis complete! Ready for Review & Export.`);
        
    } catch (err) {
        console.error(err);
        setStatus(err.message, true);
    } finally {
        runBtn.disabled = false;
    }
});

// ── RENDERERS ────────────────────────────────────────────────────────────────
function renderPulse(report) {
    pulseMeta.textContent = `${report.total_reviews} reviews analyzed • Growth Rating: ${report.avg_rating}`;
    pulseMeta.classList.remove('hidden');
    
    narrativeCard.innerHTML = parseNarrativeMarkdown(report.narrative);
    
    themesGrid.innerHTML = '';
    themesGrid.classList.remove('hidden');
    
    // Sort themes by volume
    const sortedThemes = Object.entries(report.theme_data)
        .sort((a, b) => b[1].count - a[1].count);

    for (const [theme, data] of sortedThemes) {
        if (data.count === 0) continue;
        
        let domSentiment = "Neutral";
        let maxCount = -1;
        for (const [s, count] of Object.entries(data.sentiment_dist)) {
            if (count > maxCount) { maxCount = count; domSentiment = s; }
        }

        const sentimentClass = `sentiment-${domSentiment.toLowerCase()}`;
        const quotesHtml = data.top_quotes.slice(0, 2).map(q => `<div class="quote">"${q}"</div>`).join('');

        const card = document.createElement('div');
        card.className = 'theme-card';
        card.innerHTML = `
            <div class="theme-label">
                <h4>${theme}</h4>
                <span class="sentiment-badge ${sentimentClass}">${domSentiment}</span>
            </div>
            <div class="theme-meta">
                <span>${data.count} reviews</span>
                <span>${data.avg_rating} Avg. Rating</span>
            </div>
            ${quotesHtml}
        `;
        themesGrid.appendChild(card);
    }
}

function renderFee(data) {
    const listHtml = data.bullets.map(b => {
        // Highlight the bold keys like "1. What it is:"
        const parts = b.split(':');
        if (parts.length > 1) {
            return `<li><strong>${parts[0]}:</strong>${parts.slice(1).join(':')}</li>`;
        }
        return `<li>${b}</li>`;
    }).join('');

    feeCard.innerHTML = `
        <h3 style="color:var(--primary); margin-bottom:1rem;">${data.fee_type}</h3>
        <ul class="fee-list">
            ${listHtml}
        </ul>
        <div style="margin-top:1.5rem; border-top:1px solid var(--border); padding-top:1rem;">
            <div style="font-size:0.8rem; color:var(--text-dim);">Last verified: ${data.last_checked}</div>
            <a href="${data.source_url}" target="_blank" class="source-link">View official SEBI/AMFI source ↗</a>
        </div>
    `;
}

// ── EXPORT MODAL ─────────────────────────────────────────────────────────────
const approvalModal = document.getElementById('approval-modal');
const modalCancel = document.getElementById('modal-cancel');
const modalConfirm = document.getElementById('modal-confirm');
const modalMsg = document.getElementById('modal-msg');

let currentExportAction = null;

gmailBtn.addEventListener('click', () => {
    currentExportAction = 'gmail';
    const custom = customRecipientsInput.value.trim();
    if (custom) {
        modalMsg.textContent = `Send analysis to custom recipients: ${custom}?`;
        modalPasswordGroup.classList.remove('hidden');
    } else {
        modalMsg.textContent = "Create a draft in Gmail with full analysis via MCP tool?";
        modalPasswordGroup.classList.add('hidden');
    }
    modalPasswordInput.value = '';
    approvalModal.classList.remove('hidden');
});

gdocBtn.addEventListener('click', () => {
    currentExportAction = 'gdoc';
    modalMsg.textContent = "Append 'Weekly Product Pulse' to Google Doc via MCP tool?";
    modalPasswordGroup.classList.add('hidden');
    approvalModal.classList.remove('hidden');
});

modalCancel.addEventListener('click', () => {
    approvalModal.classList.add('hidden');
    currentExportAction = null;
});

modalConfirm.addEventListener('click', async () => {
    approvalModal.classList.add('hidden');
    
    if (!lastPulseReport || !lastFeeReport) {
        setStatus("No data to export. Run analysis first.", true);
        return;
    }
    
    const payload = {
        pulse_report: lastPulseReport,
        fee_report: lastFeeReport,
        custom_recipients: customRecipientsInput.value.trim(),
        custom_export_password: modalPasswordInput.value
    };

    try {
        if (currentExportAction === 'gdoc') {
            setStatus("Exporting to Google Docs...");
            const res = await fetch(`${BASE_URL}/export-doc`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Export failed');
            setStatus(`Successfully appended to Google Doc (${data.doc_id})`);
            
        } else if (currentExportAction === 'gmail') {
            setStatus("Creating Gmail Draft...");
            const res = await fetch(`${BASE_URL}/export-email`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Draft creation failed');
            setStatus(`Gmail draft created (ID: ${data.draft_id})`);
        }
    } catch (err) {
        console.error(err);
        setStatus(`Export Error: ${err.message}`, true);
    }
});

// ── V2: DASHBOARD LOGIC ──────────────────────────────────────────────────────

// 1. Slider Synchronisation
if (daysInput && daysVal) {
    daysInput.addEventListener('input', (e) => {
        daysVal.textContent = e.target.value;
    });
}

// 2. Dark Mode Toggle
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
        body.classList.replace('light-mode', 'dark-mode');
        themeIcon.textContent = '☀️';
    }
}

themeToggle.addEventListener('click', () => {
    if (body.classList.contains('light-mode')) {
        body.classList.replace('light-mode', 'dark-mode');
        themeIcon.textContent = '☀️';
        localStorage.setItem('theme', 'dark');
    } else {
        body.classList.replace('dark-mode', 'light-mode');
        themeIcon.textContent = '🌙';
        localStorage.setItem('theme', 'light');
    }
});

initTheme();
