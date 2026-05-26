/*
 * Stage 6 — Export.
 *
 * Wave 12: the Export screen is now a true "what will export" preview.
 * It renders the CURRENT WORKING transcript through the canonical
 * backend export pipeline (render.py -> export_render.py) — the same
 * pipeline the downloaded file uses. No hardcoded mock text.
 *
 *   - "Refresh Preview" re-renders from current transcript state.
 *   - A saved job uses the backend job endpoint (authoritative).
 *   - A transient unsaved transcript uses the fallback endpoint and is
 *     clearly labelled "approximate".
 */

// The export document last rendered — shared by preview and download.
let _exportDoc = null;

function _activeJobId() {
    const ids = state.activeTranscriptJobIds || [];
    return ids.length > 0 ? ids[0] : null;
}

async function _resolveCertifiedSnapshotId(jobId) {
    if (state.caseInfo && state.caseInfo.certifiedSnapshotId) {
        return state.caseInfo.certifiedSnapshotId;
    }
    if (!jobId || !window.api || typeof window.api.listSnapshots !== 'function') {
        return null;
    }
    try {
        const res = await window.api.listSnapshots(jobId);
        const locked = (res.snapshots || []).find(s => s.locked);
        if (locked) {
            state.caseInfo.certifiedSnapshotId = locked.snapshot_id;
            return locked.snapshot_id;
        }
    } catch (err) {
        console.warn('Could not resolve certified snapshot id:', err);
    }
    return null;
}

// Build the fallback payload from current frontend transcript state.
function _fallbackPayload() {
    const lines = (state.transcriptLines || [])
        .filter(l => l.speaker !== "SYSTEM INDEXER")
        .map(l => ({
            line_type: l.type === "Q" ? "Q" : l.type === "A" ? "A"
                     : l.flagged ? "flagged" : "colloquy",
            speaker_label: l.speaker || "",
            text: l.text || "",
        }));
    const ci = state.caseInfo || {};
    return {
        lines,
        caption: ci.caption || "",
        cause_number: ci.cause || "",
        witness: ci.deponent || "",
        proceedings_date: ci.date || "",
        examining_attorney_label: ci.examiningAttorney || "",
    };
}

async function refreshExportPreview() {
    const btn = document.getElementById('refreshPreviewBtn');
    const statusLine = document.getElementById('previewStatusLine');
    const authorityBanner = document.getElementById('exportAuthorityBanner');
    if (btn) { btn.disabled = true; btn.innerText = "Rendering…"; }
    if (statusLine) statusLine.innerText = "Rendering current transcript…";

    try {
        const jobId = _activeJobId();
        const certifiedSnapshotId = jobId ? await _resolveCertifiedSnapshotId(jobId) : null;
        if (jobId) {
            _exportDoc = await window.api.getExportPreview(jobId);
        } else {
            _exportDoc = await window.api.getExportPreviewFallback(_fallbackPayload());
        }
        renderExportPreview(_exportDoc);

        const when = new Date().toLocaleTimeString();
        if (statusLine) {
            statusLine.innerText = _exportDoc.is_approximate
                ? `Approximate preview (unsaved transcript) — ${_exportDoc.total_pages} page(s), rendered ${when}`
                : `Authoritative preview — ${_exportDoc.total_pages} page(s), ${_exportDoc.total_lines} line(s), rendered ${when}`;
        }
        if (authorityBanner) {
            const sourceSel = document.getElementById('exportSourceSelect');
            const requestedSource = sourceSel ? sourceSel.value : 'working';
            authorityBanner.innerText = certifiedSnapshotId
                ? requestedSource === 'certified'
                    ? "Certified export selected: the downloaded file will be rendered from the latest locked certification snapshot. Preview remains the current working transcript for comparison."
                    : "Working export selected: the downloaded file will come from the current authoritative working transcript. Prior certified snapshots remain available as separate immutable versions."
                : "Working export mode: renders the current authoritative working transcript. Certified snapshot export becomes available after Stage 5 certification.";
        }
        if (typeof showToast === "function") {
            showToast(`Preview refreshed — ${_exportDoc.total_pages} page(s).`,
                _exportDoc.is_approximate ? "amber" : "emerald");
        }
    } catch (err) {
        if (statusLine) statusLine.innerText = `Preview failed: ${err.message}`;
        if (typeof showToast === "function") showToast(`Preview failed: ${err.message}`, "red");
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = "⟳ Refresh Preview"; }
    }
}

