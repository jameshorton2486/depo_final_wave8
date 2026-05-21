        function signTranscript() {
            const sig = document.getElementById('reporterSignatureInput').value.trim();
            const check1 = document.getElementById('certCheck1').checked;
            const check2 = document.getElementById('certCheck2').checked;
            const check3 = document.getElementById('certCheck3').checked;

            if (!sig) {
                showToast("Digital Signature signature code cannot be blank.", "red");
                return;
            }
            if (!check1 || !check2 || !check3) {
                showToast("Please acknowledge and confirm all legal certification parameters.", "red");
                return;
            }

            state.caseInfo.certified = true;
            state.caseInfo.signature = sig;

            document.getElementById('badgeWorking').classList.add('hidden');
            document.getElementById('badgeCertified').classList.remove('hidden');

            document.getElementById('renderedSignatory').innerText = sig;
            document.getElementById('lockTimestamp').innerText = new Date().toLocaleString();

            document.getElementById('certPreLock').classList.add('hidden');
            document.getElementById('certPostLock').classList.remove('hidden');

            addProvenanceRecord("Case Bundle Certified", `Court Reporter signature sealed under certificate key [${sig}]`, "system");
            showToast("Deposition successfully locked and certified!", "emerald");
        }


window.signTranscript = signTranscript;
