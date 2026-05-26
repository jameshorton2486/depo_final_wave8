function _activeExhibitJobId() {
    if (state.workspaceJob && state.workspaceJob.jobId) return state.workspaceJob.jobId;
    const ids = state.activeTranscriptJobIds || [];
    return ids.length > 0 ? ids[0] : null;
}

function _ensureExhibitsMeta() {
    if (!state.exhibitsMeta) {
        state.exhibitsMeta = {
            jobId: null,
            lastLoadedAt: null,
            lastSavedAt: null,
            lastError: null,
        };
    }
    return state.exhibitsMeta;
}

function renderExhibitAuthorityStatus(message, tone) {
    const el = document.getElementById('exhibitAuthorityStatus');
    if (!el) return;
    const classMap = {
        idle: 'text-xs text-slate-500 font-mono',
        loading: 'text-xs text-indigo-400 font-mono',
        saved: 'text-xs text-emerald-400 font-mono',
        warning: 'text-xs text-amber-400 font-mono',
        error: 'text-xs text-red-400 font-mono',
    };
    el.className = classMap[tone] || classMap.idle;
    el.innerText = message;
}

function applyExhibitMarkersToTranscript() {
    const byUtterance = {};
    (state.exhibits || []).forEach(ex => {
        const anchor = ex.anchor_utterance_id;
        if (!anchor) return;
        if (!byUtterance[anchor]) byUtterance[anchor] = [];
        byUtterance[anchor].push(ex.exhibit_number);
    });
    (state.transcriptLines || []).forEach(line => {
        if (!line || !line.jobId) return;
        const tags = byUtterance[line.id] || [];
        line.exhibit = tags.length ? tags.join(', ') : '';
    });
}

function renderExhibitsIndex() {
    const container = document.getElementById('exhibitsIndexList');
    if (!container) return;
    container.innerHTML = "";

    const exhibits = state.exhibits || [];
    if (exhibits.length === 0) {
        container.innerHTML = `<div class="bg-slate-950/60 border border-slate-800 rounded-xl p-4 text-xs text-slate-500 italic">No authoritative exhibits saved for this transcript job yet. Stage 4 anchors exhibits to transcript utterances and freezes them with certification snapshots.</div>`;
        return;
    }

    exhibits.forEach(ex => {
        const line = (state.transcriptLines || []).find(l => l && l.id === ex.anchor_utterance_id);
        const anchorLabel = line
            ? `Utterance ${line.index} · ${(line.speaker || 'Unknown Speaker')}`
            : `Anchor ${ex.anchor_utterance_id}`;
        const anchorPreview = line && line.text
            ? line.text.slice(0, 120)
            : (ex.anchor_note || 'Anchor preview unavailable until transcript is loaded.');
        const certifiedBadge = state.caseInfo && (state.caseInfo.certified || state.caseInfo.certifiedSnapshotId)
            ? `<span class="text-[8px] px-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">CERT FREEZE AVAILABLE</span>`
            : '';
        const div = document.createElement('div');
        div.className = "bg-slate-950 p-4 rounded-xl border border-slate-800 flex items-start justify-between gap-4 font-sans";
        div.innerHTML = `
            <div class="min-w-0">
                <div class="flex items-center gap-2 mb-1 flex-wrap">
                    <span class="text-[9px] font-bold tracking-wider uppercase bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/20">Exhibit ${ex.exhibit_number}</span>
                    ${certifiedBadge}
                </div>
                <h4 class="text-sm font-bold text-white mt-1">${ex.exhibit_title || 'Untitled Exhibit'}</h4>
                <p class="text-xs text-slate-400 mt-0.5">Offered by: ${ex.offering_attorney || 'Unspecified attorney'}</p>
                <p class="text-[11px] text-slate-500 mt-1 font-mono">${anchorLabel}</p>
                <p class="text-[11px] text-slate-400 mt-1 italic break-words">"${anchorPreview}"</p>
            </div>
            <div class="text-right font-mono shrink-0">
                <span class="text-[10px] text-slate-500 block">Saved anchor</span>
                <span class="text-xs text-indigo-400 font-bold block mt-0.5">${ex.anchor_utterance_id}</span>
                <div class="flex items-center justify-end gap-2 mt-3">
                    <button onclick="quickJumpToLine('${ex.anchor_utterance_id}')" class="text-[10px] text-slate-400 hover:text-white transition-all underline">Jump</button>
                    <button onclick="editTranscriptExhibit('${ex.exhibit_id}')" class="text-[10px] text-indigo-400 hover:text-indigo-300 transition-all underline">Edit</button>
                    <button onclick="deleteTranscriptExhibit('${ex.exhibit_id}')" class="text-[10px] text-red-400 hover:text-red-300 transition-all underline">Delete</button>
                </div>
            </div>
        `;
        container.appendChild(div);
    });
}

