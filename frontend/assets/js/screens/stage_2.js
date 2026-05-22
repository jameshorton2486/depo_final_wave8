/**
 * Stage 2 — Transcripts Engine (Wave 1–3, server-backed).
 *
 * Pre-recorded ingestion, transcript persistence, and the read-back
 * terminal now run against the real FastAPI backend (/api/transcripts/*):
 *
 *   - Files upload as multipart form data and queue a transcription job.
 *   - The browser polls each job's status until it completes.
 *   - Completed transcripts are loaded into state.transcriptLines from
 *     the canonical word/utterance objects, then handed to Stage 3.
 *   - The read-back terminal searches persisted utterances server-side.
 *
 * The live Zoom streaming section (Mode A) remains a front-end
 * SIMULATION — real Zoom RTMS streaming is Wave 4 and deliberately
 * deferred per the Screen 2 build plan.
 */

// ====================================================================
// PRE-RECORDED INGESTION QUEUE
// ====================================================================

// Map a backend job status to a coarse progress percentage. Deepgram
// batch ASR does not stream fine-grained progress, so status-based
// stepping is the honest representation.
const JOB_STATUS_PROGRESS = {
    queued: 8,
    preprocessing: 30,
    transcribing: 65,
    assembling: 88,
    completed: 100,
    failed: 100,
};

const JOB_STATUS_LABEL = {
    queued: "Queued",
    preprocessing: "Preprocessing",
    transcribing: "Transcribing",
    assembling: "Assembling",
    completed: "Completed",
    failed: "Failed",
};

function addFilesToIngestionQueue(input) {
    if (input.files && input.files.length) {
        for (let i = 0; i < input.files.length; i++) {
            addSingleFileToQueue(input.files[i]);
        }
        showToast(`Added ${input.files.length} file(s) to the ingestion queue.`, "indigo");
    }
    // Allow re-selecting the same file later.
    input.value = "";
}

function addSingleFileToQueue(file) {
    const fileId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
    state.fileQueue.push({
        id: fileId,
        file: file,                       // the real File object, used for upload
        name: file.name,
        size: (file.size / (1024 * 1024)).toFixed(1) + " MB",
        status: "Awaiting Ingestion",
        progress: 0,
        jobId: null,
        error: null,
    });
    renderFileQueue();
}

function moveQueueItem(index, direction) {
    if (state.isQueueProcessing) return;
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= state.fileQueue.length) return;
    const temp = state.fileQueue[index];
    state.fileQueue[index] = state.fileQueue[targetIndex];
    state.fileQueue[targetIndex] = temp;
    renderFileQueue();
    showToast("Chronological sequence updated.");
}

function removeFileFromQueue(id) {
    if (state.isQueueProcessing) return;
    state.fileQueue = state.fileQueue.filter(f => f.id !== id);
    renderFileQueue();
    showToast("File removed from the queue.");
}

function clearAllQueues() {
    if (state.isQueueProcessing) {
        showToast("Cannot reset while ingestion is running.", "amber");
        return;
    }
    state.fileQueue = [];
    renderFileQueue();
    showToast("Ingestion queue reset.");
}

