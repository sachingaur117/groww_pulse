// app.js — Phase 4.6 Bug Fixes & UX Cleanup

const BASE_URL = ""; 

// DOM Elements
const daysInput = document.getElementById('days-input');
const daysVal = document.getElementById('days-val'); 
const feeSelect = document.getElementById('fee-select');
const runBtn = document.getElementById('run-btn');
const statusBar = document.getElementById('status-bar');

const body = document.body;

const pulseContainer = document.getElementById('pulse-container');
const narrativeCard = document.getElementById('narrative-card');
const pulseMeta = document.getElementById('pulse-meta');
const feeCard = document.getElementById('fee-card');

// Workflow Elements
const gdocBtn = document.getElementById('export-gdoc-btn');
const gmailBtn = document.getElementById('export-gmail-btn');
const customRecipientsInput = document.getElementById('custom-recipients');

const modalPasswordInput = document.getElementById('modal-password');
const modalPasswordGroup = document.getElementById('modal-password-group');

// State
let lastPulseReport = null;
let lastFeeReport = null;

// ── UI INTERACTIVITY ─────────────────────────────────────────────────────────

// SLIDER FIX: Update displayed days in real-time
daysInput.addEventListener('input', (e) => {
    daysVal.innerHTML = `${e.target.value} <span class="text-[10px] text-slate-600 uppercase">Days</span>`;
});

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

async function safeFetchJson(url, options = {}) {
    const res = await fetch(url, options);
    const contentType = res.headers.get("content-type");
    
    if (!res.ok) {
        // If it's a 404 or 500, it might return HTML depending on the platform
        if (contentType && contentType.includes("application/json")) {
            const errData = await res.json();
            throw new Error(errData.detail || `Server Error (${res.status})`);
        } else {
            // Highly likely HTML error page
            throw new Error(`Connectivity Issue: Backend returned ${res.status} (Non-JSON). Check if server is still deploying.`);
        }
    }
    
    if (!contentType || !contentType.includes("application/json")) {
        throw new Error("Invalid Response: Expected JSON but received HTML/Plaintext. Verify endpoint URL.");
    }
    
    return await res.json();
}

