        function runCustomRegexRulePipeline() {
            const findVal = document.getElementById('regexFindInput').value;
            const replaceVal = document.getElementById('regexReplaceInput').value;

            if (!findVal) {
                showToast("Please enter a valid Find RegEx.", "red");
                return;
            }

            showToast("Running Python Pipeline Preprocessing...", "indigo");

            try {
                const regex = new RegExp(findVal, 'gi');
                let matchesCount = 0;

                state.transcriptLines.forEach(line => {
                    if (line.text.match(regex)) {
                        line.text = line.text.replace(regex, replaceVal);
                        matchesCount++;
                    }
                });

                if (matchesCount > 0) {
                    addProvenanceRecord("Python RegEx Pipeline", `Executed find/replace [${findVal}] -> [${replaceVal}]. ${matchesCount} substitutions completed.`, "system");
                    compileAndRenderTranscript();
                    showToast(`Pipeline execution successful: ${matchesCount} modifications applied.`, "emerald");
                } else {
                    showToast("No pattern occurrences located in transcription arrays.", "amber");
                }
            } catch (err) {
                showToast(`Regex Error: ${err.message}`, "red");
            }
        }

        // Trigger dynamic extraction of Deepgram suggestions (Stage 3)
        function triggerAISuggestionExtraction() {
            showToast("Aligning LLM confidence scores...", "cyan");
            addProvenanceRecord("AI Model Suggestions", "Parsed low confidence speech boundaries.", "ai");
            compileAndRenderTranscript();
        }

        function updateTemperatureSlider(val) {
            const sliderLabel = document.getElementById('sliderVal');
            if (val == 1) sliderLabel.innerText = "Strict (0.2)";
            if (val == 2) sliderLabel.innerText = "Balanced (0.5)";
            if (val == 3) sliderLabel.innerText = "Adaptive Creative (0.8)";
        }

        // Theme layout engine (MS Word vs Dark Canvas)
        function toggleTranscriptTheme() {
            const themeBtn = document.getElementById('btnThemeToggle');
            const canvas = document.getElementById('compiledUFMTranscriptContainer');
            const lineRuleLeft = document.getElementById('lineRuleLeft');
            const lineRuleRight = document.getElementById('lineRuleRight');

            if (state.canvasTheme === 'dark') {
                state.canvasTheme = 'word';
                themeBtn.innerText = "📁 Switch to Dark Editor";
                themeBtn.className = "px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 border border-transparent rounded-lg text-xs font-semibold text-white transition-all flex items-center gap-1.5 shadow-sm select-none";

                // Add MS Word Styling
                canvas.className = "w-full max-w-3xl ms-word-page select-text";
                lineRuleLeft.className = "ms-word-redline-left pointer-events-none";
                lineRuleRight.className = "ms-word-redline-right pointer-events-none";

                showToast("Microsoft Word Typesetting Layout Mode Enabled.", "indigo");
            } else {
                state.canvasTheme = 'dark';
                themeBtn.innerText = "📁 Toggle MS Word Layout";
                themeBtn.className = "px-3.5 py-1.5 bg-slate-950 hover:bg-slate-850 border border-slate-800 rounded-lg text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-all flex items-center gap-1.5 select-none";

                // Remove MS Word Styling
                canvas.className = "w-full max-w-3xl bg-[#0a0f18] text-slate-300 border border-slate-800/80 shadow-2xl rounded-xl p-8 font-mono text-sm leading-8 relative min-h-[1000px] select-text";
                lineRuleLeft.className = "absolute top-0 bottom-0 left-12 ufm-rule-left pointer-events-none";
                lineRuleRight.className = "absolute top-0 bottom-0 right-12 ufm-rule-right pointer-events-none";

                showToast("Editor Dark Layout Restored.");
            }
            compileAndRenderTranscript();
        }

        // Compile and render Texas UFM conforming to standard page boundaries
        function compileAndRenderTranscript() {
            const linesContainer = document.getElementById('transcriptLinesContainer');
            if (!linesContainer) return;
            linesContainer.innerHTML = "";

            let currentLineNumberOnPage = 1;
            let currentPageNumber = 1;

            state.transcriptLines.forEach((line) => {
                // If Texas strict limits are locked, wrap at 25 lines
                if (state.caseInfo.strictLineLock && currentLineNumberOnPage > 25) {
                    const divider = document.createElement('div');
                    divider.className = "border-t-2 border-dashed border-red-500/20 my-8 py-3 text-center text-xs font-mono select-none relative z-10 text-slate-500";
                    divider.innerHTML = `--- END OF PAGE ${currentPageNumber} (TEXAS UFM PAGE BREAK POINT) ---`;
                    linesContainer.appendChild(divider);

                    currentPageNumber++;
                    currentLineNumberOnPage = 1;
                }

                const row = document.createElement('div');
                row.className = `group flex items-start gap-4 hover:bg-slate-900/20 p-1.5 rounded transition-all cursor-pointer relative ${state.focusedLineId === line.id ? 'bg-indigo-950/20 border-l-2 border-indigo-500' : ''}`;
                row.id = line.id;
                row.setAttribute('onclick', `focusLineRow('${line.id}')`);

                // Index column
                const numIndex = document.createElement('div');
                numIndex.className = `w-8 text-right font-mono text-xs select-none pr-3 ${state.canvasTheme === 'word' ? 'text-slate-400' : 'text-slate-600'}`;
                numIndex.innerText = currentLineNumberOnPage;

                // Gutter Indicator
                const gutter = document.createElement('div');
                let gutterColor = "bg-emerald-500";
                if (line.confidence < 0.8) gutterColor = "bg-amber-500 animate-pulse";
                gutter.className = `w-1 self-stretch rounded-full ${gutterColor} select-none mr-2`;

                // Main textual column
                const textBlock = document.createElement('div');
                textBlock.className = `flex-1 font-mono text-xs md:text-sm select-text ${state.canvasTheme === 'word' ? 'text-slate-800' : 'text-slate-300'}`;

                let prefixHtml = "";
                if (line.type === "Q") {
                    prefixHtml = `<span class="text-indigo-600 font-bold mr-2 select-none">Q.</span>`;
                } else if (line.type === "A") {
                    prefixHtml = `<span class="text-cyan-600 font-bold mr-2 select-none">A.</span>`;
                }

                // Highlight low confidence boundaries
                let textContentHtml = "";
                const words = line.text.split(" ");

                words.forEach((word) => {
                    let cleanWord = word.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g,"");

                    if (line.hasSuggestion && line.suggestion.word.toLowerCase() === cleanWord.toLowerCase()) {
                        textContentHtml += `<span class="low-confidence-word text-amber-500 font-medium relative cursor-pointer hover:bg-amber-500/10 rounded px-0.5" onclick="event.stopPropagation(); triggerSuggestionBox('${line.id}')">${word}</span> `;
                    } else if (line.confidence < 0.85 && cleanWord.toLowerCase() === "seventh") {
                        textContentHtml += `<span class="low-confidence-word text-amber-500 cursor-pointer" onclick="event.stopPropagation(); triggerSuggestionBox('${line.id}')">${word}</span> `;
                    } else {
                        textContentHtml += `<span>${word}</span> `;
                    }
                });

                textBlock.innerHTML = `
                    <div class="flex items-center gap-2 mb-1 select-none">
                        <span class="text-[9px] font-bold text-slate-500 tracking-wider">${line.speaker}</span>
                        ${line.exhibit ? `<span class="text-[8px] px-1 bg-cyan-500/10 text-cyan-500 border border-cyan-500/20 rounded">EXHIBIT ${line.exhibit} MARKED</span>` : ''}
                    </div>
                    <div class="transcript-line outline-none focus:bg-indigo-500/5 focus:rounded p-0.5" contenteditable="${state.caseInfo.certified ? 'false' : 'true'}" onblur="handleTextEdit('${line.id}', this.innerHTML)">
                        ${prefixHtml}${textContentHtml}
                    </div>
                `;

                row.appendChild(numIndex);
                row.appendChild(gutter);
                row.appendChild(textBlock);

                // Inline suggestion display (Stage 3 Suggestion Sweep Mode)
                if (state.workspaceMode === 'suggestions' && line.hasSuggestion) {
                    const inlineCassette = createInlineSuggestionCassette(line);
                    const wrapper = document.createElement('div');
                    wrapper.className = "w-full";
                    wrapper.appendChild(row);
                    wrapper.appendChild(inlineCassette);
                    linesContainer.appendChild(wrapper);
                } else {
                    linesContainer.appendChild(row);
                }

                currentLineNumberOnPage++;
            });

            document.getElementById('livePaginationStats').innerText = `${currentPageNumber} Page${currentPageNumber > 1 ? 's' : ''} Total`;
        }

        // Inline Cassette Suggestions Drawer UI Block
        function createInlineSuggestionCassette(line) {
            const cassette = document.createElement('div');
            cassette.className = "ml-14 mr-12 mt-2 mb-4 bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-xl select-none animate-slide-in relative z-20 font-sans";
            cassette.innerHTML = `
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
                        <span class="text-xs font-bold text-white">AI Alignment Match</span>
                    </div>
                    <span class="text-[9px] font-mono text-slate-500 uppercase">${line.suggestion.source}</span>
                </div>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-900 flex items-center justify-between gap-4 mb-3">
                    <div class="font-mono text-xs">
                        <span class="text-red-400 line-through mr-2 font-mono">"${line.suggestion.original}"</span>
                        <span class="text-slate-500">→</span>
                        <span class="text-emerald-400 font-bold ml-2 font-mono">"${line.suggestion.replacement}"</span>
                    </div>
                    <span class="text-[10px] text-slate-500 font-semibold font-mono">Conf: ${(line.suggestion.confidence * 100).toFixed(0)}%</span>
                </div>
                <div class="flex items-center justify-end gap-2">
                    <button onclick="rejectSuggestion('${line.id}')" class="px-3 py-1.5 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all">Reject</button>
                    <button onclick="acceptSuggestion('${line.id}')" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-all">Accept</button>
                    <button onclick="acceptAndRememberSuggestion('${line.id}')" class="px-3 py-1.5 bg-emerald-600/10 hover:bg-emerald-600 text-emerald-400 hover:text-white border border-emerald-500/20 rounded-lg text-xs font-bold transition-all">Accept + Remember</button>
                </div>
            `;
            return cassette;
        }

        // Direct Text Editor State handler
        function handleTextEdit(id, newHtml) {
            let cleanText = newHtml.replace(/<span[^>]*>.*?<\/span>/g, '').trim();
            cleanText = cleanText.replace(/&nbsp;/g, ' ');

            const line = state.transcriptLines.find(l => l.id === id);
            if (line && line.text !== cleanText) {
                const oldText = line.text;
                line.text = cleanText;

                addProvenanceRecord("Human Line Correction", `Row ${line.index} text correction: "${oldText}" -> "${cleanText}"`, "user");
                compileAndRenderTranscript();
                showToast(`Line ${line.index} updated.`);
            }
        }

        // Focused Line Event Tracker
        function focusLineRow(id) {
            state.focusedLineId = id;
            const line = state.transcriptLines.find(l => l.id === id);
            if (line) {
                document.getElementById('cursorLineTracker').innerText = `LINE ${line.index}`;
                drawAudioWaveProgress(line.index);
                updateRightPanelContext(line);
                if (state.workspaceMode === 'suggestions') {
                    triggerSuggestionBox(id);
                }
            }
        }

        function drawAudioWaveProgress(index) {
            const playhead = document.getElementById('playheadIndicator');
            const percent = Math.min((index / state.transcriptLines.length) * 100, 100);
            playhead.style.left = `${percent}%`;

            const totalDuration = state.transcriptLines.slice(0, index).reduce((acc, c) => acc + c.duration, 0);
            document.getElementById('audioTimeLabel').innerText = `00:${totalDuration.toFixed(0).padStart(2, '0')}.2 / 02:45.0`;
        }

        function updateRightPanelContext(line) {
            document.getElementById('confidenceScoreLabel').innerText = `${(line.confidence * 100).toFixed(0)}% Conf`;
            if (line.confidence < 0.85) {
                document.getElementById('confidenceScoreLabel').className = "text-[10px] font-semibold font-mono text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded";
            } else {
                document.getElementById('confidenceScoreLabel').className = "text-[10px] font-semibold font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded";
            }
        }

        // Change workspace mode tabs
        function setWorkspaceMode(mode) {
            state.workspaceMode = mode;
            const bannerText = document.getElementById('modeBannerText');

            const btns = ['Edit', 'Suggestions', 'Audio', 'Formatting'];
            btns.forEach(b => {
                const btn = document.getElementById(`modeBtn${b}`);
                btn.className = "px-3 py-1.5 text-xs font-medium rounded-lg transition-all border border-transparent text-slate-400 hover:text-slate-200";
            });

            document.getElementById('toolSectionAudio').classList.add('hidden');
            document.getElementById('toolSectionSuggestions').classList.add('hidden');
            document.getElementById('toolSectionFormatting').classList.add('hidden');

            if (mode === 'edit') {
                document.getElementById('modeBtnEdit').className = "px-3 py-1.5 text-xs font-medium rounded-lg transition-all border border-slate-700 bg-slate-800 text-white shadow-sm";
                bannerText.innerText = "Free Edit Mode: Click any line and type to edit text directly. Left rail tags are preserved automatically.";
                document.getElementById('toolSectionAudio').classList.remove('hidden');
                document.getElementById('rightPanelTitle').innerText = "Audio & Context Wave";
            } else if (mode === 'suggestions') {
                document.getElementById('modeBtnSuggestions').className = "px-3 py-1.5 text-xs font-medium rounded-lg transition-all border border-slate-700 bg-slate-800 text-white shadow-sm";
                bannerText.innerText = "Suggestion Sweep Mode: Interactive list of low confidence alignments. Review and remember spelling lists.";
                document.getElementById('toolSectionSuggestions').classList.remove('hidden');
                document.getElementById('rightPanelTitle').innerText = "AI Suggestions Queue";
                triggerSuggestionBox(state.focusedLineId);
            } else if (mode === 'audio') {
                document.getElementById('modeBtnAudio').className = "px-3 py-1.5 text-xs font-medium rounded-lg transition-all border border-slate-700 bg-slate-800 text-white shadow-sm";
                bannerText.innerText = "Audio Sync Review Mode: Words illuminate synchronously with waveform timeline loops.";
                document.getElementById('toolSectionAudio').classList.remove('hidden');
                document.getElementById('rightPanelTitle').innerText = "Acoustic Playback Engine";
            } else if (mode === 'formatting') {
                document.getElementById('modeBtnFormatting').className = "px-3 py-1.5 text-xs font-medium rounded-lg transition-all border border-slate-700 bg-slate-800 text-white shadow-sm";
                bannerText.innerText = "UFM Layout Mode: Recalculate strict margins, margins indicators, page counts and format types (Q & A parameters).";
                document.getElementById('toolSectionFormatting').classList.remove('hidden');
                document.getElementById('rightPanelTitle').innerText = "UFM Style Toolset";
            }

            compileAndRenderTranscript();
        }

        // Suggestion sweep box logic
        function triggerSuggestionBox(lineId) {
            const line = state.transcriptLines.find(l => l.id === lineId);
            const container = document.getElementById('aiSweepContainer');

            if (line && line.hasSuggestion) {
                container.innerHTML = `
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 shadow-lg space-y-3">
                        <div class="flex items-center justify-between">
                            <span class="text-[10px] font-bold text-indigo-400 uppercase">Target Suggestion</span>
                            <span class="text-[9px] text-slate-500">Row ${line.index}</span>
                        </div>
                        <p class="text-xs text-slate-400 font-sans leading-relaxed">Match phonetic segment to target NOD dictionary lists:</p>
                        <div class="bg-slate-900/60 p-3 rounded-lg border border-slate-805 font-mono text-xs">
                            <p class="text-red-400 line-through mb-1">"${line.suggestion.original}"</p>
                            <p class="text-emerald-400 font-bold">"${line.suggestion.replacement}"</p>
                        </div>
                        <div class="flex items-center justify-end gap-2 pt-2">
                            <button onclick="rejectSuggestion('${line.id}')" class="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 text-xs rounded-lg">Reject</button>
                            <button onclick="acceptSuggestion('${line.id}')" class="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg">Accept</button>
                            <button onclick="acceptAndRememberSuggestion('${line.id}')" class="px-2.5 py-1.5 bg-emerald-600/10 text-emerald-400 hover:bg-emerald-600 hover:text-white border border-emerald-500/20 text-xs rounded-lg font-bold">Accept + Remember</button>
                        </div>
                    </div>
                `;
            } else {
                container.innerHTML = `
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 text-center py-6 text-slate-500 text-xs italic">
                        No active suggestions on selected row.
                    </div>
                `;
            }
        }

        // Suggestions action execution
        function acceptSuggestion(lineId) {
            const line = state.transcriptLines.find(l => l.id === lineId);
            if (line && line.hasSuggestion) {
                line.text = line.text.replace(new RegExp(line.suggestion.original, 'gi'), line.suggestion.replacement);
                line.hasSuggestion = false;
                addProvenanceRecord("AI Match Accepted", `Substituted speech block segment with [${line.suggestion.replacement}]`, "ai");
                compileAndRenderTranscript();
                showToast("AI suggestion merged into living transcript arrays.", "emerald");
                triggerSuggestionBox(lineId);
            }
        }

        function rejectSuggestion(lineId) {
            const line = state.transcriptLines.find(l => l.id === lineId);
            if (line && line.hasSuggestion) {
                line.hasSuggestion = false;
                addProvenanceRecord("AI Match Rejected", `Dismissed AI suggestions on line index ${line.index}`, "user");
                compileAndRenderTranscript();
                showToast("Suggestion dismissed.");
                triggerSuggestionBox(lineId);
            }
        }

        function acceptAndRememberSuggestion(lineId) {
            const line = state.transcriptLines.find(l => l.id === lineId);
            if (line && line.hasSuggestion) {
                state.correctionsMemory.push({
                    original: line.suggestion.original,
                    replacement: line.suggestion.replacement,
                    scope: "global"
                });

                line.text = line.text.replace(new RegExp(line.suggestion.original, 'gi'), line.suggestion.replacement);
                line.hasSuggestion = false;

                addProvenanceRecord("Correction Memory Commit", `Learned globally: "${line.suggestion.original}" matches "${line.suggestion.replacement}"`, "user");
                compileAndRenderTranscript();
                renderCorrectionMemory();
                showToast("Correction captured and saved to reporter memory dictionary!", "emerald");
                triggerSuggestionBox(lineId);
            }
        }

        // Visual format prefixes (Q & A)
        function applyLinePrefix(type) {
            const line = state.transcriptLines.find(l => l.id === state.focusedLineId);
            if (line) {
                line.type = type;
                addProvenanceRecord("UFM Formatting Shift", `Enforced prefix rules type ${type} on row ${line.index}`, "user");
                compileAndRenderTranscript();
                showToast(`Prefix set to ${type === 'Q' ? 'Question' : 'Answer'}.`);
            }
        }

        // Insert new structural elements
        function forceManualPageBreak() {
            state.transcriptLines.push({
                id: `manual-line-${Date.now()}`,
                index: state.transcriptLines.length + 1,
                speaker: "SYSTEM",
                text: "--- MANUALLY FORCED PAGINATION BARRIER ---",
                type: "text",
                confidence: 1.0,
                hasSuggestion: false,
                duration: 0.0
            });
            compileAndRenderTranscript();
            showToast("Forced layout page break boundary applied.");
        }

        function removeFillerWordsGlobal() {
            state.transcriptLines.forEach(line => {
                line.text = line.text.replace(/\b(um|uh)\b/gi, '').replace(/\s+/g, ' ').trim();
            });
            addProvenanceRecord("Acoustic Prep Pipeline", "Removed linguistic fillers (um/uh) globally.", "system");
            compileAndRenderTranscript();
            showToast("Linguistic fillers removed globally.", "emerald");
        }

        // Global playback sync controls
        function toggleAudioPlayback() {
            state.activePlayback = !state.activePlayback;
            const playBtn = document.getElementById('playAudioBtn');
            const svg = document.getElementById('playIconSvg');

            if (state.activePlayback) {
                svg.innerHTML = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M10 9v6m4-6v6"/>`;
                playBtn.className = "bg-amber-500 hover:bg-amber-400 text-white font-bold p-3 rounded-xl shadow-lg shadow-amber-500/20 transition-all flex items-center justify-center";
                showToast("Audio timeline active. Seeking utterance timestamps.");

                state.playbackInterval = setInterval(() => {
                    state.playbackLineIdx++;
                    if (state.playbackLineIdx >= state.transcriptLines.length) {
                        state.playbackLineIdx = 0;
                    }
                    focusLineRow(state.transcriptLines[state.playbackLineIdx].id);
                }, 1000 / state.playbackSpeed);
            } else {
                svg.innerHTML = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>`;
                playBtn.className = "bg-indigo-600 hover:bg-indigo-500 text-white font-bold p-3 rounded-xl shadow-lg shadow-indigo-600/20 transition-all flex items-center justify-center";
                clearInterval(state.playbackInterval);
            }
        }

        function changeAudioSpeed(val) {
            state.playbackSpeed = parseFloat(val);
            document.getElementById('audioSpeedLabel').innerText = `${state.playbackSpeed.toFixed(1)}x`;
            if (state.activePlayback) {
                clearInterval(state.playbackInterval);
                state.playbackInterval = setInterval(() => {
                    state.playbackLineIdx++;
                    if (state.playbackLineIdx >= state.transcriptLines.length) state.playbackLineIdx = 0;
                    focusLineRow(state.transcriptLines[state.playbackLineIdx].id);
                }, 1000 / state.playbackSpeed);
            }
        }

        function skipAudio(val) {
            const change = val > 0 ? 1 : -1;
            state.playbackLineIdx = Math.max(0, Math.min(state.playbackLineIdx + change, state.transcriptLines.length - 1));
            focusLineRow(state.transcriptLines[state.playbackLineIdx].id);
        }

        function _speakerMapState() {
            if (!state.workspaceSpeakerMapping) {
                state.workspaceSpeakerMapping = { jobs: [], assignments: {} };
            }
            return state.workspaceSpeakerMapping;
        }

        function _speakerMapEsc(value) {
            return String(value == null ? "" : value)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;");
        }

        function _speakerMapStatus(text, tone) {
            const el = document.getElementById('workspaceSpeakerMappingStatus');
            if (!el) return;
            el.innerText = text;
            const map = {
                idle: "text-[9px] font-mono text-slate-600",
                loading: "text-[9px] font-mono text-indigo-400",
                ready: "text-[9px] font-mono text-emerald-400",
                warning: "text-[9px] font-mono text-amber-400",
            };
            el.className = map[tone] || map.idle;
        }

        function _speakerMapRoleOptions(roles, current) {
            return (roles || []).map(r =>
                `<option value="${_speakerMapEsc(r.value)}"${r.value === current ? " selected" : ""}>${_speakerMapEsc(r.label)}</option>`
            ).join("");
        }

        function setWorkspaceSpeakerAssignment(jobId, speakerIndex, field, value) {
            const sm = _speakerMapState();
            if (!sm.assignments[jobId]) sm.assignments[jobId] = {};
            if (!sm.assignments[jobId][speakerIndex]) {
                sm.assignments[jobId][speakerIndex] = { role: "other", name: "", honorific: "" };
            }
            sm.assignments[jobId][speakerIndex][field] = value;
        }

        function _buildWorkspaceParticipants(jobId) {
            const sm = _speakerMapState();
            const assigns = sm.assignments[jobId] || {};
            const groups = {};
            let order = 0;
            Object.keys(assigns).forEach(idxStr => {
                const idx = parseInt(idxStr, 10);
                const a = assigns[idxStr] || {};
                const name = (a.name || "").trim();
                const role = a.role || "other";
                const honorific = (a.honorific || "").trim();
                const key = `${role}||${name.toLowerCase()}||${honorific.toUpperCase()}`;
                if (!groups[key]) {
                    groups[key] = {
                        name: name || null,
                        role: role,
                        honorific: honorific || null,
                        speaker_indices: [],
                        sort_order: order++,
                    };
                }
                groups[key].speaker_indices.push(idx);
            });
            return Object.values(groups);
        }

        function renderWorkspaceSpeakerMapping() {
            const root = document.getElementById('workspaceSpeakerMappingRoot');
            if (!root) return;
            const sm = _speakerMapState();
            if (!sm.jobs || sm.jobs.length === 0) {
                root.innerHTML = `<p class="text-[10px] text-slate-600 italic">Load a transcript job from Stage 2 to review diarization and assign speakers.</p>`;
                _speakerMapStatus('idle', 'idle');
                return;
            }
            const multiJob = sm.jobs.length > 1;
            root.innerHTML = sm.jobs.map(view => {
                const assigns = sm.assignments[view.job_id] || {};
                const badge = view.is_prefill
                    ? `<span class="px-2 py-0.5 text-[9px] font-bold rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 tracking-wider">PREFILL</span>`
                    : `<span class="px-2 py-0.5 text-[9px] font-bold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 tracking-wider">SAVED</span>`;
                const rows = (view.detected_speakers || []).map(d => {
                    const a = assigns[d.speaker_index] || { role: "other", name: "", honorific: "" };
                    return `
                        <div class="py-2.5 border-b border-slate-800/60 last:border-0">
                            <div class="flex items-center justify-between gap-2 mb-1.5">
                                <div>
                                    <div class="text-[11px] font-bold text-slate-200">${_speakerMapEsc(d.speaker_label)}</div>
                                    <div class="text-[9px] font-mono text-slate-500">${d.word_count} words · ${d.utterance_count} turns</div>
                                </div>
                                <span class="text-[9px] font-mono text-slate-600">raw id ${d.speaker_index}</span>
                            </div>
                            <p class="text-[10px] text-slate-400 italic leading-snug mb-2">"${_speakerMapEsc(d.sample) || "(no sample)"}"</p>
                            <div class="flex flex-wrap items-center gap-2">
                                <select onchange="setWorkspaceSpeakerAssignment('${view.job_id}', ${d.speaker_index}, 'role', this.value)" class="bg-slate-900 border border-slate-700 rounded-lg text-[10px] text-slate-200 px-2 py-1.5 focus:border-indigo-500 focus:outline-none">
                                    ${_speakerMapRoleOptions(view.roles, a.role)}
                                </select>
                                <select onchange="setWorkspaceSpeakerAssignment('${view.job_id}', ${d.speaker_index}, 'honorific', this.value)" class="bg-slate-900 border border-slate-700 rounded-lg text-[10px] text-slate-200 px-2 py-1.5 focus:border-indigo-500 focus:outline-none">
                                    <option value="">No honorific</option>
                                    <option value="MR"${a.honorific === "MR" ? " selected" : ""}>MR</option>
                                    <option value="MS"${a.honorific === "MS" ? " selected" : ""}>MS</option>
                                    <option value="MRS"${a.honorific === "MRS" ? " selected" : ""}>MRS</option>
                                    <option value="DR"${a.honorific === "DR" ? " selected" : ""}>DR</option>
                                </select>
                                <input type="text" value="${_speakerMapEsc(a.name)}" placeholder="Name" oninput="setWorkspaceSpeakerAssignment('${view.job_id}', ${d.speaker_index}, 'name', this.value)" class="bg-slate-900 border border-slate-700 rounded-lg text-[10px] text-slate-200 px-2 py-1.5 flex-1 min-w-[10rem] focus:border-indigo-500 focus:outline-none placeholder:text-slate-600">
                            </div>
                        </div>
                    `;
                }).join("");
                return `
                    <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                        <div class="px-3 py-2 border-b border-slate-800 flex items-center justify-between gap-2">
                            <div class="text-[11px] font-semibold text-slate-300 truncate">${multiJob ? '&#x1F4C1; ' : ''}${_speakerMapEsc(view.source_filename)}</div>
                            ${badge}
                        </div>
                        <div class="px-3 py-1.5">${rows || '<p class="text-[10px] text-slate-500 italic py-2">No speakers detected.</p>'}</div>
                    </div>
                `;
            }).join("");
            _speakerMapStatus(`${sm.jobs.length} job(s) loaded`, 'ready');
        }

        async function loadWorkspaceSpeakerMapping() {
            const root = document.getElementById('workspaceSpeakerMappingRoot');
            if (!root) return;
            const jobIds = (state.activeTranscriptJobIds || []).slice();
            const sm = _speakerMapState();
            sm.jobs = [];
            sm.assignments = {};
            if (jobIds.length === 0) {
                renderWorkspaceSpeakerMapping();
                return;
            }
            if (!window.api || typeof window.api.getSpeakerMapping !== "function") {
                root.innerHTML = `<p class="text-[10px] text-red-400">Speaker mapping backend unavailable.</p>`;
                _speakerMapStatus('unavailable', 'warning');
                return;
            }
            _speakerMapStatus('loading…', 'loading');
            try {
                for (const jobId of jobIds) {
                    const view = await window.api.getSpeakerMapping(jobId);
                    sm.jobs.push(view);
                    const assigns = {};
                    (view.participants || []).forEach(p => {
                        (p.speaker_indices || []).forEach(idx => {
                            assigns[idx] = {
                                role: p.role || "other",
                                name: p.name || "",
                                honorific: p.honorific || "",
                            };
                        });
                    });
                    (view.detected_speakers || []).forEach(d => {
                        if (!assigns[d.speaker_index]) {
                            assigns[d.speaker_index] = { role: "other", name: "", honorific: "" };
                        }
                    });
                    sm.assignments[jobId] = assigns;
                }
                console.info('[DEPO-PRO] Speaker mapping reloaded', {
                    jobIds: jobIds,
                    count: sm.jobs.length,
                });
                renderWorkspaceSpeakerMapping();
            } catch (err) {
                console.error('Workspace speaker mapping load failed:', err);
                root.innerHTML = `<p class="text-[10px] text-red-400">Could not load speaker mapping: ${_speakerMapEsc(err.message || err)}</p>`;
                _speakerMapStatus('load failed', 'warning');
            }
        }

        async function saveWorkspaceSpeakerMapping() {
            const jobIds = (state.activeTranscriptJobIds || []).slice();
            if (jobIds.length === 0) {
                showToast("Load a transcript before saving speaker mapping.", "amber");
                return;
            }
            const btn = document.getElementById('workspaceSpeakerMappingSaveBtn');
            if (btn) {
                btn.disabled = true;
                btn.innerText = 'Saving…';
            }
            _speakerMapStatus('saving…', 'loading');
            try {
                for (const jobId of jobIds) {
                    const participants = _buildWorkspaceParticipants(jobId);
                    await window.api.saveSpeakerMapping(jobId, participants);
                }
                console.info('[DEPO-PRO] Stage 3 speaker mapping saved', {
                    jobIds: jobIds,
                });
                addProvenanceRecord(
                    "Speaker Mapping",
                    `Saved authoritative speaker mapping for ${jobIds.length} transcript job(s).`,
                    "user"
                );
                await loadTranscriptResultsIntoWorkspace(jobIds);
                await loadWorkspaceSpeakerMapping();
                showToast("Speaker mapping saved to Stage 3 workspace.", "emerald");
            } catch (err) {
                console.error('Workspace speaker mapping save failed:', err);
                _speakerMapStatus('save failed', 'warning');
                showToast(`Speaker mapping save failed: ${err.message}`, "red");
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerText = 'Save Speaker Mapping';
                }
            }
        }

        // Sidebar rendering drivers
        // ============================================================
        // Workspace job context.
        // Stage 3 is now the one authoritative speaker-mapping screen.
        // The workspace binds to the active transcript job and reloads
        // both speaker mapping and AI review state from that authority.
        // ============================================================

        function _workspaceJob() {
            if (!state.workspaceJob) {
                state.workspaceJob = { jobId: null };
            }
            return state.workspaceJob;
        }

        // Bind the Workspace to a transcript job and load its Stage 3
        // speaker mapping plus AI review queue.
        async function loadWorkspaceJobContext(jobId) {
            const wj = _workspaceJob();
            wj.jobId = jobId;
            if (typeof loadWorkspaceSpeakerMapping === "function") {
                loadWorkspaceSpeakerMapping();
            }
            // Wave 16: load the AI review queue for this job.
            if (typeof refreshAIReviewStatus === "function") refreshAIReviewStatus();
            if (typeof loadAISuggestions === "function" && jobId) {
                loadAISuggestions(jobId);
            }
        }

        function renderCorrectionMemory() {
            const container = document.getElementById('correctionsMemoryContainer');
            if (!container) return;
            container.innerHTML = "";
            state.correctionsMemory.forEach(corr => {
                const item = document.createElement('div');
                item.className = "bg-slate-900 border border-slate-850 p-2 rounded-lg text-[10px] flex items-center justify-between font-mono";
                item.innerHTML = `
                    <div class="truncate mr-2">
                        <span class="text-slate-500 line-through font-mono">"${corr.original}"</span>
                        <span class="text-slate-400 font-mono">→</span>
                        <span class="text-emerald-400 font-bold font-mono">"${corr.replacement}"</span>
                    </div>
                    <span class="text-[8px] bg-slate-950 px-1 py-0.2 rounded text-slate-500 font-mono uppercase">${corr.scope}</span>
                `;
                container.appendChild(item);
            });
        }


window.runCustomRegexRulePipeline = runCustomRegexRulePipeline;
window.triggerAISuggestionExtraction = triggerAISuggestionExtraction;
window.updateTemperatureSlider = updateTemperatureSlider;
window.toggleTranscriptTheme = toggleTranscriptTheme;
window.compileAndRenderTranscript = compileAndRenderTranscript;
window.createInlineSuggestionCassette = createInlineSuggestionCassette;
window.handleTextEdit = handleTextEdit;
window.focusLineRow = focusLineRow;
window.drawAudioWaveProgress = drawAudioWaveProgress;
window.updateRightPanelContext = updateRightPanelContext;
window.setWorkspaceMode = setWorkspaceMode;
window.triggerSuggestionBox = triggerSuggestionBox;
window.acceptSuggestion = acceptSuggestion;
window.rejectSuggestion = rejectSuggestion;
window.acceptAndRememberSuggestion = acceptAndRememberSuggestion;
window.applyLinePrefix = applyLinePrefix;
window.forceManualPageBreak = forceManualPageBreak;
window.removeFillerWordsGlobal = removeFillerWordsGlobal;
window.toggleAudioPlayback = toggleAudioPlayback;
window.changeAudioSpeed = changeAudioSpeed;
window.skipAudio = skipAudio;
window.renderCorrectionMemory = renderCorrectionMemory;
window.loadWorkspaceSpeakerMapping = loadWorkspaceSpeakerMapping;
window.saveWorkspaceSpeakerMapping = saveWorkspaceSpeakerMapping;
window.setWorkspaceSpeakerAssignment = setWorkspaceSpeakerAssignment;

// ============================================================
// Wave 16 — AI review queue panel.
// AI suggestions are advisory; nothing reaches the transcript
// until the reporter approves it. The panel talks to the
// /api/ai-review endpoints — all suggestion-gated.
// ============================================================

async function refreshAIReviewStatus() {
    const el = document.getElementById('aiReviewStatus');
    const btn = document.getElementById('aiSpeakerMapBtn');
    const analyzeBtn = document.getElementById('aiAnalyzeBtn');
    if (!el) return;
    try {
        const status = await window.api.getAIReviewStatus();
        if (status.available) {
            el.innerText = "● live";
            el.className = "text-[9px] font-mono text-emerald-400";
            if (btn) btn.disabled = false;
            if (analyzeBtn) analyzeBtn.disabled = false;
        } else {
            el.innerText = "○ inert (no key)";
            el.className = "text-[9px] font-mono text-slate-600";
            if (btn) { btn.disabled = true; btn.title = "Set ANTHROPIC_API_KEY to enable."; }
            if (analyzeBtn) { analyzeBtn.disabled = true; analyzeBtn.title = "Set ANTHROPIC_API_KEY to enable."; }
        }
    } catch (err) {
        el.innerText = "unavailable";
        el.className = "text-[9px] font-mono text-slate-600";
    }
}

async function requestAIAnalysis() {
    const sp = (typeof _workspaceJob === "function") ? _workspaceJob() : null;
    const jobId = sp && sp.jobId;
    if (!jobId) {
        showToast("Load a transcript job before requesting AI analysis.", "amber");
        return;
    }
    const btn = document.getElementById('aiAnalyzeBtn');
    if (btn) { btn.disabled = true; btn.innerText = "Analyzing… (this can take a moment)"; }
    try {
        const res = await window.api.analyzeAIJob(jobId);
        if (!res.available) {
            showToast("AI review layer is inert — no API key configured.", "amber");
        } else {
            showToast(`AI analysis complete — ${res.generated} suggestion(s) queued.`, "emerald");
            addProvenanceRecord("AI Review", `Ran AI analysis: ${res.generated} suggestion(s) generated.`, "ai");
        }
        await loadAISuggestions(jobId);
    } catch (err) {
        showToast(`AI analysis failed: ${err.message}`, "red");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = "✨ Analyze transcript (boundaries · garbles · flags)";
        }
    }
}

async function requestAISpeakerMap() {
    const sp = (typeof _workspaceJob === "function") ? _workspaceJob() : null;
    const jobId = sp && sp.jobId;
    if (!jobId) {
        showToast("Load a transcript job before requesting AI suggestions.", "amber");
        return;
    }
    const btn = document.getElementById('aiSpeakerMapBtn');
    if (btn) { btn.disabled = true; btn.innerText = "Asking AI…"; }
    try {
        const res = await window.api.generateAISpeakerMap(jobId);
        if (!res.available) {
            showToast("AI review layer is inert — no API key configured.", "amber");
        } else if (!res.suggestion) {
            showToast("AI did not return a usable speaker map.", "amber");
        } else {
            showToast("AI speaker-map suggestion added to the review queue.", "emerald");
        }
        await loadAISuggestions(jobId);
    } catch (err) {
        showToast(`AI request failed: ${err.message}`, "red");
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = "✨ Suggest speaker map"; }
    }
}

async function loadAISuggestions(jobId) {
    const list = document.getElementById('aiSuggestionsList');
    if (!list) return;
    try {
        const res = await window.api.listAISuggestions(jobId);
        const pending = (res.suggestions || []).filter(s => s.status === "pending");
        list.innerHTML = "";
        if (pending.length === 0) {
            list.innerHTML = `<p class="text-[10px] text-slate-600 italic">No pending AI suggestions.</p>`;
            return;
        }
        pending.forEach(s => list.appendChild(_aiSuggestionCard(s)));
    } catch (err) {
        list.innerHTML = `<p class="text-[10px] text-red-400">Could not load suggestions.</p>`;
    }
}

function _aiSuggestionCard(s) {
    const card = document.createElement('div');
    card.className = "bg-slate-950/50 border border-slate-800 rounded-lg p-2 space-y-1.5";
    // A suggestion that failed the four-part test is a flag, not an edit.
    const badge = s.is_applicable_edit
        ? `<span class="text-[8px] px-1 py-0.5 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/25">EDIT</span>`
        : `<span class="text-[8px] px-1 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/25">FLAG — REVIEW</span>`;
    let detail = "";
    if (s.kind === "speaker_map" && s.payload && s.payload.speaker_map) {
        const rows = Object.entries(s.payload.speaker_map)
            .map(([i, role]) => `Speaker ${i} → ${role}`).join("<br>");
        detail = `<div class="text-[9px] font-mono text-slate-400 mt-1">${rows}</div>`;
    } else if (s.before_text || s.after_text) {
        detail = `<div class="text-[9px] font-mono text-slate-400 mt-1">
            <span class="text-red-400">${s.before_text || ""}</span> →
            <span class="text-emerald-400">${s.after_text || ""}</span></div>`;
    }
    card.innerHTML = `
        <div class="flex items-center justify-between">
            <span class="text-[9px] font-bold uppercase tracking-wider text-slate-400">${s.kind}</span>
            ${badge}
        </div>
        <p class="text-[10px] text-slate-300 leading-snug">${s.reason || ""}</p>
        ${detail}
        <div class="flex gap-1 pt-0.5">
            <button onclick="approveAISuggestion('${s.suggestion_id}')"
                class="flex-1 text-[9px] font-bold text-white bg-emerald-700 hover:bg-emerald-600 rounded py-1">Approve</button>
            <button onclick="rejectAISuggestion('${s.suggestion_id}')"
                class="flex-1 text-[9px] font-bold text-slate-300 bg-slate-800 hover:bg-slate-700 rounded py-1">Reject</button>
        </div>`;
    return card;
}

async function approveAISuggestion(suggestionId) {
    try {
        await window.api.approveAISuggestion(suggestionId);
        showToast("Suggestion approved.", "emerald");
        addProvenanceRecord("AI Review", `Approved AI suggestion ${suggestionId.slice(0, 8)}.`, "user");
        const sp = (typeof _workspaceJob === "function") ? _workspaceJob() : null;
        if (sp && sp.jobId) await loadAISuggestions(sp.jobId);
    } catch (err) {
        showToast(`Approve failed: ${err.message}`, "red");
    }
}

async function rejectAISuggestion(suggestionId) {
    try {
        await window.api.rejectAISuggestion(suggestionId);
        showToast("Suggestion rejected.", "cyan");
        const sp = (typeof _workspaceJob === "function") ? _workspaceJob() : null;
        if (sp && sp.jobId) await loadAISuggestions(sp.jobId);
    } catch (err) {
        showToast(`Reject failed: ${err.message}`, "red");
    }
}

window.refreshAIReviewStatus = refreshAIReviewStatus;
window.requestAISpeakerMap = requestAISpeakerMap;
window.requestAIAnalysis = requestAIAnalysis;
window.loadAISuggestions = loadAISuggestions;
window.approveAISuggestion = approveAISuggestion;
window.rejectAISuggestion = rejectAISuggestion;
// Workspace job context (binds the AI review queue to a job)
window.loadWorkspaceJobContext = loadWorkspaceJobContext;