function renderFileQueue() {
    const list = document.getElementById('sequentialQueueList');
    const submitBtn = document.getElementById('btnIngestQueue');
    if (!list || !submitBtn) return;
    list.innerHTML = "";

    if (state.fileQueue.length === 0) {
        list.innerHTML = `<p class="text-xs text-slate-600 italic text-center py-4 bg-slate-950/40 rounded-xl border border-slate-850 font-sans">In-order queue is empty. Browse audio/video files above.</p>`;
        submitBtn.disabled = true;
        return;
    }

    submitBtn.disabled = state.isQueueProcessing;

    state.fileQueue.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = "flex flex-col bg-slate-950 p-3 rounded-xl border border-slate-850 hover:border-slate-800 transition-all text-xs gap-2";

        let badgeColor = "text-slate-400 bg-slate-900 border border-slate-800";
        if (file.status === "Completed") badgeColor = "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20";
        else if (file.status === "Failed") badgeColor = "text-red-400 bg-red-500/10 border border-red-500/20";
        else if (file.status !== "Awaiting Ingestion") badgeColor = "text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 animate-pulse";

        const isFirst = index === 0;
        const isLast = index === state.fileQueue.length - 1;
        const showBar = file.progress > 0 || file.status === "Completed";

        item.innerHTML = `
            <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-5 h-5 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-[10px] font-bold text-slate-400 shrink-0">
                        ${index + 1}
                    </div>
                    <div class="truncate">
                        <p class="font-mono text-white truncate max-w-xs md:max-w-md">${file.name}</p>
                        <p class="text-[10px] text-slate-500">${file.size}${file.error ? ` — <span class="text-red-400">${file.error}</span>` : ''}</p>
                    </div>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                    <div class="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 mr-1">
                        <button onclick="moveQueueItem(${index}, -1)" ${isFirst || state.isQueueProcessing ? 'disabled style="opacity:0.3"' : ''} class="p-1 hover:text-white text-slate-500 transition-all font-bold text-[10px]" title="Move Up">▲</button>
                        <div class="w-px h-3 bg-slate-800 mx-0.5"></div>
                        <button onclick="moveQueueItem(${index}, 1)" ${isLast || state.isQueueProcessing ? 'disabled style="opacity:0.3"' : ''} class="p-1 hover:text-white text-slate-500 transition-all font-bold text-[10px]" title="Move Down">▼</button>
                    </div>
                    <span class="px-2 py-0.5 rounded text-[9px] font-semibold uppercase ${badgeColor}">${file.status}</span>
                    <button onclick="removeFileFromQueue('${file.id}')" ${state.isQueueProcessing ? 'disabled style="opacity:0.3"' : ''} class="text-slate-500 hover:text-red-400 p-1 font-bold text-sm transition-all" title="Remove File">&times;</button>
                </div>
            </div>
            ${showBar ? `
            <div class="w-full bg-slate-900 h-1 rounded-full overflow-hidden mt-1">
                <div class="${file.status === 'Failed' ? 'bg-red-500' : 'bg-indigo-500'} h-full transition-all duration-300" style="width: ${file.progress}%"></div>
            </div>` : ''}
        `;
        list.appendChild(item);
    });
}

