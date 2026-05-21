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

        // Sidebar rendering drivers
        function renderSpeakersList() {
            const list = document.getElementById('speakersList');
            if (!list) return;
            list.innerHTML = "";
            const distinct = [...new Set(state.transcriptLines.map(l => l.speaker).filter(s => s !== "SYSTEM" && s !== "SYSTEM INDEXER"))];

            distinct.forEach(sp => {
                const item = document.createElement('div');
                item.className = "flex items-center justify-between bg-slate-950/40 p-2 rounded-lg border border-slate-800/80 hover:border-slate-700 transition-all cursor-pointer";
                item.innerHTML = `
                    <div class="flex items-center gap-2 font-mono">
                        <span class="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                        <span class="text-xs font-bold text-white">${sp}</span>
                    </div>
                    <span class="text-[9px] text-slate-500 font-mono font-sans">Speaker Block</span>
                `;
                list.appendChild(item);
            });
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
window.renderSpeakersList = renderSpeakersList;
window.renderCorrectionMemory = renderCorrectionMemory;
