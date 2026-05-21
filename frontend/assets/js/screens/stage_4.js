        function renderExhibitsIndex() {
            const container = document.getElementById('exhibitsIndexList');
            if (!container) return;
            container.innerHTML = "";
            state.exhibits.forEach(ex => {
                const div = document.createElement('div');
                div.className = "bg-slate-950 p-4 rounded-xl border border-slate-800 flex items-center justify-between gap-4 font-sans";
                div.innerHTML = `
                    <div>
                        <span class="text-[9px] font-bold tracking-wider uppercase bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/20">Exhibit ${ex.num}</span>
                        <h4 class="text-sm font-bold text-white mt-1">${ex.title}</h4>
                        <p class="text-xs text-slate-400 mt-0.5">Offered by: ${ex.attorney} · Recorded on Line ${ex.line}</p>
                    </div>
                    <div class="text-right font-mono">
                        <span class="text-xs text-indigo-400 font-bold block">PAGE ${ex.page} : LINE ${ex.line}</span>
                        <button onclick="quickJumpToLine('line-${ex.line}')" class="text-[10px] text-slate-500 hover:text-white transition-all underline mt-1">Jump to Anchor</button>
                    </div>
                `;
                container.appendChild(div);
            });
        }

        function createNewExhibitMark() {
            const nextNum = state.exhibits.length + 1;
            state.exhibits.push({
                id: `ex-${nextNum}`,
                num: nextNum,
                title: "Simulated Custom Exhibit Insertion",
                page: 1,
                line: 7,
                attorney: "Richard Vance, Esq."
            });
            renderExhibitsIndex();
            showToast(`Exhibit ${nextNum} successfully cataloged.`);
        }

        function quickJumpToLine(id) {
            goToStage(3);
            setTimeout(() => {
                const el = document.getElementById(id);
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    focusLineRow(id);
                }
            }, 300);
        }

window.renderExhibitsIndex = renderExhibitsIndex;
window.createNewExhibitMark = createNewExhibitMark;
window.quickJumpToLine = quickJumpToLine;