// --------------------------------------------------------------------
// Real sequential ingestion: upload each file, poll its job to completion
// --------------------------------------------------------------------
async function startSequentialIngestion() {
    if (!window.api) {
        showToast("API client unavailable — cannot reach the transcription backend.", "red");
        return;
    }
    if (state.fileQueue.length === 0 || state.isQueueProcessing) return;

    state.isQueueProcessing = true;
    const submitBtn = document.getElementById('btnIngestQueue');
    if (submitBtn) submitBtn.disabled = true;

    const logs = document.getElementById('sequentialLogs');
    const progressContainer = document.getElementById('sequentialProgressBar');
    const fill = document.getElementById('queueProgressFill');
    const percentLabel = document.getElementById('queueProgressPercent');
    const label = document.getElementById('queueProgressLabel');
    const statTimeElapsed = document.getElementById('statTimeElapsed');
    const statTimeRemaining = document.getElementById('statTimeRemaining');
    const statSpeedRatio = document.getElementById('statSpeedRatio');

    if (logs) { logs.classList.remove('hidden'); logs.innerHTML = ""; }
    if (progressContainer) progressContainer.classList.remove('hidden');

    const log = (msg, cls) => {
        if (!logs) return;
        const p = document.createElement('p');
        p.className = cls || "text-slate-400";
        p.innerText = `> ${msg}`;
        logs.appendChild(p);
        logs.scrollTop = logs.scrollHeight;
    };

    log("Initializing chronological ingestion pipeline...", "text-indigo-400");

    const startedAt = Date.now();
    const elapsedTimer = setInterval(() => {
        if (statTimeElapsed) {
            statTimeElapsed.innerText = `${((Date.now() - startedAt) / 1000).toFixed(1)}s`;
        }
    }, 100);

    const total = state.fileQueue.length;
    const completedJobIds = [];
    let failures = 0;

    for (let i = 0; i < total; i++) {
        const item = state.fileQueue[i];
        if (label) label.innerText = `Ingesting file ${i + 1} of ${total}: ${item.name}`;

        const setAggregate = (fileProgress) => {
            const aggregate = ((i * 100) + fileProgress) / (total * 100) * 100;
            if (fill) fill.style.width = `${aggregate}%`;
            if (percentLabel) percentLabel.innerText = `${Math.round(aggregate)}%`;
        };

        try {
            // --- 1. Upload ------------------------------------------------
            item.status = "Uploading…";
            item.progress = 4;
            renderFileQueue();
            setAggregate(4);
            log(`Uploading ${item.name} to the transcription backend...`);

            const job = await window.api.uploadTranscriptFile(item.file, {
                caseId: state.caseId || null,
                sequenceIndex: i,
            });
            item.jobId = job.job_id;
            log(`Job ${job.job_id.slice(0, 8)} queued for ${item.name}.`, "text-slate-500");

            // --- 2. Poll the job until it finishes ------------------------
            const finalJob = await pollTranscriptJob(job.job_id, (polled) => {
                const pct = JOB_STATUS_PROGRESS[polled.status] || 10;
                item.status = JOB_STATUS_LABEL[polled.status] || "Processing";
                item.progress = pct;
                renderFileQueue();
                setAggregate(pct);
                if (statSpeedRatio) statSpeedRatio.innerText = JOB_STATUS_LABEL[polled.status] || "—";
            });

            if (finalJob.status === "completed") {
                item.status = "Completed";
                item.progress = 100;
                completedJobIds.push(finalJob.job_id);
                const engine = finalJob.transcription_source === "deepgram"
                    ? "Deepgram Nova-3" : "offline fallback";
                log(`Completed ${item.name}: ${finalJob.word_count} words, ${finalJob.speaker_count} speakers (${engine}).`, "text-emerald-400 font-semibold");
            } else {
                throw new Error(finalJob.error_message || "Transcription failed.");
            }
        } catch (err) {
            failures++;
            item.status = "Failed";
            item.progress = 100;
            item.error = err.message;
            log(`Failed ${item.name}: ${err.message}`, "text-red-400 font-semibold");
            console.error("Ingestion failed for", item.name, err);
        }
        renderFileQueue();
        setAggregate(100);
    }

    clearInterval(elapsedTimer);
    state.isQueueProcessing = false;
    if (submitBtn) submitBtn.disabled = false;
    if (statTimeRemaining) statTimeRemaining.innerText = "Completed";
    if (statSpeedRatio) {
        statSpeedRatio.className = "text-emerald-400 font-bold";
        statSpeedRatio.innerText = failures ? `${failures} failed` : "All transcripts synced";
    }

    addProvenanceRecord(
        "Transcript Ingestion",
        `Processed ${completedJobIds.length}/${total} media file(s) into the canonical transcript layer.`,
        "system"
    );

    await refreshServerTranscriptJobs();

    if (completedJobIds.length === 0) {
        showToast("No files were transcribed successfully. Check the log.", "red");
        return;
    }

    showToast(`${completedJobIds.length} transcript(s) ingested. Loading workspace…`, "emerald");
    state.activeTranscriptJobIds = completedJobIds.slice();
    await loadTranscriptResultsIntoWorkspace(completedJobIds);
    setTimeout(() => goToStage("2b"), 900);
}

/**
 * Poll a transcript job until it reaches a terminal status.
 * Calls onUpdate(job) after every poll. Resolves with the final job.
 */