// Render the ExportDocument into the MS-Word-style preview pane.
function renderExportPreview(doc) {
    const body = document.getElementById('exportPreviewBody');
    if (!body || !doc) return;
    body.innerHTML = "";

    (doc.pages || []).forEach(page => {
        const pageEl = document.createElement('div');
        pageEl.className = "mb-6";

        const head = document.createElement('div');
        head.innerHTML = `
            <p class="text-center font-bold text-slate-600 text-[10px] mb-1 font-mono">PAGE ${page.page_number}</p>
            ${doc.caption ? `<p class="text-center text-slate-400 text-[9px] border-b border-slate-100 pb-2 mb-2 font-mono">${doc.caption}</p>` : ""}`;
        pageEl.appendChild(head);

        const grid = document.createElement('div');
        grid.className = "flex gap-3 font-mono text-[9px] leading-5";

        const nums = (page.lines || [])
            .map(l => l.line_number).join("<br>");
        const numCol = document.createElement('div');
        numCol.className = "text-slate-400 text-right w-5 border-r border-red-200 pr-2 shrink-0";
        numCol.innerHTML = nums;

        const textCol = document.createElement('div');
        textCol.className = "flex-1 text-slate-700 whitespace-pre";
        textCol.innerHTML = (page.lines || []).map(l => {
            const safe = (l.text || "").replace(/&/g, "&amp;").replace(/</g, "&lt;");
            let cls = "";
            if (l.line_kind === "examination") cls = "font-bold text-slate-800";
            else if (l.line_kind === "flagged") cls = "text-amber-600";
            else if (l.line_kind === "proceedings") cls = "text-slate-500 uppercase";
            return `<span class="${cls}">${safe || "&nbsp;"}</span>`;
        }).join("<br>");

        grid.appendChild(numCol);
        grid.appendChild(textCol);
        pageEl.appendChild(grid);
        body.appendChild(pageEl);
    });

    // Update the watermark + seal.
    const seal = document.getElementById('exportPreviewSeal');
    if (seal) {
        if (doc.is_approximate) {
            seal.className = "bg-amber-950/40 p-3.5 rounded-xl border border-amber-500/30 mt-4 text-center";
            seal.innerHTML = `<p class="text-xs text-amber-300 font-bold">⚠ Approximate — transcript not yet saved</p>`;
        } else {
            seal.className = "bg-emerald-950/40 p-3.5 rounded-xl border border-emerald-500/20 mt-4 text-center";
            seal.innerHTML = `<p class="text-xs text-emerald-300 font-bold">✓ Preview matches export output</p>`;
        }
    }
}

// Wave 18: export is done by the BACKEND, which writes a real file to
// disk and returns the path. This replaces the old browser-blob
// download, which silently failed inside the PyWebView desktop shell.
async function triggerExportAction() {
    const formatSelect = document.getElementById('exportFormatSelect');
    const destSelect = document.getElementById('exportDestinationSelect');
    const sourceSelect = document.getElementById('exportSourceSelect');
    const format = formatSelect ? formatSelect.value : 'txt';
    const destination = destSelect ? destSelect.value : 'downloads';
    const exportSource = sourceSelect ? sourceSelect.value : 'working';

    const jobId = _activeJobId();
    if (!jobId) {
        if (typeof showToast === "function")
            showToast("No transcript loaded to export.", "red");
        return;
    }

    let explicitPath = null;
    if (destination === 'path') {
        // "Choose folder each time" -- ask the desktop shell for a
        // native folder/save dialog. pywebview exposes this; if it is
        // unavailable (e.g. running in a plain browser) fall back to
        // the Downloads folder.
        if (window.pywebview && window.pywebview.api
                && window.pywebview.api.choose_save_folder) {
            try {
                explicitPath = await window.pywebview.api.choose_save_folder();
            } catch (e) { explicitPath = null; }
            if (!explicitPath) {
                if (typeof showToast === "function")
                    showToast("Export cancelled — no folder chosen.", "amber");
                return;
            }
        } else {
            if (typeof showToast === "function")
                showToast("Folder picker unavailable here — saving to Downloads.", "amber");
        }
    }

    const btn = document.getElementById('exportActionBtn');
    if (btn) { btn.disabled = true; }
    try {
        let snapshotId = null;
        if (exportSource === 'certified') {
            snapshotId = await _resolveCertifiedSnapshotId(jobId);
            if (!snapshotId) {
                throw new Error('No locked certification snapshot is available for certified export.');
            }
        }
        const res = await window.api.exportTranscript(
            jobId,
            format,
            explicitPath ? 'path' : destination,
            explicitPath,
            snapshotId
        );
        if (typeof showToast === "function") {
            showToast(`Saved: ${res.path}`, "emerald");
        }
        if (typeof addProvenanceRecord === "function") {
            addProvenanceRecord("Export",
                `Exported ${res.format.toUpperCase()} (${res.pages} page(s)) to ${res.path}`, "user", {
                    eventType: 'export_requested',
                    source: 'export',
                    metadata: {
                        format: res.format,
                        export_state: res.export_state || 'working',
                        path: res.path,
                    },
                    relatedSnapshotId: res.snapshot_id || '',
                });
        }
        // Surface the saved path in the status line so it does not vanish.
        const statusLine = document.getElementById('previewStatusLine');
        if (statusLine) {
            statusLine.innerText = `Saved ${res.format.toUpperCase()} (${res.export_state === 'certified_snapshot' ? 'certified snapshot export' : 'working transcript export'}) — ${res.path}`;
        }
    } catch (err) {
        if (typeof showToast === "function")
            showToast(`Export failed: ${err.message}`, "red");
    } finally {
        if (btn) { btn.disabled = false; }
    }
}

window.refreshExportPreview = refreshExportPreview;
window.renderExportPreview = renderExportPreview;
window.triggerExportAction = triggerExportAction;

// Auto-render the preview when the Export screen opens, so the reporter
// always sees the current transcript state without an extra click.
window.addEventListener("screen:loaded", (e) => {
    if (e.detail && e.detail.stageNum === 6) {
        refreshExportPreview();
    }
});

document.addEventListener('change', (event) => {
    if (event.target && event.target.id === 'exportSourceSelect') {
        refreshExportPreview();
    }
});
