// app.js — Phase 4 Frontend Logic (V4 SaaS Redesign)

const BASE_URL = ""; // Empty string for relative pathing on Render/Localhost

// DOM Elements
const daysInput = document.getElementById('days-input');
const daysVal = document.getElementById('days-val'); 
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
    if (isError) {
        statusBar.classList.replace('text-emerald-500', 'text-red-400');
        statusBar.classList.replace('border-emerald-500', 'border-red-400');
        statusBar.classList.replace('bg-emerald-500/10', 'bg-red-400/10');
    } else {
        statusBar.classList.add('text-emerald-500', 'border-emerald-500', 'bg-emerald-500/10');
    }
}

function parseNarrativeMarkdown(text) {
    // Premium H3 parsing with Tailwind classes
    return text.replace(/### (.*?)\n/g, '<h3 class="text-xl font-bold text-white mb-4 mt-6 first:mt-0">$1</h3>\n');
}

// ── MAIN ANALYSIS FLOW ───────────────────────────────────────────────────────
runBtn.addEventListener('click', async () => {
    const days = daysInput.value;
    const feeType = feeSelect.value;

    runBtn.disabled = true;
    gdocBtn.disabled = true;
    gmailBtn.disabled = true;
    
    // UI Loading State
    narrativeCard.innerHTML = `
        <div class="flex flex-col items-center justify-center animate-pulse">
            <div class="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-slate-400 font-medium">Crunching executive insights...</p>
        </div>
    `;

    try {
        // Step 1: Scrape
        setStatus(`Scraping reviews for the last ${days} day(s)...`);
        const scrapeRes = await fetch(`${BASE_URL}/scrape?days=${days}`);
        const scrapeData = await scrapeRes.json();
        
        if (!scrapeRes.ok) throw new Error(scrapeData.detail || 'Scraping failed');

        const { csv_filename, row_count } = scrapeData;
        
        // Step 2 & 3 in parallel: AI Analysis & Fee Explainer
        setStatus(`Scraped ${row_count} reviews. Running Intelligence analysis...`);
        
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
        narrativeCard.innerHTML = `<p class="text-red-400 font-bold">${err.message}</p>`;
    } finally {
        runBtn.disabled = false;
    }
});

// ── RENDERERS ────────────────────────────────────────────────────────────────
function renderPulse(report) {
    pulseMeta.textContent = `${report.total_reviews} reviews • Rating: ${report.avg_rating}★`;
    pulseMeta.classList.remove('hidden');
    
    // Remove centered centering for actual report
    narrativeCard.classList.replace('flex', 'block');
    narrativeCard.classList.remove('justify-center', 'items-center', 'text-center');
    narrativeCard.innerHTML = `<div class="prose prose-invert max-w-none text-slate-300">${parseNarrativeMarkdown(report.narrative)}</div>`;
    
    themesGrid.innerHTML = '';
    themesGrid.classList.remove('hidden');
    
    const sortedThemes = Object.entries(report.theme_data)
        .sort((a, b) => b[1].count - a[1].count);

    for (const [theme, data] of sortedThemes) {
        if (data.count === 0) continue;
        
        let domSentiment = "Neutral";
        let maxCount = -1;
        for (const [s, count] of Object.entries(data.sentiment_dist)) {
            if (count > maxCount) { maxCount = count; domSentiment = s; }
        }

        let badgeClass = "bg-slate-500/10 text-slate-400"; // Neutral
        if (domSentiment === "Positive") badgeClass = "bg-emerald-500/10 text-emerald-500";
        if (domSentiment === "Negative") badgeClass = "bg-red-400/10 text-red-400";

        const quotesHtml = data.top_quotes.slice(0, 2).map(q => 
            `<div class="text-xs italic text-slate-500 border-l-2 border-white/5 pl-3 mt-3 py-1 bg-white/5 rounded-r-md">"${q}"</div>`
        ).join('');

        const card = document.createElement('div');
        card.className = 'p-5 bg-slate-900/60 border border-white/10 rounded-2xl hover:border-emerald-500/30 transition-all group';
        card.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h4 class="font-bold text-slate-200 group-hover:text-emerald-500 transition-colors uppercase tracking-tight text-sm">${theme}</h4>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-widest ${badgeClass}">${domSentiment}</span>
            </div>
            <div class="flex items-center space-x-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">
                <span>${data.count} Data Points</span>
                <span>${data.avg_rating}★ Rating</span>
            </div>
            ${quotesHtml}
        `;
        themesGrid.appendChild(card);
    }
}

function renderFee(data) {
    const listHtml = data.bullets.map(b => {
        const parts = b.split(':');
        if (parts.length > 1) {
            return `<li class="flex items-start space-x-2"><span class="text-emerald-500 mt-1">•</span><span><strong class="text-slate-200">${parts[0]}:</strong>${parts.slice(1).join(':')}</span></li>`;
        }
        return `<li class="flex items-start space-x-2"><span class="text-emerald-500 mt-1">•</span><span>${b}</span></li>`;
    }).join('');

    feeCard.classList.remove('flex', 'justify-center', 'items-center', 'text-center');
    feeCard.innerHTML = `
        <h4 class="text-emerald-500 font-black uppercase tracking-widest text-[10px] mb-4">Strategic Matrix: ${data.fee_type}</h4>
        <ul class="space-y-4 text-sm text-slate-400">
            ${listHtml}
        </ul>
        <div class="mt-8 pt-6 border-t border-white/5 space-y-3">
            <div class="text-[10px] font-bold text-slate-600 uppercase tracking-wider">Verification Date: ${data.last_checked}</div>
            <a href="${data.source_url}" target="_blank" class="inline-flex items-center space-x-2 text-xs font-bold text-emerald-500 hover:text-emerald-400 transition-colors">
                <span>SEBI/AMFI Intelligence Source</span>
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
            </a>
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
        modalMsg.textContent = `Pushing Intelligence to executive channel: ${custom}`;
        modalPasswordGroup.classList.remove('hidden');
    } else {
        modalMsg.textContent = "Initiating automated Gmail draft generation via MCP protocol.";
        modalPasswordGroup.classList.add('hidden');
    }
    modalPasswordInput.value = '';
    approvalModal.classList.remove('hidden');
});