function pollTranscriptJob(jobId, onUpdate) {
    // The backend allows Deepgram up to 600s, and large depositions
    // (100 MB+ audio) legitimately take that long. Poll every 3s with
    // a 20-minute ceiling so the UI never gives up before the backend.
    const POLL_MS = 3000;
    const MAX_POLLS = 400;          // 3s x 400 = 20-minute ceiling
    let polls = 0;

    return new Promise((resolve, reject) => {
        const tick = async () => {
            try {
                const job = await window.api.getTranscriptJob(jobId);
                if (typeof onUpdate === "function") onUpdate(job);
                if (job.status === "completed" || job.status === "failed") {
                    resolve(job);
                    return;
                }
                if (++polls >= MAX_POLLS) {
                    // The job is NOT necessarily failed -- the backend may
                    // still be transcribing. Tell the user it is still
                    // running and can be picked up from the job list.
                    reject(new Error(
                        "Still transcribing after 20 minutes. The job is " +
                        "likely still running on the backend — check the " +
                        "transcript job list in a few minutes; do not re-upload."
                    ));
                    return;
                }
                setTimeout(tick, POLL_MS);
            } catch (err) {
                reject(err);
            }
        };
        tick();
    });
}

/**
 * Load completed transcript jobs into state.transcriptLines so the
 * Stage 3 Workspace renders real testimony. Builds lines from the
 * canonical utterance objects; speaker labels come from the speaker map.
 */
async function loadTranscriptResultsIntoWorkspace(jobIds) {
    const lines = [];
    let runningIndex = 0;

    for (let j = 0; j < jobIds.length; j++) {
        let content;
        try {
            content = await window.api.getTranscriptContent(jobIds[j]);
        } catch (err) {
            console.error("Could not load transcript content for", jobIds[j], err);
            continue;
        }

        const speakerNames = {};
        (content.speakers || []).forEach(s => {
            speakerNames[s.speaker_index] = s.assigned_name || s.speaker_label;
        });

        // Canonical participant directory: raw diarization index -> Q/A
        // mode and confirmed name. Populated once the reporter completes
        // the Speaker Mapping step. Until then every line is neutral
        // colloquy -- the app no longer guesses Q/A from speaker index.
        const qaByIndex = {};
        const nameByIndex = {};
        (content.participants || []).forEach(p => {
            const mode = p.role === "examining_attorney" ? "Q"
                       : p.role === "witness" ? "A" : "colloquy";
            (p.speaker_indices || []).forEach(idx => {
                qaByIndex[idx] = mode;
                if (p.name) nameByIndex[idx] = p.name;
            });
        });

        // A divider between media files keeps multi-session batches clear.
        if (jobIds.length > 1) {
            lines.push({
                id: `job-divider-${content.job.job_id}`,
                index: ++runningIndex,
                speaker: "SYSTEM INDEXER",
                text: `======= MEDIA FILE: ${content.job.source_filename} =======`,
                type: "text",
                confidence: 1.0,
                hasSuggestion: false,
                duration: 0.0,
            });
        }

        (content.utterances || []).forEach(utt => {
            lines.push({
                id: utt.utterance_id,
                index: ++runningIndex,
                jobId: content.job.job_id,
                speaker: nameByIndex[utt.speaker_index]
                    || speakerNames[utt.speaker_index] || utt.speaker_label,
                speakerIndex: utt.speaker_index,
                text: utt.text,
                // Q/A and colloquy come from the reporter-confirmed
                // Speaker Mapping step -- never from a raw speaker index.
                type: qaByIndex[utt.speaker_index] || "colloquy",
                confidence: utt.avg_confidence != null ? utt.avg_confidence : 0.95,
                hasSuggestion: false,
                duration: Math.max(0, (utt.end_time || 0) - (utt.start_time || 0)),
                startTime: utt.start_time,
            });
        });
    }

    if (lines.length > 0) {
        state.transcriptLines = lines;
        state.focusedLineId = lines[0].id;
        if (typeof compileAndRenderTranscript === "function") compileAndRenderTranscript();
        if (typeof updateStatsBar === "function") updateStatsBar();
        // Bind the Workspace to the first job so its AI review queue
        // knows which job it operates on. Speaker assignment is done on
        // Step 2B. (Single-job batches are the common case; multi-job
        // uses job 1.)
        if (typeof loadWorkspaceJobContext === "function" && jobIds.length > 0) {
            loadWorkspaceJobContext(jobIds[0]);
        }
    }
}

