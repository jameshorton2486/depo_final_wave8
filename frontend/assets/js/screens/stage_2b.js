/**
 * Stage 2b — Speaker Mapping.
 *
 * Bridges raw Deepgram diarization (acoustic speaker clusters) to a
 * canonical participant list. The reporter assigns each detected speaker
 * a role and a name; speakers sharing a role + name collapse into one
 * participant. On confirm, the mapping is persisted per job and the
 * Workspace transcript is rebuilt so Q/A and colloquy reflect it.
 *
 * No AI is involved: this is the reporter's judgment captured as data.
 */

// Module state for the screen. Rebuilt every time the screen loads.
let _smState = { jobs: [], assignments: {} };

function _smEsc(s) {
    return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/** Update one speaker's role/name assignment as the reporter edits. */
function _smSetAssignment(jobId, speakerIndex, field, value) {
    const job = _smState.assignments[jobId];
    if (!job) return;
    if (!job[speakerIndex]) job[speakerIndex] = { role: "other", name: "" };
    job[speakerIndex][field] = value;
}

/** Load the speaker-mapping payload for every active job and render it. */
async function _smLoad() {
    const root = document.getElementById("speakerMappingRoot");
    if (!root) return;

    const jobIds = (state.activeTranscriptJobIds || []).slice();
    _smState = { jobs: [], assignments: {} };

    if (jobIds.length === 0) {
        root.innerHTML = `
            <div class="text-center py-16">
                <p class="text-sm text-slate-400">No transcribed media is loaded.</p>
                <button onclick="goToStage(2)" class="mt-3 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold">
                    Go to Transcripts
                </button>
            </div>`;
        _smSetHint("");
        return;
    }

    if (!window.api || typeof window.api.getSpeakerMapping !== "function") {
        root.innerHTML = `<p class="text-sm text-red-400">Speaker mapping is unavailable — backend not reachable.</p>`;
        return;
    }

    try {
        for (const jobId of jobIds) {
            const view = await window.api.getSpeakerMapping(jobId);
            _smState.jobs.push(view);

            // Seed per-speaker assignments from the prefill participants.
            const assigns = {};
            (view.participants || []).forEach(p => {
                (p.speaker_indices || []).forEach(idx => {
                    assigns[idx] = { role: p.role || "other", name: p.name || "" };
                });
            });
            (view.detected_speakers || []).forEach(d => {
                if (!assigns[d.speaker_index]) {
                    assigns[d.speaker_index] = { role: "other", name: "" };
                }
            });
            _smState.assignments[jobId] = assigns;
        }
    } catch (err) {
        console.error("Speaker mapping load failed:", err);
        root.innerHTML = `<p class="text-sm text-red-400">Could not load speaker data: ${_smEsc(err.message || err)}</p>`;
        return;
    }

    _smRender();
}

/** Build the role <select> options markup, pre-selecting `current`. */
function _smRoleOptions(roles, current) {
    return (roles || []).map(r =>
        `<option value="${_smEsc(r.value)}"${r.value === current ? " selected" : ""}>${_smEsc(r.label)}</option>`
    ).join("");
}

function _smRender() {
    const root = document.getElementById("speakerMappingRoot");
    if (!root) return;

    const multiJob = _smState.jobs.length > 1;
    const blocks = _smState.jobs.map(view => {
        const assigns = _smState.assignments[view.job_id] || {};
        const prefillBadge = view.is_prefill
            ? `<span class="px-2 py-0.5 text-[9px] font-bold rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 tracking-wider">PREFILLED GUESS — REVIEW</span>`
            : `<span class="px-2 py-0.5 text-[9px] font-bold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 tracking-wider">CONFIRMED</span>`;

        const rows = (view.detected_speakers || []).map(d => {
            const a = assigns[d.speaker_index] || { role: "other", name: "" };
            return `
            <div class="flex items-start gap-3 py-3 border-b border-slate-800/70 last:border-0">
                <div class="w-20 shrink-0">
                    <div class="text-xs font-bold text-slate-200">${_smEsc(d.speaker_label)}</div>
                    <div class="text-[10px] text-slate-500 font-mono mt-0.5">${d.word_count} words</div>
                    <div class="text-[10px] text-slate-500 font-mono">${d.utterance_count} turns</div>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-[11px] text-slate-400 italic leading-snug mb-2 line-clamp-2">&ldquo;${_smEsc(d.sample) || "(no sample)"}&rdquo;</p>
                    <div class="flex flex-wrap items-center gap-2">
                        <select onchange="_smSetAssignment('${view.job_id}', ${d.speaker_index}, 'role', this.value)"
                                class="bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 px-2 py-1.5 focus:border-indigo-500 focus:outline-none">
                            ${_smRoleOptions(view.roles, a.role)}
                        </select>
                        <input type="text" value="${_smEsc(a.name)}" placeholder="Name (e.g. Heath Thomas)"
                               oninput="_smSetAssignment('${view.job_id}', ${d.speaker_index}, 'name', this.value)"
                               class="bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 px-2 py-1.5 w-56 focus:border-indigo-500 focus:outline-none placeholder:text-slate-600">
                    </div>
                </div>
            </div>`;
        }).join("");

        return `
        <div class="bg-slate-900/60 border border-slate-800 rounded-xl mb-5 overflow-hidden">
            <div class="px-4 py-2.5 border-b border-slate-800 flex items-center justify-between gap-3 bg-slate-900">
                <div class="text-xs font-semibold text-slate-300 truncate">
                    ${multiJob ? "&#x1F4C1; " : ""}${_smEsc(view.source_filename)}
                </div>
                ${prefillBadge}
            </div>
            <div class="px-4 py-1">${rows || '<p class="text-xs text-slate-500 py-3 italic">No speakers detected.</p>'}</div>
        </div>`;
    }).join("");

    root.innerHTML = `
        <div class="max-w-4xl">
            <div class="flex items-start gap-2 mb-5 text-[11px] text-slate-500 bg-slate-900/40 border border-slate-800/60 rounded-lg px-3 py-2">
                <span class="text-indigo-400 font-bold">Tip</span>
                <span>Examining Attorney renders as <span class="text-indigo-300 font-mono">Q.</span>,
                Witness as <span class="text-cyan-300 font-mono">A.</span>; every other role renders as
                named colloquy. Two clusters of the same person &mdash; same role and name &mdash; become one participant.</span>
            </div>
            ${blocks}
        </div>`;
    _smSetHint(`${_smState.jobs.length} file(s) ready to map`);
}

function _smSetHint(text) {
    const hint = document.getElementById("speakerMappingHint");
    if (hint) hint.textContent = text;
}

/** Group a job's per-speaker assignments into canonical participants. */
function _smBuildParticipants(jobId) {
    const assigns = _smState.assignments[jobId] || {};
    const groups = {};   // key: role||name  ->  participant
    let order = 0;
    Object.keys(assigns).forEach(idxStr => {
        const idx = parseInt(idxStr, 10);
        const a = assigns[idxStr];
        const name = (a.name || "").trim();
        const role = a.role || "other";
        const key = role + "||" + name.toLowerCase();
        if (!groups[key]) {
            groups[key] = {
                name: name || null,
                role: role,
                speaker_indices: [],
                sort_order: order++,
            };
        }
        groups[key].speaker_indices.push(idx);
    });
    return Object.values(groups);
}

/** Persist every job's mapping, rebuild the transcript, advance to Stage 3. */
async function confirmSpeakerMapping() {
    const btn = document.getElementById("confirmSpeakerMappingBtn");
    const jobIds = (state.activeTranscriptJobIds || []).slice();
    if (jobIds.length === 0) { goToStage(2); return; }

    if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
    try {
        for (const jobId of jobIds) {
            const participants = _smBuildParticipants(jobId);
            await window.api.saveSpeakerMapping(jobId, participants);
        }
        showToast("Speaker mapping confirmed.", "emerald");

        if (typeof addProvenanceRecord === "function") {
            addProvenanceRecord(
                "Speaker Mapping",
                `Confirmed canonical speaker identities for ${jobIds.length} file(s).`,
                "user"
            );
        }

        // Rebuild Workspace lines so Q/A + colloquy reflect the mapping.
        if (typeof loadTranscriptResultsIntoWorkspace === "function") {
            await loadTranscriptResultsIntoWorkspace(jobIds);
        }
        goToStage(3);
    } catch (err) {
        console.error("Saving speaker mapping failed:", err);
        showToast("Could not save the speaker mapping. See console.", "red");
        if (btn) { btn.disabled = false; btn.textContent = "Confirm Mapping & Continue →"; }
    }
}

// Self-register: render whenever the router loads this screen.
window.addEventListener("screen:loaded", (e) => {
    if (e.detail && e.detail.stageNum === "2b") {
        // Keep the Transcripts tab visually active for this sub-step.
        const tab2 = document.getElementById("stageTab2");
        if (tab2) {
            tab2.className = "px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 shadow-sm";
        }
        _smLoad();
    }
});

// Expose handlers used from inline markup.
window._smSetAssignment = _smSetAssignment;
window.confirmSpeakerMapping = confirmSpeakerMapping;