async function loadWorkspaceExhibits(jobId) {
    const resolvedJobId = jobId || _activeExhibitJobId();
    const meta = _ensureExhibitsMeta();
    meta.jobId = resolvedJobId || null;
    state.exhibits = [];
    applyExhibitMarkersToTranscript();
    renderExhibitsIndex();

    if (!resolvedJobId || !window.api || typeof window.api.listTranscriptExhibits !== 'function') {
        renderExhibitAuthorityStatus('No transcript job loaded.', 'idle');
        return;
    }

    renderExhibitAuthorityStatus('Loading authoritative exhibits…', 'loading');
    try {
        if (!state.caseInfo.certifiedSnapshotId && window.api.listSnapshots) {
            try {
                const snapRes = await window.api.listSnapshots(resolvedJobId);
                const locked = (snapRes.snapshots || []).find(s => s.locked);
                if (locked) {
                    state.caseInfo.certifiedSnapshotId = locked.snapshot_id;
                }
            } catch (_) {}
        }
        const res = await window.api.listTranscriptExhibits(resolvedJobId);
        state.exhibits = (res && res.exhibits) || [];
        meta.lastLoadedAt = new Date().toISOString();
        meta.lastError = null;
        applyExhibitMarkersToTranscript();
        renderExhibitsIndex();
        if (typeof compileAndRenderTranscript === 'function') compileAndRenderTranscript();
        const statusSuffix = state.caseInfo && (state.caseInfo.certified || state.caseInfo.certifiedSnapshotId)
            ? ' Locked certification snapshot present.'
            : '';
        renderExhibitAuthorityStatus(
            `${state.exhibits.length} saved exhibit(s) loaded from backend.${statusSuffix}`,
            state.exhibits.length ? 'saved' : 'idle'
        );
    } catch (err) {
        meta.lastError = err.message || String(err);
        state.exhibits = [];
        applyExhibitMarkersToTranscript();
        renderExhibitsIndex();
        renderExhibitAuthorityStatus(`Exhibit load failed: ${meta.lastError}`, 'error');
    }
}

function _focusedAnchorLine() {
    const focused = (state.transcriptLines || []).find(
        line => line && line.id === state.focusedLineId && line.jobId
    );
    if (focused) return focused;
    return (state.transcriptLines || []).find(line => line && line.jobId) || null;
}

function _nextExhibitNumber() {
    const nums = (state.exhibits || [])
        .map(ex => parseInt(ex.exhibit_number, 10))
        .filter(n => Number.isFinite(n));
    if (!nums.length) return '1';
    return String(Math.max(...nums) + 1);
}

async function createNewExhibitMark() {
    const jobId = _activeExhibitJobId();
    if (!jobId) {
        showToast("Load a transcript job before creating an exhibit anchor.", "amber");
        return;
    }
    const anchorLine = _focusedAnchorLine();
    if (!anchorLine) {
        showToast("Focus a real transcript utterance in Stage 3 before anchoring an exhibit.", "amber");
        return;
    }

    const exhibitNumber = window.prompt('Exhibit number', _nextExhibitNumber());
    if (exhibitNumber === null) return;
    const exhibitTitle = window.prompt('Exhibit title/description', 'Deposition Exhibit');
    if (exhibitTitle === null) return;
    const offeringAttorney = window.prompt('Offering attorney', state.caseInfo.custodialName || state.caseInfo.requestingParty || '');
    if (offeringAttorney === null) return;

    renderExhibitAuthorityStatus('Saving exhibit anchor…', 'loading');
    try {
        await window.api.createTranscriptExhibit(jobId, {
            exhibit_number: String(exhibitNumber || '').trim(),
            exhibit_title: String(exhibitTitle || '').trim(),
            offering_attorney: String(offeringAttorney || '').trim(),
            description: String(exhibitTitle || '').trim(),
            anchor_utterance_id: anchorLine.id,
            anchor_note: anchorLine.text || '',
        });
        _ensureExhibitsMeta().lastSavedAt = new Date().toISOString();
        await loadWorkspaceExhibits(jobId);
        showToast(`Exhibit ${String(exhibitNumber).trim()} saved to the authoritative exhibit record.`, "emerald");
    } catch (err) {
        renderExhibitAuthorityStatus(`Exhibit save failed: ${err.message}`, 'error');
        showToast(`Exhibit save failed: ${err.message}`, "red");
    }
}