// ====================================================================
// PERSISTED TRANSCRIPT SESSIONS (server-side job list)
// ====================================================================

async function refreshServerTranscriptJobs() {
    if (!window.api) return;
    try {
        const listing = await window.api.listTranscriptJobs(state.caseId || null);
        state.transcriptJobs = (listing && listing.jobs) || [];
    } catch (err) {
        console.warn("Could not load transcript jobs:", err);
        state.transcriptJobs = [];
    }
    renderServerTranscriptJobs();
}

function renderServerTranscriptJobs() {
    const list = document.getElementById('serverJobsList');
    if (!list) return;

    const jobs = state.transcriptJobs || [];
    if (jobs.length === 0) {
        list.innerHTML = `<p class="text-xs text-slate-600 italic text-center py-6 font-sans">No transcripts ingested yet. Process a media file above.</p>`;
        updateEngineModeBadge(null);
        return;
    }

    // Surface whether real Deepgram or the offline fallback produced
    // these transcripts.
    const usedFallback = jobs.some(j => j.transcription_source === "offline-fallback");
    updateEngineModeBadge(usedFallback ? "fallback" : "deepgram");

    list.innerHTML = "";
    jobs.forEach(job => {
        const statusStyles = {
            completed: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
            failed: "text-red-400 bg-red-500/10 border-red-500/20",
            queued: "text-slate-400 bg-slate-900 border-slate-800",
        };
        const style = statusStyles[job.status] || "text-indigo-400 bg-indigo-500/10 border-indigo-500/20";
        const done = job.status === "completed";
        const dur = job.duration_seconds ? `${Math.round(job.duration_seconds)}s` : "—";
        const conf = job.avg_confidence != null ? `${Math.round(job.avg_confidence * 100)}%` : "—";

        const card = document.createElement('div');
        card.className = "bg-slate-950 border border-slate-850 rounded-xl p-3 flex flex-col gap-2";
        card.innerHTML = `
            <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                    <p class="font-mono text-xs text-white truncate">${job.source_filename}</p>
                    <p class="text-[10px] text-slate-500 font-mono">
                        ${job.word_count} words · ${job.speaker_count} speakers · ${dur} · conf ${conf}
                    </p>
                </div>
                <span class="px-2 py-0.5 rounded text-[9px] font-semibold uppercase border ${style} shrink-0">${job.status}</span>
            </div>
            ${job.status === "failed" && job.error_message ? `<p class="text-[10px] text-red-400 font-mono">${job.error_message}</p>` : ''}
            <div class="flex items-center gap-2 pt-1 border-t border-slate-900">
                <span class="text-[9px] uppercase tracking-wider font-semibold ${job.transcription_source === 'deepgram' ? 'text-emerald-500' : 'text-amber-500'}">
                    ${job.transcription_source === 'deepgram' ? 'Deepgram Nova-3' : (job.transcription_source || 'pending')}
                </span>
                <div class="flex-1"></div>
                <button onclick="viewTranscriptJob('${job.job_id}')" ${done ? '' : 'disabled style="opacity:0.4"'}
                    class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-[10px] font-semibold transition-all">
                    Open in Workspace
                </button>
                <button onclick="deleteServerTranscriptJob('${job.job_id}')"
                    class="px-2 py-1 text-slate-500 hover:text-red-400 text-[10px] font-semibold transition-all">
                    Delete
                </button>
            </div>
        `;
        list.appendChild(card);
    });
}

