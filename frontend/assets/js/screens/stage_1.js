        function validateUFMField(inputEl, label) {
            const val = inputEl.value.trim();
            const badge = inputEl.parentElement.querySelector('.ufm-val-badge');

            // Map inputs to state case schema
            const idMap = {
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

            const stateField = idMap[inputEl.id];
            if (stateField) {
                state.caseInfo[stateField] = val;
            }

            if (val === "") {
                inputEl.className = "w-full bg-slate-900 border border-red-500/30 text-xs px-2.5 py-1 rounded-lg text-white focus:outline-none";
                if (badge) {
                    badge.innerText = "MISSING";
                    badge.className = "ufm-val-badge absolute right-2 top-6 text-[8px] px-1 py-0.2 rounded bg-red-500/10 text-red-400";
                }
            } else {
                inputEl.className = "w-full bg-slate-900 border border-emerald-500/30 text-xs px-2.5 py-1 rounded-lg text-white focus:outline-none";
                if (badge) {
                    badge.innerText = "✓ VERIFIED";
                    badge.className = "ufm-val-badge absolute right-2 top-6 text-[8px] px-1 py-0.2 rounded bg-emerald-500/10 text-emerald-400";
                }
            }

            // Sync legacy global mirrors if present (no-op when those nodes don't exist in current shell)
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

        // Run validation calculations over all fields
        function checkSchemaValidationStatus() {
            const summaryBadge = document.getElementById('validationSummaryBadge');
            if (!summaryBadge) return;

            const fields = [
                'ufmCause', 'ufmStyle', 'ufmCourt', 'ufmCounty', 'ufmState',
                'ufmWitness', 'ufmDate', 'ufmStartTime', 'ufmEndTime', 'ufmAddress',
                'ufmCSRName', 'ufmCSRLicense', 'ufmFirmReg', 'ufmCSRCertExp',
                'ufmCustodialName', 'ufmRequestingParty'
            ];

            let incomplete = false;
            fields.forEach(id => {
                const el = document.getElementById(id);
                if (el && el.value.trim() === "") {
                    incomplete = true;
                }
            });

            if (incomplete) {
                summaryBadge.innerText = "⚠️ SCHEMA INCOMPLETE";
                summaryBadge.className = "text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 font-bold";
            } else {
                summaryBadge.innerText = "✓ ALL FIELDS VERIFIED";
                summaryBadge.className = "text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold";
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

            // Mirror parsed keyterms into corrections memory + UFM dictionary
            const keyterms = payload.keyterms || [];
            keyterms.forEach(kt => {
                state.correctionsMemory.push({
                    original: kt.term.toLowerCase(),
                    replacement: kt.term,
                    scope: "case",
                    category: kt.category || "Term",
                    boost: kt.boost || 1.0,
                });
            });

            renderAllStateComponents();
            renderUFMTermsTable();

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

            // Mirror parsed keyterms into the corrections memory + UFM dictionary
            const keyterms = payload.keyterms || [];
            keyterms.forEach(kt => {
                state.correctionsMemory.push({
                    original: kt.term.toLowerCase(),
                    replacement: kt.term,
                    scope: "case",
                    category: kt.category || "Term",
                    boost: kt.boost || 1.0,
                });
            });

            renderAllStateComponents();
            renderUFMTermsTable();

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
                validateUFMField(el, id);
            }
        }

        function renderUFMTermsTable() {
            const tbody = document.getElementById('ufmTermsTableBody');
            const countEl = document.getElementById('ufmTermsCount');
            if (!tbody) return;

            const rows = [];
            const seenTerms = new Set();
            const addRow = (term, category, source, boost) => {
                if (!term) return;
                const key = term.trim().toLowerCase();
                if (seenTerms.has(key)) return;
                seenTerms.add(key);
                rows.push({ term, category, source, boost });
            };

            if (state.caseInfo.deponent) addRow(state.caseInfo.deponent, 'Deponent', 'Notice parser', 1.5);
            if (state.caseInfo.csrName) addRow(state.caseInfo.csrName, 'Reporter', 'Notice parser', 1.0);
            if (state.caseInfo.custodialName) addRow(state.caseInfo.custodialName, 'Attorney', 'Notice parser', 1.2);
            if (state.caseInfo.requestingParty) addRow(state.caseInfo.requestingParty, 'Firm', 'Notice parser', 1.0);
            (state.correctionsMemory || []).forEach(corr => {
                addRow(
                    corr.replacement,
                    'Medical',
                    corr.scope === 'global' ? 'Learned' : 'Notice parser',
                    1.5
                );
            });

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
            const summaryBadge = document.getElementById('validationSummaryBadge');
            if (summaryBadge.innerText.includes("INCOMPLETE")) {
                showToast("Warning: Some mandatory UFM variables are blank. UFM generation may fail.", "amber");
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

        function openKeyTermsJsonModal() {
            const payload = buildKeytermsPayload();
            const pre = document.getElementById('keytermsJsonContent');
            if (pre) pre.textContent = JSON.stringify(payload, null, 2);
            const modal = document.getElementById('keytermsJsonModal');
            if (modal) modal.classList.remove('hidden');
        }

        function closeKeyTermsJsonModal() {
            const modal = document.getElementById('keytermsJsonModal');
            if (modal) modal.classList.add('hidden');
        }

        function copyKeyTermsJson() {
            const pre = document.getElementById('keytermsJsonContent');
            if (pre && navigator.clipboard) {
                navigator.clipboard.writeText(pre.textContent).then(() => {
                    showToast && showToast("Keyterms JSON copied to clipboard.", "emerald");
                });
            }
        }

        function buildKeytermsPayload() {
            const terms = [];
            const seen = new Set();
            const addTerm = (term, boost, source) => {
                if (!term) return;
                const key = term.trim().toLowerCase();
                if (seen.has(key)) return;
                seen.add(key);
                terms.push({ term, boost, source });
            };

            if (state.caseInfo.deponent) addTerm(state.caseInfo.deponent, 1.5, 'notice_parser');
            if (state.caseInfo.csrName) addTerm(state.caseInfo.csrName, 1.0, 'notice_parser');
            if (state.caseInfo.custodialName) addTerm(state.caseInfo.custodialName, 1.2, 'notice_parser');
            if (state.caseInfo.requestingParty) addTerm(state.caseInfo.requestingParty, 1.0, 'notice_parser');
            (state.correctionsMemory || []).forEach(c => {
                addTerm(c.replacement, 1.5, c.scope === 'global' ? 'learned' : 'notice_parser');
            });
            return {
                case_id: 'pending_phase_b',
                case_caption: state.caseInfo.caption || null,
                cause_number: state.caseInfo.cause || null,
                generated_at: new Date().toISOString(),
                keyterms: terms
            };
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
