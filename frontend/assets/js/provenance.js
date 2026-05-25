        function _activeProvenanceJobId() {
            const ids = (state && state.activeTranscriptJobIds) || [];
            return ids.length > 0 ? ids[0] : null;
        }

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
                            <span class="text-[9px] text-slate-500">${log.timestamp || ''}</span>
                        </div>
                        <p class="text-[10px] text-slate-400 mt-0.5 font-sans leading-relaxed">${log.text}</p>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        async function loadTranscriptProvenance(jobId) {
            if (!jobId || !window.api || typeof window.api.listTranscriptProvenance !== 'function') {
                return;
            }
            try {
                const res = await window.api.listTranscriptProvenance(jobId);
                state.provenance = (res.events || []).map(ev => ({
                    id: ev.event_id,
                    title: ev.title,
                    text: ev.detail || '',
                    timestamp: ev.created_at,
                    type: ev.actor_type || 'system',
                    metadata: ev.metadata || {},
                    source: ev.source || '',
                }));
                renderProvenanceTimeline();
            } catch (err) {
                console.warn('Could not load transcript provenance:', err);
            }
        }

        function addProvenanceRecord(title, text, type = 'user', options = {}) {
            const date = new Date();
            const timestamp = date.toLocaleString();
            const localRecord = {
                id: options.localId || `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
                title,
                text,
                timestamp,
                type,
                metadata: options.metadata || {},
                source: options.source || 'workspace',
            };
            state.provenance.push(localRecord);
            renderProvenanceTimeline();

            const jobId = options.jobId || _activeProvenanceJobId();
            if (!jobId || !window.api || typeof window.api.recordTranscriptProvenance !== 'function') {
                return;
            }
            window.api.recordTranscriptProvenance(jobId, {
                event_type: options.eventType || 'workspace_event',
                title: title,
                detail: text,
                actor_type: type,
                source: options.source || 'workspace',
                metadata: options.metadata || {},
                related_snapshot_id: options.relatedSnapshotId || '',
                related_suggestion_id: options.relatedSuggestionId || '',
                related_package_id: options.relatedPackageId || '',
            }).then(function (saved) {
                localRecord.id = saved.event_id;
                localRecord.timestamp = saved.created_at;
            }).catch(function (err) {
                console.warn('Could not persist provenance event:', err);
            });
        }


window.renderProvenanceTimeline = renderProvenanceTimeline;
window.addProvenanceRecord = addProvenanceRecord;
window.loadTranscriptProvenance = loadTranscriptProvenance;