gdocBtn.addEventListener('click', () => {
    currentExportAction = 'gdoc';
    modalMsg.textContent = "Appending Product Intelligence to Global Documentation repository.";
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
        setStatus("Matrix Empty. Run analysis first.", true);
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
            setStatus("Syncing with Google Docs repository...");
            const res = await fetch(`${BASE_URL}/export-doc`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Export failed');
            setStatus(`Handshake success (${data.doc_id})`);
            
        } else if (currentExportAction === 'gmail') {
            setStatus("Transmitting Gmail Intelligence...");
            const res = await fetch(`${BASE_URL}/export-email`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Transmission failed');
            setStatus(`Transmission complete (ID: ${data.draft_id})`);
        }
    } catch (err) {
        console.error(err);
        setStatus(`Intel Error: ${err.message}`, true);
    }
});

// ── V4: DASHBOARD UX ────────────────────────────────────────────────────────

// 1. Slider Synchronisation
if (daysInput && daysVal) {
    daysInput.addEventListener('input', (e) => {
        daysVal.textContent = e.target.value;
    });
}

// 2. Theme Toggle (Tailwind Focus)
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark'; // Default to dark for SaaS look
    if (savedTheme === 'light') {
        body.classList.remove('dark-mode');
        body.classList.add('bg-slate-50', 'text-slate-900');
        body.classList.remove('bg-slate-950', 'text-slate-200');
        themeIcon.textContent = '🌙';
    } else {
        body.classList.add('dark-mode');
        themeIcon.textContent = '☀️';
    }
}

themeToggle.addEventListener('click', () => {
    if (body.classList.contains('dark-mode')) {
        body.classList.remove('dark-mode');
        body.classList.replace('bg-slate-950', 'bg-slate-50');
        body.classList.replace('text-slate-200', 'text-slate-900');
        themeIcon.textContent = '🌙';
        localStorage.setItem('theme', 'light');
    } else {
        body.classList.add('dark-mode');
        body.classList.replace('bg-slate-50', 'bg-slate-950');
        body.classList.replace('text-slate-900', 'text-slate-200');
        themeIcon.textContent = '☀️';
        localStorage.setItem('theme', 'dark');
    }
});

initTheme();