function updateEngineModeBadge(mode) {
    const badge = document.getElementById('engineModeBadge');
    if (!badge) return;
    if (mode === "deepgram") {
        badge.textContent = "Deepgram Nova-3 connected";
        badge.className = "text-[10px] font-semibold px-2 py-0.5 rounded border text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
    } else if (mode === "fallback") {
        badge.textContent = "Offline fallback — set DEEPGRAM_API_KEY for live ASR";
        badge.className = "text-[10px] font-semibold px-2 py-0.5 rounded border text-amber-400 bg-amber-500/10 border-amber-500/20";
    } else {
        badge.textContent = "Deepgram Nova-3 · batch ingestion";
        badge.className = "text-[10px] font-semibold px-2 py-0.5 rounded border text-slate-400 bg-slate-900 border-slate-800";
    }
}

async function viewTranscriptJob(jobId) {
    showToast("Loading transcript…", "indigo");
    state.activeTranscriptJobIds = [jobId];
    await loadTranscriptResultsIntoWorkspace([jobId]);
    goToStage("2b");
}

async function deleteServerTranscriptJob(jobId) {
    if (!window.api) return;
    try {
        await window.api.deleteTranscriptJob(jobId);
        showToast("Transcript job deleted.", "emerald");
        await refreshServerTranscriptJobs();
    } catch (err) {
        showToast(`Delete failed: ${err.message}`, "red");
    }
}

// ====================================================================
// LIVE READ-BACK TERMINAL (server-backed, debounced)
// ====================================================================

function executeReadbackSearch(query) {
    state.liveSearchQuery = (query || "").trim();
    if (state.readbackTimer) clearTimeout(state.readbackTimer);
    // Debounce so we do not fire a request on every keystroke.
    state.readbackTimer = setTimeout(() => runReadbackSearch(state.liveSearchQuery), 280);
}

async function runReadbackSearch(query) {
    const resultsBox = document.getElementById('readBackResultsContainer');
    if (!resultsBox) return;

    if (!query) {
        resultsBox.innerHTML = `<p class="text-[10px] text-slate-500 text-center py-24 italic font-sans">Search persisted transcripts above to check the record.</p>`;
        return;
    }

    let matches = [];
    let usedServer = true;
    try {
        const result = await window.api.readbackSearch(query, state.caseId || null);
        matches = (result && result.matches) || [];
    } catch (err) {
        // Graceful fallback: search whatever is already in the workspace.
        usedServer = false;
        console.warn("Readback server search failed, using local fallback:", err);
        matches = (state.transcriptLines || [])
            .filter(l => (l.text || "").toLowerCase().includes(query.toLowerCase()))
            .map(l => ({
                speaker_label: l.speaker,
                text: l.text,
                start_time: l.startTime || 0,
                source_filename: "current workspace",
                _localId: l.id,
            }));
    }

    if (matches.length === 0) {
        resultsBox.innerHTML = `<p class="text-[10px] text-slate-500 text-center py-12 italic">No matches found for "${query}".</p>`;
        return;
    }

    resultsBox.innerHTML = "";
    if (!usedServer) {
        const note = document.createElement('p');
        note.className = "text-[9px] text-amber-500 italic mb-1";
        note.innerText = "Offline — searching current workspace only.";
        resultsBox.appendChild(note);
    }

    matches.forEach(match => {
        const tStamp = match.start_time
            ? `${Math.floor(match.start_time / 60)}:${String(Math.floor(match.start_time % 60)).padStart(2, '0')}`
            : "—";
        const item = document.createElement('div');
        item.className = "bg-slate-900 border border-slate-850 p-2 rounded-lg hover:border-red-500 transition-all";
        item.innerHTML = `
            <div class="flex items-center justify-between text-[9px] font-mono mb-1">
                <span class="text-indigo-400 font-semibold">${match.speaker_label || 'Speaker'}</span>
                <span class="text-slate-500">@ ${tStamp}</span>
            </div>
            <p class="text-[11px] text-slate-300 font-mono leading-relaxed">"${highlightQuery(match.text, query)}"</p>
            <p class="text-[9px] text-slate-600 font-mono mt-1 truncate">${match.source_filename || ''}</p>
        `;
        resultsBox.appendChild(item);
    });
}