function parseNarrativeMarkdown(text) {
    return text.replace(/### (.*?)\n/g, '<h3 class="text-xs font-black text-emerald-500 mb-3 mt-8 first:mt-0 uppercase tracking-[0.3em] border-b border-emerald-500/10 pb-2">$1</h3>\n');
}

function unlockExportPanel() {
    customRecipientsInput.disabled = false;
    customRecipientsInput.classList.remove('opacity-50');
    
    gdocBtn.disabled = false;
    gdocBtn.classList.remove('text-blue-500/40', 'cursor-not-allowed', 'bg-slate-800/40');
    gdocBtn.classList.add('bg-slate-800', 'hover:bg-slate-700', 'text-blue-500', 'cursor-pointer', 'shadow-glow', 'shadow-blue-500/10');
    gdocBtn.querySelector('span').classList.replace('text-slate-600', 'text-white');
    
    gmailBtn.disabled = false;
    gmailBtn.classList.remove('text-red-500/40', 'cursor-not-allowed', 'bg-slate-800/40');
    gmailBtn.classList.add('bg-slate-800', 'hover:bg-slate-700', 'text-red-500', 'cursor-pointer', 'shadow-glow', 'shadow-red-500/10');
    gmailBtn.querySelector('span').classList.replace('text-slate-600', 'text-white');
}

function lockExportPanel() {
    customRecipientsInput.disabled = true;
    customRecipientsInput.classList.add('opacity-50');

    gdocBtn.disabled = true;
    gdocBtn.classList.add('text-blue-500/40', 'cursor-not-allowed', 'bg-slate-800/40');
    gdocBtn.classList.remove('bg-slate-800', 'hover:bg-slate-700', 'text-blue-500', 'cursor-pointer', 'shadow-glow', 'shadow-blue-500/10');
    gdocBtn.querySelector('span').classList.replace('text-white', 'text-slate-600');
    
    gmailBtn.disabled = true;
    gmailBtn.classList.add('text-red-500/40', 'cursor-not-allowed', 'bg-slate-800/40');
    gmailBtn.classList.remove('bg-slate-800', 'hover:bg-slate-700', 'text-red-500', 'cursor-pointer', 'shadow-glow', 'shadow-red-500/10');
    gmailBtn.querySelector('span').classList.replace('text-white', 'text-slate-600');
}

// ── MAIN ANALYSIS FLOW ───────────────────────────────────────────────────────
runBtn.addEventListener('click', async () => {
    const days = daysInput.value;
    const feeType = feeSelect.value;
    runBtn.disabled = true;
    lockExportPanel();
    
    narrativeCard.innerHTML = `
        <div class="flex flex-col items-center justify-center animate-pulse">
            <div class="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Analyzing Intelligence...</p>
        </div>
    `;
    feeCard.innerHTML = `
        <div class="flex flex-col items-center justify-center animate-pulse">
            <div class="w-12 h-12 border-4 border-slate-700 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
            <p class="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Syncing Insights...</p>
        </div>
    `;

    try {
        setStatus(`ORCHESTRATING DATA FLOW: ${days} DAY PERSPECTIVE...`);
        
        // Use safeFetchJson to avoid "Unexpected token <" error silently failing
        const scrapeData = await safeFetchJson(`${BASE_URL}/scrape?days=${days}`);

        setStatus(`HARVESTED ${scrapeData.row_count} DATA POINTS. EXECUTING AI ANALYSIS...`);
        
        const [analyzeData, feeData] = await Promise.all([
            safeFetchJson(`${BASE_URL}/analyze?csv_filename=${scrapeData.csv_filename}`, { method: 'POST' }),
            safeFetchJson(`${BASE_URL}/fee-explain?fee_type=${encodeURIComponent(feeType)}`, { method: 'POST' })
        ]);

        renderPulse(analyzeData.pulse_report);
        renderFee(feeData.data);
        
        lastPulseReport = analyzeData.pulse_report;
        lastFeeReport = feeData.data;
        unlockExportPanel();
        setStatus(`ANALYSIS READY. PROTOCOL COMPLETE.`);
        
    } catch (err) {
        console.error(err);
        setStatus(`SYSTEM ERROR: ${err.message}`, true);
        
        // Reset landing state if it fails
        narrativeCard.innerHTML = `
            <div class="empty-state opacity-40">
                <div class="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mb-6 mx-auto border border-white/5">
                    <svg class="w-10 h-10 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                </div>
                <p class="text-xs font-black uppercase tracking-[0.2em] text-red-500">Analysis Halted: Check Logs</p>
            </div>
        `;
    } finally {
        runBtn.disabled = false;
    }
});

// ── RENDERERS ────────────────────────────────────────────────────────────────
function renderPulse(report) {
    pulseContainer.innerHTML = '';
    
    const narrativeEl = document.createElement('div');
    narrativeEl.className = "p-10 bg-slate-900 border border-white/10 rounded-2xl min-h-[300px] text-left transition-all duration-500";
    narrativeEl.innerHTML = `
        <div class="prose prose-invert max-w-none text-slate-300 text-sm md:text-base leading-relaxed font-medium">
            ${parseNarrativeMarkdown(report.narrative)}
        </div>
    `;
    pulseContainer.appendChild(narrativeEl);
    
    pulseMeta.classList.remove('hidden');
    
    const sortedThemes = Object.entries(report.theme_data || {})
        .filter(([_, data]) => data.count > 0)
        .sort((a, b) => b[1].count - a[1].count);

    for (const [theme, data] of sortedThemes) {
        let domSentiment = "Neutral";
        let maxCount = -1;
        for (const [sentiment, count] of Object.entries(data.sentiment_dist)) {
            if (count > maxCount) { maxCount = count; domSentiment = sentiment; }
        }

        let badgeClass = "bg-slate-500/10 text-slate-400";
        if (domSentiment.toLowerCase() === "positive") badgeClass = "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20";
        if (domSentiment.toLowerCase() === "negative") badgeClass = "bg-red-400/10 text-red-400 border border-red-400/20";

        const quotesHtml = data.top_quotes.slice(0, 2).map(q => 
            `<div class="text-[11px] italic text-slate-400 border-l-2 border-emerald-500/30 pl-3 mt-3 py-1.5 bg-white/5 rounded-r-lg truncate hover:whitespace-normal transition-all duration-300">"${q}"</div>`
        ).join('');

        const card = document.createElement('div');
        card.className = 'p-6 bg-slate-900 border border-white/5 rounded-2xl hover:border-emerald-500/30 transition-all animate-in fade-in slide-in-from-bottom-2 duration-500';
        card.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <h4 class="font-black text-slate-100 uppercase tracking-widest text-xs">${theme}</h4>
                <span class="px-2.5 py-1 rounded-md text-[9px] font-black uppercase tracking-[0.2em] ${badgeClass}">${domSentiment}</span>
            </div>
            <div class="flex items-center space-x-4 text-[10px] font-black text-slate-600 uppercase tracking-widest mb-3 border-b border-white/5 pb-2">
                <span>${data.count} REVIEWS</span>
                <span>${data.avg_rating}★ AVG</span>
            </div>
            ${quotesHtml}
        `;
        pulseContainer.appendChild(card);
    }
}

function renderFee(data) {
    const listHtml = data.bullets.map(b => {
        const parts = b.split(':');
        if (parts.length > 1) {
            return `
                <li class="flex items-start space-x-4">
                    <span class="text-emerald-500 mt-1.5 flex-shrink-0"><svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></span>
                    <span class="leading-relaxed">
                        <strong class="text-slate-100 font-black uppercase tracking-[0.2em] text-[10px] block mb-1">${parts[0]}</strong>
                        <span class="block text-slate-400 text-sm">${parts.slice(1).join(':')}</span>
                    </span>
                </li>`;
        }
        return `<li class="flex items-start space-x-4"><span class="text-emerald-500 mt-1.5">•</span><span class="text-slate-400 text-sm">${b}</span></li>`;
    }).join('');

    feeCard.classList.remove('flex', 'justify-center', 'items-center', 'text-center');
    feeCard.className = "p-10 bg-slate-900 border border-white/10 rounded-2xl min-h-[250px] text-left transition-all duration-500";
    feeCard.innerHTML = `
        <div class="flex items-center justify-between mb-8 border-b border-white/5 pb-4">
            <h4 class="text-emerald-500 font-black uppercase tracking-[0.3em] text-[11px]">${data.fee_type} Insights</h4>
            <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-glow shadow-emerald-500/50"></div>
        </div>
        <ul class="space-y-6">${listHtml}</ul>
        <div class="mt-8 pt-6 border-t border-white/5 flex items-center justify-between">
            <div class="text-[10px] font-black text-slate-700 uppercase tracking-widest italic">Checked: ${data.last_checked}</div>
            <a href="${data.source_url}" target="_blank" class="text-[9px] font-black text-emerald-500 hover:text-emerald-400 uppercase tracking-widest bg-emerald-500/5 px-3 py-1.5 rounded-lg border border-emerald-500/10">Official Source</a>
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
    modalMsg.textContent = customRecipientsInput.value.trim() ? `TARGETING: ${customRecipientsInput.value.trim()}` : "PREPARING GMAIL DRAFT.";
    modalPasswordGroup.classList.toggle('hidden', !customRecipientsInput.value.trim());
    approvalModal.classList.remove('hidden');
});

gdocBtn.addEventListener('click', () => {
    currentExportAction = 'gdoc';
    modalMsg.textContent = "SYNCING WITH CLOUD REPOSITORY.";
    modalPasswordGroup.classList.add('hidden');
    approvalModal.classList.remove('hidden');
});

modalCancel.addEventListener('click', () => approvalModal.classList.add('hidden'));

modalConfirm.addEventListener('click', async () => {
    approvalModal.classList.add('hidden');
    const payload = { pulse_report: lastPulseReport, fee_report: lastFeeReport, custom_recipients: customRecipientsInput.value.trim(), custom_export_password: modalPasswordInput.value };
    try {
        const route = currentExportAction === 'gdoc' ? '/export-doc' : '/export-email';
        setStatus("Processing Export...");
        
        const data = await safeFetchJson(`${BASE_URL}${route}`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(payload) 
        });
        
        setStatus(`Export Complete: ${data.doc_id || data.draft_id}`);
    } catch (err) { setStatus(`Export Error: ${err.message}`, true); }
});

document.documentElement.classList.add('dark');
body.classList.add('dark-mode');
console.log("Intelligence Interface V4.6 Live (UI Resilience Protocol)");
