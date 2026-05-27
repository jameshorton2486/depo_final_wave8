        // The raw intake notes field starts empty. The court reporter
        // pastes a real scheduling note, or drops a NOD PDF, and the
        // parser fills the schema from that. No mock/sample data is
        // injected on load.

        // ---- Global error surface -------------------------------------
        // Catch uncaught errors and unhandled promise rejections so the
        // user is actually told something failed, instead of the UI
        // silently freezing while the error sits only in the console.
        window.addEventListener('error', function (event) {
            console.error('[DEPO-PRO] Uncaught error:', event.error || event.message);
            if (typeof showToast === 'function') {
                showToast(
                    'Something went wrong: ' + (event.message || 'unexpected error') +
                    '. Press F12 \u2192 Console for details.',
                    'red'
                );
            }
        });
        window.addEventListener('unhandledrejection', function (event) {
            var reason = event.reason;
            var msg = (reason && reason.message) ? reason.message : String(reason);
            console.error('[DEPO-PRO] Unhandled promise rejection:', reason);
            if (typeof showToast === 'function') {
                showToast('Request failed: ' + msg, 'red');
            }
        });

        // Window Initializer
        window.onload = function() {
            renderAllStateComponents();
            if (document.getElementById('validationSummaryBadge')) {
                checkSchemaValidationStatus();
            }
            hydrateFromServer();
        };

        function workspaceHasUnsavedChanges() {
            const saveState = state.workspaceSave || {};
            return !!(saveState.dirty || saveState.pending || saveState.saving);
        }

        function confirmDiscardWorkspaceChanges(message) {
            if (!workspaceHasUnsavedChanges()) return true;
            return window.confirm(
                message ||
                "You have unsaved transcript changes. Continue and discard local edits that have not been saved yet?"
            );
        }

        window.addEventListener('beforeunload', function (event) {
            if (!workspaceHasUnsavedChanges()) return;
            event.preventDefault();
            event.returnValue = 'You have unsaved transcript changes.';
            return event.returnValue;
        });

        function defaultStage1State() {
            return {
                rawIntakeNotes: '',
                keytermEntries: [],
                parserMetadata: {
                    appearances: [],
                    speaker_hints: [],
                    deepgram_config: {},
                    jurisdiction_type: 'texas_state',
                    location_type: 'unknown',
                    detected_types: [],
                    warnings: [],
                    field_sources: {},
                },
                workspace: {
                    sessions: {},
                },
            };
        }

        function resetVolatileCaseState() {
            if (state.workspaceSave && state.workspaceSave.timer) {
                clearTimeout(state.workspaceSave.timer);
            }
            if (typeof window.resetPlaybackTransport === 'function') {
                window.resetPlaybackTransport();
            }
            state.sessionId = null;
            state.reporterId = null;
            state.stage1 = defaultStage1State();
            state.correctionsMemory = [];
            state.provenance = [];
            state.activeTranscriptJobIds = [];
            state.workspaceJob = { jobId: null };
            state.workspaceSpeakerMapping = { jobs: [], assignments: {} };
            state.workspaceSnapshots = {
                jobId: null,
                items: [],
                selectedSnapshotId: null,
                lastLoadedAt: null,
            };
            state.certificationHistory = {
                jobId: null,
                packages: [],
                snapshots: [],
                lastLoadedAt: null,
                lastError: null,
            };
            state.workspaceSave = {
                dirty: false,
                pending: false,
                saving: false,
                lastSavedAt: null,
                lastError: null,
                timer: null,
            };
            state.transcriptLines = [];
            state.workspaceAudioDurations = {};
            state.workspaceTranscriptWordsByJob = {};
            state.playbackTransport = null;
            state.activePlayback = false;
            state.playbackSpeed = 1.0;
            state.exhibits = [];
            state.exhibitsMeta = {
                jobId: null,
                lastLoadedAt: null,
                lastSavedAt: null,
                lastError: null,
            };
            state.focusedLineId = null;
            const rawNotesField = document.getElementById('rawIntakeNotes');
            if (rawNotesField) rawNotesField.value = '';
            console.info('[DEPO-PRO] Cleared volatile case state');
        }

        async function hydrateStage1Artifacts(caseId) {
            if (!window.api || !caseId) return;
            try {
                const artifacts = await window.api.getStage1Artifacts(caseId);
                state.stage1 = {
                    ...defaultStage1State(),
                    rawIntakeNotes: artifacts.raw_intake_notes || '',
                    keytermEntries: artifacts.keyterms || [],
                    parserMetadata: {
                        ...defaultStage1State().parserMetadata,
                        ...(artifacts.parser_metadata || {}),
                    },
                    workspace: artifacts.workspace || { sessions: {} },
                };
                const rawNotesField = document.getElementById('rawIntakeNotes');
                if (rawNotesField) rawNotesField.value = state.stage1.rawIntakeNotes || '';
                console.info('[DEPO-PRO] Hydrated Stage 1 artifacts', {
                    caseId: caseId,
                    keytermCount: (state.stage1.keytermEntries || []).length,
                });
            } catch (err) {
                console.warn('[DEPO-PRO] Stage 1 artifact hydration failed', err);
                state.stage1 = defaultStage1State();
            }
        }

        // On startup, ask the backend for the most recent case. If there is one,
        // load it (and its session + reporter, if present) into state.caseInfo.
        // Silent no-op when the backend is unreachable or no cases exist yet.
        async function hydrateFromServer() {
            if (!window.api) {
                showToast("Workspace initialized. Texas UFM layout active.");
                return;
            }
            try {
                const listing = await window.api.listCases();
                refreshCasePicker(listing);
                if (listing && listing.count > 0) {
                    await loadCaseById(listing.cases[0].case_id, /*silent=*/false);
                } else {
                    showToast("Workspace initialized. Texas UFM layout active.");
                }
            } catch (err) {
                console.warn("Hydration failed:", err);
                showToast("Workspace initialized (offline mode — no server).", "amber");
            }
        }

        // Load one case fully (case + session + reporter) into state and re-render.
        async function loadCaseById(caseId, silent) {
            if (!window.api) return;
            try {
                if (!silent && !confirmDiscardWorkspaceChanges(
                    "You have unsaved transcript changes. Switch cases and discard any unsaved Stage 3 edits?"
                )) {
                    return;
                }
                resetVolatileCaseState();
                const caseRow = await window.api.getCase(caseId);
                state.caseId = caseRow.case_id;
                Object.assign(state.caseInfo, window.api.caseRowToCaseInfo(caseRow));

                // Sessions
                const sessList = await window.api.listSessionsForCase(caseId);
                if (sessList && sessList.count > 0) {
                    const sess = sessList.sessions[0];
                    state.sessionId = sess.session_id;
                    Object.assign(state.caseInfo, window.api.sessionRowToCaseInfoPatch(sess));

                    // Reporter (if linked)
                    if (sess.reporter_id) {
                        try {
                            const rep = await window.api.getReporter(sess.reporter_id);
                            state.reporterId = rep.reporter_id;
                            Object.assign(state.caseInfo, window.api.reporterRowToCaseInfoPatch(rep));
                        } catch (err) {
                            console.warn("Reporter load failed:", err);
                        }
                    }
                } else {
                    // No session yet — clear session-only fields
                    Object.assign(state.caseInfo, {
                        deponent: '', date: '', startTime: '', endTime: '',
                        address: '', custodialName: '', requestingParty: '',
                        csrName: '', csrLicense: '', firmReg: '', csrCertExp: '',
                    });
                }

                await hydrateStage1Artifacts(caseId);

                if (typeof hydrateUFMFormFromState === 'function') hydrateUFMFormFromState();
                if (typeof renderUFMTermsTable === 'function') renderUFMTermsTable();
                refreshCasePickerLabel();

                if (!silent) {
                    const label = caseRow.case_number_value || caseRow.case_id.slice(0, 8);
                    showToast(`Loaded case ${label}.`, "emerald");
                }
            } catch (err) {
                console.error("Failed to load case:", err);
                showToast(`Load failed: ${err.message}`, "red");
            }
        }

        // Discard current state and start a blank case (no server call until save).
        function newCase() {
            if (!confirmDiscardWorkspaceChanges(
                "You have unsaved transcript changes. Start a new case and discard any unsaved Stage 3 edits?"
            )) {
                return;
            }
            state.caseId = null;
            resetVolatileCaseState();
            Object.assign(state.caseInfo, {
                cause: '', caption: '', court: '', county: '', state: '',
                deponent: '', date: '', startTime: '', endTime: '',
                address: '', csrName: '', csrLicense: '', firmReg: '', csrCertExp: '',
                custodialName: '', requestingParty: '',
                signature: '', certified: false,
            });
            if (typeof hydrateUFMFormFromState === 'function') hydrateUFMFormFromState();
            if (typeof renderUFMTermsTable === 'function') renderUFMTermsTable();
            refreshCasePickerLabel();
            showToast("Started a new case. Fill in Stage 1 and click save.", "indigo");
        }

        // ----- Case picker UI -----

        function refreshCasePickerLabel() {
            const label = document.getElementById('casePickerLabel');
            if (!label) return;
            if (state.caseId && state.caseInfo.cause) {
                label.innerText = state.caseInfo.cause;
            } else if (state.caseId) {
                label.innerText = '(unnamed case)';
            } else {
                label.innerText = 'New case';
            }
        }

        async function refreshCasePicker(precomputedListing) {
            const dropdown = document.getElementById('casePickerDropdown');
            if (!dropdown) return;
            const itemsContainer = dropdown.querySelector('[data-case-list]');
            if (!itemsContainer) return;
            let listing = precomputedListing;
            if (!listing && window.api) {
                try {
                    listing = await window.api.listCases();
                } catch (err) {
                    itemsContainer.innerHTML = '<p class="text-xs text-red-400 px-3 py-2">Failed to load cases.</p>';
                    return;
                }
            }
            if (!listing || listing.count === 0) {
                itemsContainer.innerHTML = '<p class="text-xs text-slate-500 px-3 py-2 italic">No saved cases yet.</p>';
                refreshCasePickerLabel();
                return;
            }
            itemsContainer.innerHTML = '';
            listing.cases.forEach(c => {
                const active = c.case_id === state.caseId;
                const div = document.createElement('div');
                div.className = `px-3 py-2 cursor-pointer hover:bg-slate-800 transition-all ${active ? 'bg-indigo-500/10 border-l-2 border-indigo-500' : ''}`;
                div.innerHTML = `
                    <p class="text-xs font-semibold text-white truncate">${c.case_number_value || '(no cause)'}</p>
                    <p class="text-[10px] text-slate-500 truncate">${c.caption_full || ''}</p>
                `;
                div.addEventListener('click', () => {
                    document.getElementById('casePickerDropdown').classList.add('hidden');
                    loadCaseById(c.case_id, false);
                });
                itemsContainer.appendChild(div);
            });
            refreshCasePickerLabel();
        }

        function toggleCasePicker() {
            const dd = document.getElementById('casePickerDropdown');
            if (!dd) return;
            dd.classList.toggle('hidden');
            if (!dd.classList.contains('hidden')) {
                refreshCasePicker();
            }
        }

        // Complete state rendering dispatch
        function renderAllStateComponents() {
            if (document.getElementById('correctionsMemoryContainer')) renderCorrectionMemory();
            if (document.getElementById('provenanceLogContainer')) renderProvenanceTimeline();
            if (document.getElementById('transcriptLinesContainer')) compileAndRenderTranscript();
            if (document.getElementById('exhibitsIndexList')) renderExhibitsIndex();
            if (document.getElementById('flagCount')) updateStatsBar();
            if (document.getElementById('sequentialQueueList')) renderFileQueue();
            if (document.getElementById('ufmTermsTableBody')) renderUFMTermsTable();
        }


        async function goToStage(stageNum) {
            if (state.currentStage === 3 && stageNum !== 3 && !confirmDiscardWorkspaceChanges(
                "You have unsaved transcript changes. Leave Stage 3 and discard any edits that have not been saved yet?"
            )) {
                return;
            }
            if (state.currentStage === 3 && typeof window.persistWorkspaceTranscript === 'function') {
                const saveState = state.workspaceSave || {};
                if (saveState.timer) {
                    clearTimeout(saveState.timer);
                    saveState.timer = null;
                }
                if (saveState.pending || saveState.saving) {
                    await window.persistWorkspaceTranscript('stage_transition');
                }
            }

            // Update tab highlights
            for (let i = 1; i <= 6; i++) {
                const tab = document.getElementById(`stageTab${i}`);
                if (!tab) continue;
                if (i === stageNum) {
                    tab.className = "px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 shadow-sm";
                } else {
                    tab.className = "px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all text-slate-400 hover:text-slate-200 hover:bg-slate-800";
                }
            }
            state.currentStage = stageNum;
            loadScreen(stageNum);
            showToast(`Stage loaded: ${getStageName(stageNum)}`);
        }

        function updateStatsBar() {
            const suggestionsCount = Number.isInteger(state.reviewFlagCount)
                ? state.reviewFlagCount
                : state.transcriptLines.filter(l => l.hasSuggestion).length;
            const flagCount = document.getElementById('flagCount');
            if (!flagCount) return;
            flagCount.innerText = `${suggestionsCount} review flags`;
        }


        async function simulateSave() {
            // Name kept for backward compat with onclick handlers in index.html.
            // Now orchestrates saves across cases, sessions, and reporters.
            if (!window.api) {
                showToast("API client not loaded.", "red");
                return;
            }
            const cause = (state.caseInfo.cause || '').trim();
            if (!cause && !state.caseId) {
                showToast("Enter a Cause Number before saving.", "amber");
                return;
            }

            const summary = { case: null, session: null, reporter: null, errors: [] };

            // ----- 1. Case -----
            try {
                let savedCase;
                if (state.caseId) {
                    savedCase = await window.api.updateCase(state.caseId, state.caseInfo);
                    summary.case = "updated";
                } else {
                    savedCase = await window.api.createCase(state.caseInfo);
                    state.caseId = savedCase.case_id;
                    summary.case = "created";
                }
            } catch (err) {
                summary.errors.push(`case: ${err.message}`);
                console.error("Case save failed:", err);
                showToast(`Save failed (case): ${err.message}`, "red");
                return;  // Without a case_id we can't save the rest
            }

            // ----- 2. Reporter (Block 3) -----
            if (window.api.canSaveReporter(state.caseInfo)) {
                try {
                    if (state.reporterId) {
                        await window.api.updateReporter(state.reporterId, state.caseInfo);
                        summary.reporter = "updated";
                    } else {
                        const savedRep = await window.api.createReporter(state.caseInfo);
                        state.reporterId = savedRep.reporter_id;
                        summary.reporter = "created";
                    }
                } catch (err) {
                    summary.errors.push(`reporter: ${err.message}`);
                    console.error("Reporter save failed:", err);
                }
            }

            // ----- 3. Session (Block 2 + Block 4) -----
            if (window.api.canSaveSession(state.caseInfo)) {
                try {
                    if (state.sessionId) {
                        const body = window.api.caseInfoToSessionPayload(state.caseInfo, state.caseId);
                        body.reporter_id = state.reporterId;
                        delete body.case_id;
                        await fetch(`/api/sessions/${encodeURIComponent(state.sessionId)}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body),
                        }).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); });
                        summary.session = "updated";
                    } else {
                        const body = window.api.caseInfoToSessionPayload(state.caseInfo, state.caseId);
                        body.reporter_id = state.reporterId;
                        const r = await fetch('/api/sessions', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body),
                        });
                        if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
                        const saved = await r.json();
                        state.sessionId = saved.session_id;
                        summary.session = "created";
                    }
                } catch (err) {
                    summary.errors.push(`session: ${err.message}`);
                    console.error("Session save failed:", err);
                }
            }

            // ----- 4. Authoritative Stage 1 artifacts ----- 
            if (state.caseId) {
                try {
                    state.stage1.rawIntakeNotes = (document.getElementById('rawIntakeNotes') || {}).value || '';
                    const syncResult = await window.api.syncStage1Artifacts(state);
                    state.stage1.keytermEntries = (syncResult && syncResult.keyterms) || state.stage1.keytermEntries;
                    state.stage1.parserMetadata = (syncResult && syncResult.parser_metadata) || state.stage1.parserMetadata;
                    state.stage1.workspace = (syncResult && syncResult.workspace) || state.stage1.workspace;
                } catch (err) {
                    summary.errors.push(`stage1: ${err.message}`);
                    console.error("Stage 1 artifact sync failed:", err);
                }
            }

            // ----- Summary toast -----
            const parts = [];
            if (summary.case) parts.push(`case ${summary.case}`);
            if (summary.session) parts.push(`session ${summary.session}`);
            if (summary.reporter) parts.push(`reporter ${summary.reporter}`);
            const msg = parts.length
                ? `Saved: ${parts.join(', ')}.`
                : "Nothing to save.";
            showToast(msg, summary.errors.length ? "amber" : "emerald");
            if (summary.errors.length) {
                console.warn("Partial save with errors:", summary.errors);
            }
            addProvenanceRecord && addProvenanceRecord(
                "Persistence",
                msg + (summary.errors.length ? ` (warnings: ${summary.errors.length})` : ''),
                "system"
            );

            // Refresh the case picker if it's open / present
            if (typeof refreshCasePicker === 'function') {
                refreshCasePicker();
            }
        }

        window.addEventListener("screen:loaded", (e) => {
            const stageNum = e.detail.stageNum;
            // Re-bind handlers and re-render data into the freshly-mounted screen
            try {
                if (stageNum === 1) {
                    hydrateUFMFormFromState && hydrateUFMFormFromState();
                    renderUFMTermsTable && renderUFMTermsTable();
                    checkSchemaValidationStatus && checkSchemaValidationStatus();
                } else if (stageNum === 2) {
                    renderFileQueue && renderFileQueue();
                    renderServerTranscriptJobs && renderServerTranscriptJobs();
                    refreshServerTranscriptJobs && refreshServerTranscriptJobs();
                } else if (stageNum === 3) {
                    compileAndRenderTranscript && compileAndRenderTranscript();
                    renderCorrectionMemory && renderCorrectionMemory();
                    renderProvenanceTimeline && renderProvenanceTimeline();
                    renderWorkspaceSaveStatus && renderWorkspaceSaveStatus();
                    updateStatsBar && updateStatsBar();
                    loadWorkspaceSpeakerMapping && loadWorkspaceSpeakerMapping();
                    loadWorkspaceSnapshots && loadWorkspaceSnapshots();
                } else if (stageNum === 4) {
                    renderExhibitsIndex && renderExhibitsIndex();
                    loadWorkspaceExhibits && loadWorkspaceExhibits();
                } else if (stageNum === 5) {
                    loadCertFields && loadCertFields();
                    loadCertificationHistory && loadCertificationHistory();
                }
            } catch (err) {
                console.warn(`Render error for stage ${stageNum}:`, err);
            }
        });

window.renderAllStateComponents = renderAllStateComponents;
window.goToStage = goToStage;
window.updateStatsBar = updateStatsBar;
window.simulateSave = simulateSave;
window.hydrateFromServer = hydrateFromServer;
window.loadCaseById = loadCaseById;
window.newCase = newCase;
window.refreshCasePicker = refreshCasePicker;
window.refreshCasePickerLabel = refreshCasePickerLabel;
window.toggleCasePicker = toggleCasePicker;
window.resetVolatileCaseState = resetVolatileCaseState;
window.workspaceHasUnsavedChanges = workspaceHasUnsavedChanges;