function highlightQuery(text, query) {
    if (!text || !query) return text || "";
    try {
        const safe = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return text.replace(new RegExp(`(${safe})`, 'gi'),
            '<span class="bg-red-500/30 text-white rounded px-0.5">$1</span>');
    } catch (_) {
        return text;
    }
}

// ====================================================================
// SIGNAL DIAGNOSTICS (local mic test — unchanged utility)
// ====================================================================

function testGainAndAudio() {
    const container = document.getElementById('liveGainContainer');
    if (!container) return;
    container.classList.remove('hidden');
    showToast("Testing local sound card gain levels…", "indigo");

    let ticks = 0;
    const timer = setInterval(() => {
        const randomGain = -10 - Math.random() * 45;
        const fillPercent = Math.max(10, 100 + (randomGain * 1.5));
        const fillEl = document.getElementById('gainLevelFill');
        const dbEl = document.getElementById('dbValueLabel');
        const dot = document.getElementById('micDiagnosticLevel');
        if (fillEl) fillEl.style.width = `${fillPercent}%`;
        if (dbEl) dbEl.innerText = `${randomGain.toFixed(1)} dBFS`;
        if (dot) {
            if (randomGain > -15) dot.className = "w-1.5 h-1.5 rounded-full bg-red-500 animate-ping";
            else if (randomGain > -35) dot.className = "w-1.5 h-1.5 rounded-full bg-emerald-500";
            else dot.className = "w-1.5 h-1.5 rounded-full bg-amber-500";
        }
        if (++ticks > 40) {
            clearInterval(timer);
            container.classList.add('hidden');
            showToast("Signal diagnostics complete.", "emerald");
        }
    }, 100);
}

// ====================================================================
// LIVE ZOOM STREAMING — Wave 4 SIMULATION (deferred per build plan)
// Real Zoom RTMS streaming is not implemented yet; this section keeps
// a faithful UI preview so the workflow is demonstrable.
// ====================================================================

async function requestMicPermissions() {
    try {
        if (!state.audioContext) {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            state.micStream = stream;
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            state.audioContext = new AudioContextClass();
            state.audioAnalyser = state.audioContext.createAnalyser();
            const source = state.audioContext.createMediaStreamSource(stream);
            source.connect(state.audioAnalyser);
            state.audioAnalyser.fftSize = 32;
        }
    } catch (err) {
        showToast("Microphone capture unavailable. Running in simulation mode.", "amber");
    }
}

function startZoomStreaming() {
    state.isStreaming = true;
    const btnStart = document.getElementById('btnStartStream');
    const btnStop = document.getElementById('btnStopStream');
    if (btnStart) { btnStart.disabled = true; btnStart.style.opacity = 0.5; }
    if (btnStop) { btnStop.disabled = false; btnStop.style.opacity = 1.0; }

    const glow = document.getElementById('liveStreamWaveGlow');
    if (glow) { glow.classList.remove('opacity-0'); glow.classList.add('opacity-100'); }
    const header = document.getElementById('zoomStatusHeader');
    if (header) {
        header.innerText = "Streaming (simulated)…";
        header.className = "text-xs font-bold text-red-500 flex items-center gap-1.5 justify-center md:justify-start animate-pulse";
    }
    const ts = document.getElementById('liveTimestamp');
    if (ts) ts.classList.remove('hidden');

    showToast("Live stream simulation active (real Zoom RTMS is Wave 4).", "red");
    addProvenanceRecord("Zoom Stream (Simulated)", "Live streaming preview started.", "system");

    runAudioVisualizerAnimation();
    runLiveTestimonySimulation();
}

function stopZoomStreaming() {
    state.isStreaming = false;
    const btnStart = document.getElementById('btnStartStream');
    const btnStop = document.getElementById('btnStopStream');
    if (btnStart) { btnStart.disabled = false; btnStart.style.opacity = 1.0; }
    if (btnStop) { btnStop.disabled = true; btnStop.style.opacity = 0.5; }

    const glow = document.getElementById('liveStreamWaveGlow');
    if (glow) glow.classList.add('opacity-0');
    const header = document.getElementById('zoomStatusHeader');
    if (header) {
        header.innerText = "Stream Disconnected";
        header.className = "text-xs font-bold text-slate-400";
    }
    const ts = document.getElementById('liveTimestamp');
    if (ts) ts.classList.add('hidden');

    clearInterval(state.visualizerTimer);
    showToast("Live stream simulation stopped.");
}

