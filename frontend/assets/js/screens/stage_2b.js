/**
 * Stage 2b — DEPRECATED.
 *
 * DEPRECATED — authoritative speaker mapping now occurs in Stage 3 Workspace.
 *
 * This file is preserved temporarily for compatibility with any stale
 * route references. It no longer loads or saves speaker assignments.
 */

window.addEventListener("screen:loaded", (e) => {
    if (!e.detail || e.detail.stageNum !== "2b") return;
    const tab2 = document.getElementById("stageTab2");
    if (tab2) {
        tab2.className = "px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 shadow-sm";
    }
    const root = document.getElementById("speakerMappingRoot");
    if (root) {
        root.innerHTML = `
            <div class="max-w-3xl bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
                <p class="text-sm font-bold text-white mb-2">Stage 2b is deprecated.</p>
                <p class="text-xs text-slate-400 leading-relaxed">
                    Open Stage 3 Workspace to review diarization and save the authoritative speaker map.
                </p>
            </div>
        `;
    }
    console.info('[DEPO-PRO] Stage 2b opened in deprecated compatibility mode');
});
