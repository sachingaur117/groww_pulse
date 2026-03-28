// app.js — Phase 4.4 UX Refinement

const BASE_URL = ""; 

// DOM Elements
const daysInput = document.getElementById('days-input');
const daysVal = document.getElementById('days-val'); 
const feeSelect = document.getElementById('fee-select');
const runBtn = document.getElementById('run-btn');
const statusBar = document.getElementById('status-bar');

const body = document.body;

const narrativeCard = document.getElementById('narrative-card');
const themesGrid = document.getElementById('themes-grid');
const pulseMeta = document.getElementById('pulse-meta');
const feeCard = document.getElementById('fee-card');

// Workflow Elements
const exportPanel = document.getElementById('export-panel');
const gdocBtn = document.getElementById('export-gdoc-btn');
const gmailBtn = document.getElementById('export-gmail-btn');
const customRecipientsInput = document.getElementById('custom-recipients');

const modalPasswordInput = document.getElementById('modal-password');
const modalPasswordGroup = document.getElementById('modal-password-group');

// State
let lastPulseReport = null;
let lastFeeReport = null;

// ── UTILS ────────────────────────────────────────────────────────────────────
function setStatus(msg, isError = false) {
    statusBar.textContent = msg;
    statusBar.classList.remove('hidden');
    if (isError) {
        statusBar.className = "px-6 py-4 bg-red-400/10 border-l-4 border-red-400 text-red-400 rounded-r-xl text-[10px] font-black uppercase tracking-widest animate-pulse";
    } else {
        statusBar.className = "px-6 py-4 bg-emerald-500/10 border-l-4 border-emerald-500 text-emerald-500 rounded-r-xl text-[10px] font-black uppercase tracking-widest animate-pulse";
    }
}