async function editTranscriptExhibit(exhibitId) {
    const ex = (state.exhibits || []).find(item => item.exhibit_id === exhibitId);
    if (!ex) return;
    const exhibitNumber = window.prompt('Exhibit number', ex.exhibit_number || '');
    if (exhibitNumber === null) return;
    const exhibitTitle = window.prompt('Exhibit title/description', ex.exhibit_title || '');
    if (exhibitTitle === null) return;
    const offeringAttorney = window.prompt('Offering attorney', ex.offering_attorney || '');
    if (offeringAttorney === null) return;
    const anchorLine = _focusedAnchorLine() || (state.transcriptLines || []).find(line => line && line.id === ex.anchor_utterance_id);
    if (!anchorLine) {
        showToast("Load the anchored transcript before editing this exhibit.", "amber");
        return;
    }
    try {
        renderExhibitAuthorityStatus('Updating exhibit…', 'loading');
        await window.api.updateTranscriptExhibit(exhibitId, {
            exhibit_number: String(exhibitNumber || '').trim(),
            exhibit_title: String(exhibitTitle || '').trim(),
            offering_attorney: String(offeringAttorney || '').trim(),
            description: String(exhibitTitle || '').trim(),
            anchor_utterance_id: anchorLine.id,
            anchor_note: anchorLine.text || '',
        });
        _ensureExhibitsMeta().lastSavedAt = new Date().toISOString();
        await loadWorkspaceExhibits(_activeExhibitJobId());
        showToast(`Exhibit ${String(exhibitNumber).trim()} updated.`, "emerald");
    } catch (err) {
        renderExhibitAuthorityStatus(`Exhibit update failed: ${err.message}`, 'error');
        showToast(`Exhibit update failed: ${err.message}`, "red");
    }
}

async function deleteTranscriptExhibit(exhibitId) {
    const ex = (state.exhibits || []).find(item => item.exhibit_id === exhibitId);
    if (!ex) return;
    if (!window.confirm(`Delete Exhibit ${ex.exhibit_number}? This removes the authoritative exhibit record for the current working transcript.`)) {
        return;
    }
    try {
        renderExhibitAuthorityStatus('Deleting exhibit…', 'loading');
        await window.api.deleteTranscriptExhibit(exhibitId);
        _ensureExhibitsMeta().lastSavedAt = new Date().toISOString();
        await loadWorkspaceExhibits(_activeExhibitJobId());
        showToast(`Exhibit ${ex.exhibit_number} deleted.`, "emerald");
    } catch (err) {
        renderExhibitAuthorityStatus(`Exhibit delete failed: ${err.message}`, 'error');
        showToast(`Exhibit delete failed: ${err.message}`, "red");
    }
}

function quickJumpToLine(anchorUtteranceId) {
    goToStage(3);
    setTimeout(() => {
        const el = document.getElementById(anchorUtteranceId);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            focusLineRow(anchorUtteranceId);
        } else {
            showToast("Anchor line is not currently loaded in the workspace.", "amber");
        }
    }, 300);
}

window.renderExhibitsIndex = renderExhibitsIndex;
window.loadWorkspaceExhibits = loadWorkspaceExhibits;
window.createNewExhibitMark = createNewExhibitMark;
window.editTranscriptExhibit = editTranscriptExhibit;
window.deleteTranscriptExhibit = deleteTranscriptExhibit;
window.quickJumpToLine = quickJumpToLine;
window.applyExhibitMarkersToTranscript = applyExhibitMarkersToTranscript;
