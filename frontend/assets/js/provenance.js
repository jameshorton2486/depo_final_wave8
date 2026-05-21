        function renderProvenanceTimeline() {
            const container = document.getElementById('provenanceLogContainer');
            if (!container) return;
            container.innerHTML = "";
            state.provenance.slice().reverse().forEach(log => {
                const item = document.createElement('div');
                item.className = "flex gap-2.5 items-start border-b border-slate-900 pb-2.5 last:border-0 last:pb-0";

                let dotColor = "bg-indigo-500";
                if (log.type === "system") dotColor = "bg-slate-500";
                if (log.type === "ai") dotColor = "bg-amber-500";

                item.innerHTML = `
                    <div class="w-1.5 h-1.5 rounded-full ${dotColor} mt-1.5 shrink-0"></div>
                    <div class="flex-1 font-mono">
                        <div class="flex items-center justify-between">
                            <p class="text-[11px] font-bold text-white">${log.title}</p>
                            <span class="text-[9px] text-slate-500">${log.timestamp}</span>
                        </div>
                        <p class="text-[10px] text-slate-400 mt-0.5 font-sans leading-relaxed">${log.text}</p>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        function addProvenanceRecord(title, text, type = 'user') {
            const date = new Date();
            const timestamp = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')} AM`;
            state.provenance.push({ title, text, timestamp, type });
            renderProvenanceTimeline();
        }


window.renderProvenanceTimeline = renderProvenanceTimeline;
window.addProvenanceRecord = addProvenanceRecord;