function parseNarrativeMarkdown(text) {
    // Premium headers for pulse overview
    return text.replace(/### (.*?)\n/g, '<h3 class="text-xs font-black text-emerald-500 mb-3 mt-8 first:mt-0 uppercase tracking-[0.3em] border-b border-emerald-500/10 pb-2">$1</h3>\n');
}

function unlockExportPanel() {
    // Enable input
    customRecipientsInput.disabled = false;
    customRecipientsInput.classList.remove('opacity-50');
    
    // Enable Docs Button
    gdocBtn.disabled = false;
    gdocBtn.classList.remove('bg-slate-800/40', 'text-slate-600', 'cursor-not-allowed');
    gdocBtn.classList.add('bg-slate-800', 'hover:bg-slate-700', 'text-white', 'cursor-pointer');
    gdocBtn.querySelector('svg').classList.remove('opacity-40');
    
    // Enable Gmail Button
    gmailBtn.disabled = false;
    gmailBtn.classList.remove('bg-slate-800/40', 'text-slate-600', 'cursor-not-allowed');
    gmailBtn.classList.add('bg-slate-800', 'hover:bg-slate-700', 'text-white', 'cursor-pointer');
    gmailBtn.querySelector('svg').classList.remove('opacity-40');
}

function lockExportPanel() {
    // Disable input
    customRecipientsInput.disabled = true;
    customRecipientsInput.classList.add('opacity-50');

    // Disable Docs Button
    gdocBtn.disabled = true;
    gdocBtn.classList.add('bg-slate-800/40', 'text-slate-600', 'cursor-not-allowed');
    gdocBtn.classList.remove('bg-slate-800', 'hover:bg-slate-700', 'text-white', 'cursor-pointer');
    gdocBtn.querySelector('svg').classList.add('opacity-40');
    
    // Disable Gmail Button
    gmailBtn.disabled = true;
    gmailBtn.classList.add('bg-slate-800/40', 'text-slate-600', 'cursor-not-allowed');
    gmailBtn.classList.remove('bg-slate-800', 'hover:bg-slate-700', 'text-white', 'cursor-pointer');
    gmailBtn.querySelector('svg').classList.add('opacity-40');
}

// ── MAIN ANALYSIS FLOW ───────────────────────────────────────────────────────
runBtn.addEventListener('click', async () => {
    const days = daysInput.value;
    const feeType = feeSelect.value;

    runBtn.disabled = true;
    lockExportPanel();
    
    // UI Loading State
    narrativeCard.innerHTML = `
        <div class="flex flex-col items-center justify-center animate-pulse">
            <div class="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Analyzing Data...</p>
        </div>
    `;
    feeCard.innerHTML = `
        <div class="flex flex-col items-center justify-center animate-pulse">
            <div class="w-12 h-12 border-4 border-slate-700 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
            <p class="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Loading Insights...</p>
        </div>
    `;

    try {
        setStatus(`Scraping ${days}-day data...`);
        const scrapeRes = await fetch(`${BASE_URL}/scrape?days=${days}`);
        const scrapeData = await scrapeRes.json();
        
        if (!scrapeRes.ok) throw new Error(scrapeData.detail || 'Scraping failed');

        const { csv_filename, row_count } = scrapeData;
        
        setStatus(`Classifying ${row_count} reviews using Gemini AI...`);
        
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
        
        // Success: Unlock Workflow
        lastPulseReport = analyzeData.pulse_report;
        lastFeeReport = feeData.data;
        unlockExportPanel();

        setStatus(`Analysis Ready. Report available for export.`);
        
    } catch (err) {
        console.error(err);
        setStatus(`System Error: ${err.message}`, true);
        narrativeCard.innerHTML = `<p class="text-red-400 font-black p-4 text-center text-[10px] tracking-widest uppercase">${err.message}</p>`;
    } finally {
        runBtn.disabled = false;
    }
});

// ── RENDERERS ────────────────────────────────────────────────────────────────
function renderPulse(report) {
    narrativeCard.classList.replace('flex', 'block');
    narrativeCard.classList.remove('justify-center', 'items-center', 'text-center');
    // Ensure padding/size matches user preference
    narrativeCard.className = "p-10 bg-slate-900 border border-white/10 rounded-2xl min-h-[300px] text-left mb-6 transition-all duration-500";
    
    narrativeCard.innerHTML = `
        <div class="prose prose-invert max-w-none text-slate-300 text-sm md:text-base leading-relaxed font-medium">
            ${parseNarrativeMarkdown(report.narrative)}
        </div>
    `;
    
    pulseMeta.classList.remove('hidden');
    themesGrid.innerHTML = '';
    themesGrid.classList.remove('hidden'); // Ensure visible
    
    // Convert theme_data to array and filter + sort
    const sortedThemes = Object.entries(report.theme_data || {})
        .filter(([_, data]) => data.count > 0)
        .sort((a, b) => b[1].count - a[1].count);

    if (sortedThemes.length === 0) {
        themesGrid.classList.add('hidden');
    }

    for (const [theme, data] of sortedThemes) {
        let domSentiment = "Neutral";
        let maxCount = -1;
        for (const [sentiment, count] of Object.entries(data.sentiment_dist)) {
            if (count > maxCount) { maxCount = count; domSentiment = sentiment; }
        }

        let badgeClass = "bg-slate-500/10 text-slate-400";
        if (domSentiment === "positive" || domSentiment === "Positive") badgeClass = "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20";
        if (domSentiment === "negative" || domSentiment === "Negative") badgeClass = "bg-red-400/10 text-red-400 border border-red-400/20";

        const quotesHtml = data.top_quotes.slice(0, 2).map(q => 
            `<div class="text-[11px] italic text-slate-400 border-l-2 border-emerald-500/30 pl-3 mt-3 py-1.5 bg-white/5 rounded-r-lg leading-relaxed truncate hover:whitespace-normal transition-all duration-300">"${q}"</div>`
        ).join('');

        const card = document.createElement('div');
        card.className = 'p-6 bg-slate-950/50 border border-white/5 rounded-2xl hover:border-emerald-500/30 transition-all group animate-in fade-in slide-in-from-bottom-2 duration-500';
        card.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <h4 class="font-black text-slate-100 group-hover:text-emerald-500 transition-colors uppercase tracking-widest text-xs">${theme}</h4>
                <span class="px-2.5 py-1 rounded-md text-[9px] font-black uppercase tracking-[0.2em] ${badgeClass}">${domSentiment}</span>
            </div>
            <div class="flex items-center space-x-4 text-[10px] font-black text-slate-600 uppercase tracking-widest mb-3 border-b border-white/5 pb-2">
                <span class="flex items-center"><svg class="w-3 h-3 mr-1 text-slate-700" fill="currentColor" viewBox="0 0 24 24"><path d="M7 10l5 5 5-5H7z"/></svg> ${data.count} Reviews</span>
                <span class="flex items-center"><svg class="w-3 h-3 mr-1 text-slate-700" fill="currentColor" viewBox="0 0 24 24"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg> ${data.avg_rating}★</span>
            </div>
            ${quotesHtml}
        `;
        themesGrid.appendChild(card);
    }
}

function renderFee(data) {
    // 3 bullets only for V4.4
    const listHtml = data.bullets.slice(0, 3).map(b => {
        const parts = b.split(':');
        if (parts.length > 1) {
            return `
                <li class="flex items-start space-x-4 group">
                    <span class="text-emerald-500 mt-1.5 flex-shrink-0">
                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                    </span>
                    <span class="leading-relaxed">
                        <strong class="text-slate-100 font-black uppercase tracking-[0.2em] text-[10px] block mb-1">${parts[0]}</strong>
                        <span class="block text-slate-400">${parts.slice(1).join(':')}</span>
                    </span>
                </li>`;
        }
        return `
            <li class="flex items-start space-x-4">
                <span class="text-emerald-500 mt-1.5">•</span>
                <span class="text-slate-400">${b}</span>
            </li>`;
    }).join('');

    feeCard.classList.remove('flex', 'justify-center', 'items-center', 'text-center');
    // Shorter card for V4.4
    feeCard.className = "p-10 bg-slate-900 border border-white/10 rounded-2xl min-h-[250px] text-left transition-all duration-500";
    feeCard.innerHTML = `
        <div class="flex items-center justify-between mb-8 border-b border-white/5 pb-4">
            <h4 class="text-emerald-500 font-black uppercase tracking-[0.3em] text-[11px]">${data.fee_type} Insights</h4>
            <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-glow shadow-emerald-500/50"></div>
        </div>
        <ul class="space-y-6 text-sm text-slate-300 font-medium">
            ${listHtml}
        </ul>
        <div class="mt-10 pt-6 border-t border-white/5 flex items-center justify-between">
            <div class="text-[10px] font-black text-slate-700 uppercase tracking-widest italic">Checked: ${data.last_checked}</div>
            <a href="${data.source_url}" target="_blank" class="flex items-center space-x-2 text-[9px] font-black text-emerald-500 hover:text-emerald-400 shadow-glow shadow-emerald-500/10 transition-colors uppercase tracking-widest bg-emerald-500/5 px-3 py-1.5 rounded-lg border border-emerald-500/10">
                Official Source
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
        modalMsg.textContent = `TARGETING CHANNEL: ${custom}`;
        modalPasswordGroup.classList.remove('hidden');
    } else {
        modalMsg.textContent = "ORCHESTRATING GMAIL DRAFT INJECTION.";
        modalPasswordGroup.classList.add('hidden');
    }
    modalPasswordInput.value = '';
    approvalModal.classList.remove('hidden');
});

