/**
 * Tiny client-side router for Depo-Pro Phase A.
 * Loads ui/screens/stage_N_*.html into #appRoot when goToStage(N) is called.
 * Caches loaded screens in memory after first fetch.
 */
const SCREEN_FILES = {
    1: "screens/stage_1_intake.html",
    2: "screens/stage_2_transcripts.html",
    "2b": "screens/stage_2b_speakers.html",
    3: "screens/stage_3_workspace.html",
    4: "screens/stage_4_insertions.html",
    5: "screens/stage_5_certify.html",
    6: "screens/stage_6_export.html",
};

const screenCache = {};
let currentStage = null;

async function loadScreen(stageNum) {
    if (!SCREEN_FILES[stageNum]) {
        console.error(`Unknown stage: ${stageNum}`);
        return;
    }

    const appRoot = document.getElementById("appRoot");
    if (!appRoot) {
        console.error("#appRoot element not found");
        return;
    }

    let html = screenCache[stageNum];
    if (!html) {
        try {
            const response = await fetch(SCREEN_FILES[stageNum]);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            html = await response.text();
            screenCache[stageNum] = html;
        } catch (err) {
            console.error(`Failed to load stage ${stageNum}:`, err);
            appRoot.innerHTML = `<div class="p-8 text-red-400">Failed to load screen ${stageNum}. See console.</div>`;
            return;
        }
    }

    appRoot.innerHTML = html;
    currentStage = stageNum;

    // Fire a custom event so per-screen init code can hook in (Phase A.2)
    window.dispatchEvent(new CustomEvent("screen:loaded", { detail: { stageNum } }));
}

// Initial load
window.addEventListener("DOMContentLoaded", () => loadScreen(1));
