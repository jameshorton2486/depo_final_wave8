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
    if (btn) { btn.disabled = true; btn.innerText = "Rendering…"; }
    if (statusLine) statusLine.innerText = "Rendering current transcript…";

    try {
        const jobId = _activeJobId();
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

// Export uses the SAME rendered document as the preview.
async function triggerExportAction() {
    const formatSelect = document.getElementById('exportFormatSelect');
    const format = formatSelect ? formatSelect.value : 'txt';
    const mimeMap = {
        docx: 'text/plain', pdf: 'text/plain',
        txt: 'text/plain', rtf: 'application/rtf',
    };

    // Always render fresh so the file equals the current transcript.
    await refreshExportPreview();
    if (!_exportDoc) {
        if (typeof showToast === "function") showToast("Nothing to export — preview failed.", "red");
        return;
    }

    let payload = "";
    if (_exportDoc.caption) payload += `${_exportDoc.caption}\n`;
    if (_exportDoc.cause_number) payload += `CAUSE NO. ${_exportDoc.cause_number}\n`;
    if (_exportDoc.witness) payload += `CERTIFIED DEPOSITION OF ${_exportDoc.witness.toUpperCase()}\n`;
    payload += "\n";

    (_exportDoc.pages || []).forEach(page => {
        payload += `${"=".repeat(55)}\nPAGE ${page.page_number}\n${"=".repeat(55)}\n`;
        (page.lines || []).forEach(l => {
            payload += `${String(l.line_number).padEnd(3, ' ')}| ${l.text}\n`;
        });
        payload += "\n";
    });

    if (state.exhibits && state.exhibits.length) {
        payload += `\nEXHIBIT INDEX APPEND:\n`;
        state.exhibits.forEach(ex => {
            payload += `Exhibit ${ex.num}: ${ex.title} · Offered by ${ex.attorney} · Page ${ex.page}, Line ${ex.line}\n`;
        });
    }
    payload += `\n\nDIGITAL SIGNATURE ID SEAL: ${(state.caseInfo && state.caseInfo.signature) || "CSR"}\n`;

    const blob = new Blob([payload], { type: mimeMap[format] || 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const slug = (_exportDoc.caption || "transcript")
        .replace(/[^a-z0-9]+/gi, "_").slice(0, 40);
    a.download = `${slug}_Certified_Transcript.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    if (typeof showToast === "function") {
        showToast(`Certified transcript (.${format}) downloaded — matches preview.`, "emerald");
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