function runAudioVisualizerAnimation() {
    const visualizerBars = document.getElementById('visualizerBars');
    if (!visualizerBars) return;
    const dataArray = new Uint8Array(state.audioAnalyser ? state.audioAnalyser.frequencyBinCount : 16);

    state.visualizerTimer = setInterval(() => {
        let amplitude = 25;
        if (state.audioAnalyser) {
            state.audioAnalyser.getByteFrequencyData(dataArray);
            amplitude = dataArray.reduce((acc, v) => acc + v, 0) / dataArray.length;
        } else {
            amplitude = 15 + Math.random() * 40;
        }
        const scale = Math.max(10, Math.min(amplitude, 60));
        visualizerBars.setAttribute('d', `M50,${50 - scale/2} L50,${50 + scale/2} M35,${50 - scale/3} L35,${50 + scale/3} M65,${50 - scale/3} L65,${50 + scale/3}`);
        const ts = document.getElementById('liveTimestamp');
        if (ts) ts.innerText = new Date().toLocaleTimeString();
    }, 100);
}

function runLiveTestimonySimulation() {
    const container = document.getElementById('liveStreamTextContainer');
    if (!container) return;
    container.innerHTML = "";
    let idx = 0;

    const liveSentences = [
        "VANCE: Please state your occupation, Doctor.",
        "LEIFER: I am a board-certified neurosurgeon at Houston Neurological.",
        "VANCE: And you reviewed the MRI scans of Ms. Sarah Jenkins?",
        "LEIFER: Yes. We identified a sizable acoustic neuroma.",
    ];

    const simInterval = setInterval(() => {
        if (!state.isStreaming) { clearInterval(simInterval); return; }
        if (idx < liveSentences.length) {
            const p = document.createElement('p');
            p.className = "border-l-2 border-red-500 pl-2 py-1 bg-slate-900/40 rounded transition-all";
            p.innerHTML = `<span class="text-[9px] text-slate-500 block">${new Date().toLocaleTimeString()}</span> ${liveSentences[idx]}`;
            container.appendChild(p);
            container.scrollTop = container.scrollHeight;
            idx++;
        } else {
            clearInterval(simInterval);
        }
    }, 3000);
}

// ====================================================================
// Exports (functions are invoked from inline onclick handlers)
// ====================================================================
window.addFilesToIngestionQueue = addFilesToIngestionQueue;
window.addSingleFileToQueue = addSingleFileToQueue;
window.moveQueueItem = moveQueueItem;
window.renderFileQueue = renderFileQueue;
window.removeFileFromQueue = removeFileFromQueue;
window.clearAllQueues = clearAllQueues;
window.startSequentialIngestion = startSequentialIngestion;
window.pollTranscriptJob = pollTranscriptJob;
window.loadTranscriptResultsIntoWorkspace = loadTranscriptResultsIntoWorkspace;
window.refreshServerTranscriptJobs = refreshServerTranscriptJobs;
window.renderServerTranscriptJobs = renderServerTranscriptJobs;
window.viewTranscriptJob = viewTranscriptJob;
window.deleteServerTranscriptJob = deleteServerTranscriptJob;
window.executeReadbackSearch = executeReadbackSearch;
window.testGainAndAudio = testGainAndAudio;
window.requestMicPermissions = requestMicPermissions;
window.startZoomStreaming = startZoomStreaming;
window.stopZoomStreaming = stopZoomStreaming;
window.runAudioVisualizerAnimation = runAudioVisualizerAnimation;
window.runLiveTestimonySimulation = runLiveTestimonySimulation;