gdocBtn.addEventListener('click', () => {
    currentExportAction = 'gdoc';
    modalMsg.textContent = "COMMITTING INTELLIGENCE TO CLOUD REPOSITORY.";
    modalPasswordGroup.classList.add('hidden');
    approvalModal.classList.remove('hidden');
});

modalCancel.addEventListener('click', () => {
    approvalModal.classList.add('hidden');
    currentExportAction = null;
});

modalConfirm.addEventListener('click', async () => {
    approvalModal.classList.add('hidden');
    
    const payload = {
        pulse_report: lastPulseReport,
        fee_report: lastFeeReport,
        custom_recipients: customRecipientsInput.value.trim(),
        custom_export_password: modalPasswordInput.value
    };

    try {
        if (currentExportAction === 'gdoc') {
            setStatus("Syncing with Docs...");
            const res = await fetch(`${BASE_URL}/export-doc`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Sync failed');
            setStatus(`Data Sync Complete: ${data.doc_id}`);
            
        } else if (currentExportAction === 'gmail') {
            setStatus("Preparing Gmail Draft...");
            const res = await fetch(`${BASE_URL}/export-email`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Broadcast failed');
            setStatus(`Draft Prepared: ${data.draft_id}`);
        }
    } catch (err) {
        console.error(err);
        setStatus(`Export Error: ${err.message}`, true);
    }
});

// ── V4.4 INIT ─────────────────────────────────────────────────────────────

if (daysInput && daysVal) {
    daysInput.addEventListener('input', (e) => {
        daysVal.innerHTML = `${e.target.value} <span class="text-[10px] text-slate-600 uppercase">Days</span>`;
    });
}

document.documentElement.classList.add('dark');
body.classList.add('dark-mode');
console.log("Intelligence Interface V4.4 Live (Human-Centric UX Protocols)");
