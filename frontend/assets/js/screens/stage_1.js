        // Canonical UFM field IDs. Must match backend intake_store.UFM_FIELD_IDS.
        const UFM_FIELD_IDS = [
            'ufmCause', 'ufmStyle', 'ufmCourt', 'ufmCounty', 'ufmState',
            'ufmWitness', 'ufmDate', 'ufmStartTime', 'ufmEndTime', 'ufmAddress',
            'ufmCSRName', 'ufmCSRLicense', 'ufmFirmReg', 'ufmCSRCertExp',
            'ufmCustodialName', 'ufmRequestingParty',
        ];

        const UFM_FIELD_LABELS = {
            ufmCause: 'Cause Number',
            ufmStyle: 'Full Caption / Style',
            ufmCourt: 'Court / Judicial District',
            ufmCounty: 'County of Venue',
            ufmState: 'State',
            ufmWitness: 'Deponent / Witness Name',
            ufmDate: 'Deposition Date',
            ufmStartTime: 'Start Time',
            ufmEndTime: 'End Time',
            ufmAddress: 'Deposition Address',
            ufmCSRName: 'CSR Officer Name',
            ufmCSRLicense: 'CSR License Number',
            ufmFirmReg: 'Firm Registration Number',
            ufmCSRCertExp: 'CSR License Expiration',
            ufmCustodialName: 'Custodial Attorney Name',
            ufmRequestingParty: 'Requesting Firm / Party',
        };

        function renderCaseContextBanner() {
            const banner = document.getElementById('caseContextBanner');
            if (!banner) return;
            const title = document.getElementById('caseContextBannerTitle');
            const subtitle = document.getElementById('caseContextBannerSubtitle');
            const btn = document.getElementById('caseContextBannerNewBtn');
            if (!title || !subtitle || !btn) return;

            if (state.caseId) {
                const cause = (state.caseInfo.cause || '').trim() || '(unnamed case)';
                const raw = state.caseInfo.updatedAt || '';
                let stamp = 'last saved unknown';
                if (raw) {
                    const d = new Date(raw);
                    if (!isNaN(d.getTime())) {
                        stamp = `last saved ${d.toISOString()}`;
                    }
                }
                title.innerText = 'EDITING EXISTING CASE';
                title.className = 'text-[10px] font-bold uppercase tracking-widest text-indigo-400';
                subtitle.innerText = `${cause} · ${stamp}`;
                banner.classList.remove('border-l-emerald-500');
                banner.classList.add('border-l-indigo-500');
                btn.classList.remove('hidden');
            } else {
                title.innerText = 'NEW CASE';
                title.className = 'text-[10px] font-bold uppercase tracking-widest text-emerald-400';
                subtitle.innerText = 'Fill in the fields below and click Save to create a case.';
                banner.classList.remove('border-l-indigo-500');
                banner.classList.add('border-l-emerald-500');
                btn.classList.add('hidden');
            }
        }

        function normalizeStage1KeytermSource(source) {
            const src = String(source || 'manual').trim().toLowerCase();
            if (src === 'notice_parser') return 'nod_parser';
            return ['nod_parser', 'text_parser', 'learned', 'manual'].includes(src)
                ? src
                : 'manual';
        }

        function setRawIntakeNotesState(value) {
            state.stage1.rawIntakeNotes = value || '';
        }

        function buildStage1ParserMetadata(payload) {
            const meta = (payload && payload.metadata) || {};
            return {
                appearances: payload.appearances || [],
                speaker_hints: payload.speaker_hints || [],
                deepgram_config: payload.deepgram_config || {},
                jurisdiction_type: meta.jurisdiction_type || 'texas_state',
                location_type: meta.location_type || 'unknown',
                detected_types: meta.detected_types || [],
                warnings: meta.warnings || [],
                field_sources: meta.field_sources || {},
            };
        }

        function collectStage1KeytermEntries() {
            const rows = [];
            const seen = new Set();
            const add = (term, boost, category, source) => {
                if (!term) return;
                const clean = String(term).trim();
                if (!clean) return;
                const key = clean.toLowerCase();
                if (seen.has(key)) return;
                seen.add(key);
                rows.push({
                    term: clean,
                    boost: Number(boost || 1.0),
                    category: category || 'Term',
                    source: normalizeStage1KeytermSource(source),
                });
            };

            (state.stage1.keytermEntries || []).forEach(kt => {
                add(kt.term, kt.boost, kt.category, kt.source);
            });
            add(state.caseInfo.deponent, 1.5, 'Deponent', 'manual');
            add(state.caseInfo.csrName, 1.0, 'Reporter', 'manual');
            add(state.caseInfo.custodialName, 1.2, 'Attorney', 'manual');
            add(state.caseInfo.requestingParty, 1.0, 'Firm', 'manual');
            return rows;
        }

        async function persistStage1ArtifactsIfBound(reason) {
            if (!window.api || !state.caseId || !state.sessionId) return null;
            state.stage1.rawIntakeNotes = (document.getElementById('rawIntakeNotes') || {}).value || state.stage1.rawIntakeNotes;
            state.stage1.keytermEntries = collectStage1KeytermEntries();
            try {
                const result = await window.api.syncStage1Artifacts(state);
                if (result && result.keyterms) {
                    state.stage1.keytermEntries = result.keyterms;
                }
                if (result && result.parser_metadata) {
                    state.stage1.parserMetadata = result.parser_metadata;
                }
                if (result && result.field_confirmations) {
                    state.stage1.field_confirmations = result.field_confirmations;
                }
                console.info('[DEPO-PRO] Stage 1 artifacts synchronized', {
                    reason: reason,
                    caseId: state.caseId,
                    sessionId: state.sessionId,
                    keytermCount: (state.stage1.keytermEntries || []).length,
                });
                return result;
            } catch (err) {
                console.warn('[DEPO-PRO] Stage 1 artifact sync failed', err);
                showToast(`Stage 1 sync failed: ${err.message}`, "amber");
                return null;
            }
        }

        function mergeStage1KeytermEntries(nextEntries) {
            const merged = [];
            const seen = new Set();
            [...(state.stage1.keytermEntries || []), ...(nextEntries || [])].forEach(kt => {
                if (!kt || !kt.term) return;
                const key = String(kt.term).trim().toLowerCase();
                if (!key || seen.has(key)) return;
                seen.add(key);
                merged.push({
                    term: kt.term,
                    boost: Number(kt.boost || 1.0),
                    category: kt.category || 'Term',
                    source: normalizeStage1KeytermSource(kt.source),
                });
            });
            state.stage1.keytermEntries = merged;
        }

        function applyParsedStage1Payload(payload) {
            const nextMeta = buildStage1ParserMetadata(payload);
            const mergedSources = {
                ...(state.stage1.parserMetadata.field_sources || {}),
                ...(nextMeta.field_sources || {}),
            };
            state.stage1.parserMetadata = {
                ...state.stage1.parserMetadata,
                ...nextMeta,
                field_sources: mergedSources,
                appearances: (nextMeta.appearances && nextMeta.appearances.length)
                    ? nextMeta.appearances
                    : state.stage1.parserMetadata.appearances,
                speaker_hints: (nextMeta.speaker_hints && nextMeta.speaker_hints.length)
                    ? nextMeta.speaker_hints
                    : state.stage1.parserMetadata.speaker_hints,
                deepgram_config: Object.keys(nextMeta.deepgram_config || {}).length
                    ? nextMeta.deepgram_config
                    : state.stage1.parserMetadata.deepgram_config,
            };
            mergeStage1KeytermEntries(payload.keyterms || []);
        }

        // Map UFM input ID → state.caseInfo key.
        const UFM_ID_TO_CASEINFO = {
            'ufmCause': 'cause',
            'ufmStyle': 'caption',
            'ufmCourt': 'court',
            'ufmCounty': 'county',
            'ufmState': 'state',
            'ufmWitness': 'deponent',
            'ufmDate': 'date',
            'ufmStartTime': 'startTime',
            'ufmEndTime': 'endTime',
            'ufmAddress': 'address',
            'ufmCSRName': 'csrName',
            'ufmCSRLicense': 'csrLicense',
            'ufmFirmReg': 'firmReg',
            'ufmCSRCertExp': 'csrCertExp',
            'ufmCustodialName': 'custodialName',
            'ufmRequestingParty': 'requestingParty',
        };

        function renderUFMValidationBadge(fieldId, badge, val) {
            // Three-state badge: MISSING (red) / AUTO-POPULATED (amber) / ✓ CONFIRMED (green).
            // Source and confirmation are two ORTHOGONAL axes. Source attribution
            // is preserved through persistence; the badge only depends on (value,
            // confirmed) per CLAUDE.md transparency rules — a parser-populated
            // value is never displayed as "verified" until the operator attests.
            if (!badge) return;
            const confirmed = state.stage1.field_confirmations
                && state.stage1.field_confirmations[fieldId] === 'confirmed';

            if (val === '') {
                badge.innerText = 'MISSING';
                badge.className = 'ufm-val-badge absolute right-2 top-6 text-[8px] px-1 py-0.2 rounded bg-red-500/10 text-red-400';
                badge.title = 'No value entered.';
                badge.style.cursor = 'default';
                badge.onclick = null;
            } else if (confirmed) {
                badge.innerText = '✓ CONFIRMED';
                badge.className = 'ufm-val-badge absolute right-2 top-6 text-[8px] px-1 py-0.2 rounded bg-emerald-500/10 text-emerald-400';
                badge.title = 'Operator-attested. Editing this field will clear the confirmation.';
                badge.style.cursor = 'default';
                badge.onclick = null;
            } else {
                badge.innerText = 'AUTO · CONFIRM?';
                badge.className = 'ufm-val-badge absolute right-2 top-6 text-[8px] px-1 py-0.2 rounded bg-amber-500/10 text-amber-400 cursor-pointer hover:bg-amber-500/20';
                badge.title = 'Value present but not yet attested by the operator. Click to confirm.';
                badge.style.cursor = 'pointer';
                badge.onclick = () => confirmUFMField(fieldId);
            }
        }

        function renderUFMInputBorder(inputEl, val) {
            const baseInput = inputEl.tagName === 'TEXTAREA'
                ? 'w-full bg-slate-900 text-xs px-2.5 py-1 rounded-lg text-white focus:outline-none h-12 leading-normal'
                : 'w-full bg-slate-900 text-xs px-2.5 py-1 rounded-lg text-white focus:outline-none';
            const confirmed = state.stage1.field_confirmations
                && state.stage1.field_confirmations[inputEl.id] === 'confirmed';
            let border;
            if (val === '') {
                border = 'border border-red-500/30';
            } else if (confirmed) {
                border = 'border border-emerald-500/30';
            } else {
                border = 'border border-amber-500/30';
            }
            // Preserve font-mono if it was on the original markup.
            const mono = inputEl.className.includes('font-mono') ? ' font-mono' : '';
            inputEl.className = `${baseInput} ${border}${mono}`;
        }

        function validateUFMField(inputEl, label) {
            const val = inputEl.value.trim();
            const badge = inputEl.parentElement.querySelector('.ufm-val-badge');
            const fieldId = inputEl.id;

            const stateField = UFM_ID_TO_CASEINFO[fieldId];
            if (stateField) {
                state.caseInfo[stateField] = val;
            }

            // Editing a confirmed field clears its confirmation. The check
            // runs on every input event; if the value is currently
            // different from what we have stored as confirmed, drop it.
            if (state.stage1.field_confirmations
                && state.stage1.field_confirmations[fieldId] === 'confirmed'
                && inputEl.dataset.confirmedValue !== undefined
                && inputEl.dataset.confirmedValue !== val) {
                delete state.stage1.field_confirmations[fieldId];
                delete inputEl.dataset.confirmedValue;
            }

            renderUFMInputBorder(inputEl, val);
            renderUFMValidationBadge(fieldId, badge, val);

            // Sync legacy global mirrors if present.
            if (stateField === 'caption') {
                const mirror = document.getElementById('caseCaption');
                if (mirror) mirror.value = val;
            }
            if (stateField === 'deponent') {
                const mirror = document.getElementById('caseDeponent');
                if (mirror) mirror.value = val;
            }

            checkSchemaValidationStatus();
        }

        function confirmUFMField(fieldId) {
            const el = document.getElementById(fieldId);
            if (!el) return;
            const val = el.value.trim();
            if (!val) return;  // can't confirm an empty field
            if (!state.stage1.field_confirmations) {
                state.stage1.field_confirmations = {};
            }
            state.stage1.field_confirmations[fieldId] = 'confirmed';
            el.dataset.confirmedValue = val;
            renderUFMInputBorder(el, val);
            const badge = el.parentElement.querySelector('.ufm-val-badge');
            renderUFMValidationBadge(fieldId, badge, val);
            checkSchemaValidationStatus();
            persistStage1ArtifactsIfBound('field-confirmed');
        }

        function confirmAllPopulatedUFMFields() {
            if (!state.stage1.field_confirmations) {
                state.stage1.field_confirmations = {};
            }
            let confirmed = 0;
            UFM_FIELD_IDS.forEach(fieldId => {
                const el = document.getElementById(fieldId);
                if (!el) return;
                const val = el.value.trim();
                if (!val) return;
                state.stage1.field_confirmations[fieldId] = 'confirmed';
                el.dataset.confirmedValue = val;
                renderUFMInputBorder(el, val);
                const badge = el.parentElement.querySelector('.ufm-val-badge');
                renderUFMValidationBadge(fieldId, badge, val);
                confirmed += 1;
            });
            checkSchemaValidationStatus();
            persistStage1ArtifactsIfBound('confirm-all');
            showToast(`Confirmed ${confirmed} populated field${confirmed === 1 ? '' : 's'}.`, 'emerald');
        }

        // Enumerate missing required fields and operator confirmations.
        // Deterministic, no graded score. Header is always `{N} of {R}
        // required fields populated`; body lists each missing field by
        // human-readable label (or, when all are populated, the count of
        // operator-confirmed values).
        function checkSchemaValidationStatus() {
            const summaryBadge = document.getElementById('validationSummaryBadge');
            const headerEl = document.getElementById('validationSummaryHeader');
            const listEl = document.getElementById('validationSummaryList');
            if (!summaryBadge || !headerEl || !listEl) return;

            const required = UFM_FIELD_IDS.length;
            const missing = [];
            let populated = 0;
            UFM_FIELD_IDS.forEach(id => {
                const el = document.getElementById(id);
                const val = el ? el.value.trim() : '';
                if (val === '') {
                    missing.push(UFM_FIELD_LABELS[id] || id);
                } else {
                    populated += 1;
                }
            });
            const confirmations = state.stage1.field_confirmations || {};
            const confirmed = UFM_FIELD_IDS.filter(id => confirmations[id] === 'confirmed').length;

            if (populated === required) {
                summaryBadge.className = 'text-[10px] rounded bg-emerald-500/5 border border-emerald-500/20 p-2 text-emerald-300';
                headerEl.className = 'font-bold text-emerald-400';
                headerEl.innerText = `✓ All required fields populated. ${confirmed} of ${required} confirmed by operator.`;
                listEl.innerHTML = '';
            } else {
                summaryBadge.className = 'text-[10px] rounded bg-red-500/5 border border-red-500/20 p-2 text-slate-300';
                headerEl.className = 'font-bold text-red-400';
                headerEl.innerText = `${populated} of ${required} required fields populated`;
                listEl.innerHTML = missing
                    .map(label => `<li class="text-slate-400">• ${label}</li>`)
                    .join('');
            }
        }

        // Run text-based parser on pasted intake notes (placeholder for future LLM call).
        // The real NOD parser endpoint (POST /api/nod/parse) is invoked via parseNODFile() instead.
        async function runAILegalParser() {
            const rawNotes = document.getElementById('rawIntakeNotes').value;
            if (!rawNotes.trim()) {
                showToast("Intake notes workspace is empty. Paste scheduling notes first.", "red");
                return;
            }
            setRawIntakeNotesState(rawNotes);

            showToast("Parsing pasted notes...", "cyan");
            addProvenanceRecord("Text Parser", "Parsing pasted intake notes.", "user");

            let payload;
            try {
                const res = await fetch(`/api/intake/parse-text`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: rawNotes }),
                });
                if (!res.ok) {
                    const errBody = await res.json().catch(() => ({}));
                    throw new Error(errBody.detail || `HTTP ${res.status}`);
                }
                payload = await res.json();
            } catch (err) {
                showToast(`Text parse failed: ${err.message}`, "red");
                addProvenanceRecord("Text Parser", `Parse failed: ${err.message}`, "system");
                return;
            }

            // Apply parsed fields to the UFM form
            applyParsedStage1Payload(payload);
            const fields = payload.fields || {};
            let populated = 0;
            for (const [id, value] of Object.entries(fields)) {
                const el = document.getElementById(id);
                if (el && value) {
                    el.value = value;
                    validateUFMField(el, id);
                    el.classList.add('animate-flash');
                    setTimeout(() => el.classList.remove('animate-flash'), 1500);
                    populated++;
                }
            }

            renderAllStateComponents();
            renderUFMTermsTable();
            await persistStage1ArtifactsIfBound('text-parser');

            const keyterms = payload.keyterms || [];
            if (populated === 0 && keyterms.length === 0) {
                showToast(
                    "No fields recognized. Use labels like 'Cause No:', 'Deponent:', 'Court Reporter:'.",
                    "amber"
                );
            } else {
                showToast(
                    `Extracted ${populated} field(s) and ${keyterms.length} keyterm(s) from pasted notes.`,
                    "emerald"
                );
            }
            addProvenanceRecord(
                "Text Parser",
                `Extracted ${populated} fields + ${keyterms.length} keyterms from pasted notes.`,
                "ai"
            );

            const warnings = (payload.metadata && payload.metadata.warnings) || [];
            warnings.forEach(w => showToast(w, "amber"));
        }

        // Real Notice of Deposition PDF parser — calls backend POST /api/nod/parse
        async function parseNODFile(input) {
            if (!input.files || !input.files[0]) return;
            const file = input.files[0];
            document.getElementById('nodLabel').innerText = `Parsing: ${file.name}...`;
            showToast(`Uploading ${file.name} to parser...`, "cyan");
            addProvenanceRecord("NOD Parser", `Uploaded ${file.name} for field extraction.`, "user");

            const formData = new FormData();
            formData.append("file", file);

            let payload;
            try {
                const res = await fetch(`/api/nod/parse`, {
                    method: "POST",
                    body: formData,
                });
                if (!res.ok) {
                    const errBody = await res.json().catch(() => ({}));
                    throw new Error(errBody.detail || `HTTP ${res.status}`);
                }
                payload = await res.json();
            } catch (err) {
                document.getElementById('nodLabel').innerText = `Drop Notice of Deposition (NOD) PDF`;
                showToast(`NOD parse failed: ${err.message}`, "red");
                addProvenanceRecord("NOD Parser", `Parse failed: ${err.message}`, "system");
                return;
            }

            // Apply the parsed fields to the UFM form
            applyParsedStage1Payload(payload);
            const fields = payload.fields || {};
            let populated = 0;
            for (const [id, value] of Object.entries(fields)) {
                const el = document.getElementById(id);
                if (el && value) {
                    el.value = value;
                    validateUFMField(el, id);
                    el.classList.add('animate-flash');
                    setTimeout(() => el.classList.remove('animate-flash'), 1500);
                    populated++;
                }
            }

            renderAllStateComponents();
            renderUFMTermsTable();
            await persistStage1ArtifactsIfBound('nod-parser');

            const keyterms = payload.keyterms || [];
            const detected = (payload.metadata && payload.metadata.detected_types) || [];
            document.getElementById('nodLabel').innerText = `Parsed: ${file.name}`;
            showToast(
                `Extracted ${populated} fields from ${file.name} (${detected.join(', ') || 'unknown layout'}).`,
                "emerald"
            );
            addProvenanceRecord(
                "NOD Parser",
                `Extracted ${populated} fields + ${keyterms.length} keyterms. Detected: ${detected.join(', ')}`,
                "ai"
            );

            // Surface warnings (e.g. multi-deposition packets)
            const warnings = (payload.metadata && payload.metadata.warnings) || [];
            warnings.forEach(w => showToast(w, "amber"));

            // Note additional sessions if found
            const additional = (payload.metadata && payload.metadata.additional_sessions) || [];
            if (additional.length > 0) {
                addProvenanceRecord(
                    "NOD Parser",
                    `${additional.length} additional deposition(s) found in this packet (not yet imported): ${additional.map(s => s.witness_name || 'unknown').join('; ')}`,
                    "system"
                );
            }
        }

        // Repopulate UFM form inputs from state.caseInfo (e.g. when revisiting Stage 1)
        function hydrateUFMFormFromState() {
            const reverseMap = {
                'ufmCause': 'cause',
                'ufmStyle': 'caption',
                'ufmCourt': 'court',
                'ufmCounty': 'county',
                'ufmState': 'state',
                'ufmWitness': 'deponent',
                'ufmDate': 'date',
                'ufmStartTime': 'startTime',
                'ufmEndTime': 'endTime',
                'ufmAddress': 'address',
                'ufmCSRName': 'csrName',
                'ufmCSRLicense': 'csrLicense',
                'ufmFirmReg': 'firmReg',
                'ufmCSRCertExp': 'csrCertExp',
                'ufmCustodialName': 'custodialName',
                'ufmRequestingParty': 'requestingParty'
            };
            for (const [id, stateField] of Object.entries(reverseMap)) {
                const el = document.getElementById(id);
                if (!el) continue;
                // Always assign -- including empty strings. The previous
                // `if (val)` guard meant starting a new case left stale
                // text in the inputs because empty values were skipped.
                el.value = state.caseInfo[stateField] || '';
                // Seed dataset.confirmedValue from server-confirmed state so
                // an unchanged value keeps its CONFIRMED badge after reload.
                const confirmed = state.stage1.field_confirmations
                    && state.stage1.field_confirmations[id] === 'confirmed';
                if (confirmed) {
                    el.dataset.confirmedValue = el.value.trim();
                } else {
                    delete el.dataset.confirmedValue;
                }
                validateUFMField(el, id);
            }
        }

        function renderUFMTermsTable() {
            const tbody = document.getElementById('ufmTermsTableBody');
            const countEl = document.getElementById('ufmTermsCount');
            if (!tbody) return;

            const rows = collectStage1KeytermEntries();

            tbody.innerHTML = "";
            if (rows.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" class="py-3 px-3 text-center text-slate-600 italic">No terms parsed yet. Run AI Notes Parser to populate.</td></tr>`;
            } else {
                rows.forEach(r => {
                    const tr = document.createElement('tr');
                    tr.className = "border-t border-slate-900 hover:bg-slate-900/40 transition-all";
                    tr.innerHTML = `
                        <td class="py-1.5 px-3 text-white">${r.term}</td>
                        <td class="py-1.5 px-3"><span class="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">${r.category}</span></td>
                        <td class="py-1.5 px-3 text-slate-400">${r.source}</td>
                        <td class="py-1.5 px-3 text-right text-emerald-400">${r.boost.toFixed(1)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
            if (countEl) countEl.innerText = `${rows.length} term${rows.length === 1 ? '' : 's'}`;
        }

        // Proceed confirmation check
        function confirmProceedWithSchemaCheck() {
            const missingCount = UFM_FIELD_IDS.filter(id => {
                const el = document.getElementById(id);
                return !el || el.value.trim() === '';
            }).length;
            if (missingCount > 0) {
                showToast(
                    `Warning: ${missingCount} required field(s) are blank. UFM generation may fail.`,
                    "amber"
                );
            }
            if (!state.caseId || !state.sessionId) {
                showToast("Save Stage 1 Intake before proceeding. A valid case and session are required.", "red");
                return;
            }
            goToStage(2);
        }

        // goToStage / getStageName / triggerFileInput live in app.js and ui.js (Phase A.2 extraction)
        // handleAudioSelect, simulateNODParsing — removed in Wave 4.
        // Audio upload now lives on Stage 2; NOD parsing uses parseNODFile() above.

        // Deposition Notes attachment. The court reporter's own notes file is
        // attached to the record here. Parsing its contents is a future milestone;
        // for now the file is logged so it's available later.
        function handleDepoNotesSelect(input) {
            if (input.files && input.files[0]) {
                const file = input.files[0];
                document.getElementById('depoNotesLabel').innerText = `Notes attached: ${file.name}`;
                addProvenanceRecord && addProvenanceRecord(
                    "Deposition Notes Attached",
                    `Court reporter notes file linked: ${file.name}`,
                    "user"
                );
                showToast && showToast(`Deposition notes attached: ${file.name}`, "emerald");
            }
        }

        async function openKeyTermsJsonModal() {
            const pre = document.getElementById('keytermsJsonContent');
            const stamp = document.getElementById('keytermsJsonComputedAt');
            const modal = document.getElementById('keytermsJsonModal');
            if (!pre || !modal) return;

            let body;
            if (state.caseId && window.api) {
                try {
                    body = await window.api.getDeepgramPreview(state.caseId);
                    if (stamp) stamp.textContent = `computed_at: ${body.computed_at || ''}`;
                } catch (err) {
                    showToast && showToast(`Deepgram preview failed: ${err.message}`, "red");
                    body = buildLocalDeepgramFallback();
                    if (stamp) stamp.textContent = `local fallback · ${new Date().toISOString()}`;
                }
            } else {
                body = buildLocalDeepgramFallback();
                if (stamp) stamp.textContent = `local fallback · ${new Date().toISOString()}`;
            }
            pre.textContent = JSON.stringify(body, null, 2);
            modal.classList.remove('hidden');
        }

        function closeKeyTermsJsonModal() {
            const modal = document.getElementById('keytermsJsonModal');
            if (modal) modal.classList.add('hidden');
        }

        function copyKeyTermsJson() {
            const pre = document.getElementById('keytermsJsonContent');
            if (pre && navigator.clipboard) {
                navigator.clipboard.writeText(pre.textContent).then(() => {
                    showToast && showToast("Deepgram request copied to clipboard.", "emerald");
                });
            }
        }

        // Fallback view (case not yet saved): shows just the keyterms list.
        // The real Deepgram request params are fetched via the preview
        // endpoint once the case has been persisted.
        function buildLocalDeepgramFallback() {
            const terms = collectStage1KeytermEntries();
            return {
                case_id: state.caseId || null,
                computed_at: new Date().toISOString(),
                deepgram_request: null,
                keyterms: terms,
                keyterms_count: terms.length,
                note: "Save the case to fetch the live Deepgram request preview.",
            };
        }

        // Retained for any callers/tests that built a local-keyterms payload.
        function buildKeytermsPayload() {
            const terms = collectStage1KeytermEntries();
            return {
                case_id: state.caseId || null,
                case_caption: state.caseInfo.caption || null,
                cause_number: state.caseInfo.cause || null,
                generated_at: new Date().toISOString(),
                keyterms: terms
            };
        }

        async function openUfmPreviewModal() {
            const pre = document.getElementById('ufmPreviewContent');
            const stamp = document.getElementById('ufmPreviewComputedAt');
            const modal = document.getElementById('ufmPreviewModal');
            if (!pre || !modal) return;

            if (!state.caseId || !window.api) {
                showToast && showToast("Save the case before viewing the UFM payload.", "amber");
                return;
            }
            try {
                const body = await window.api.getUfmPreview(state.caseId);
                if (stamp) stamp.textContent = `computed_at: ${body.computed_at || ''}`;
                pre.textContent = JSON.stringify(body, null, 2);
                modal.classList.remove('hidden');
            } catch (err) {
                showToast && showToast(`UFM preview failed: ${err.message}`, "red");
            }
        }

        function closeUfmPreviewModal() {
            const modal = document.getElementById('ufmPreviewModal');
            if (modal) modal.classList.add('hidden');
        }

        function copyUfmPreviewJson() {
            const pre = document.getElementById('ufmPreviewContent');
            if (pre && navigator.clipboard) {
                navigator.clipboard.writeText(pre.textContent).then(() => {
                    showToast && showToast("UFM payload copied to clipboard.", "emerald");
                });
            }
        }


window.validateUFMField = validateUFMField;
window.checkSchemaValidationStatus = checkSchemaValidationStatus;
window.runAILegalParser = runAILegalParser;
window.parseNODFile = parseNODFile;
window.handleDepoNotesSelect = handleDepoNotesSelect;
window.hydrateUFMFormFromState = hydrateUFMFormFromState;
window.renderUFMTermsTable = renderUFMTermsTable;
window.confirmProceedWithSchemaCheck = confirmProceedWithSchemaCheck;
window.openKeyTermsJsonModal = openKeyTermsJsonModal;
window.closeKeyTermsJsonModal = closeKeyTermsJsonModal;
window.copyKeyTermsJson = copyKeyTermsJson;
window.buildKeytermsPayload = buildKeytermsPayload;
window.persistStage1ArtifactsIfBound = persistStage1ArtifactsIfBound;
window.renderCaseContextBanner = renderCaseContextBanner;
window.confirmUFMField = confirmUFMField;
window.confirmAllPopulatedUFMFields = confirmAllPopulatedUFMFields;
window.UFM_FIELD_IDS = UFM_FIELD_IDS;
window.UFM_FIELD_LABELS = UFM_FIELD_LABELS;
window.openUfmPreviewModal = openUfmPreviewModal;
window.closeUfmPreviewModal = closeUfmPreviewModal;
window.copyUfmPreviewJson = copyUfmPreviewJson;
