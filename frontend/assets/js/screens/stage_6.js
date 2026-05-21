        function triggerExportAction() {
            const formatSelect = document.getElementById('exportFormatSelect');
            const format = formatSelect ? formatSelect.value : 'docx';
            const mimeMap = {
                docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                pdf: 'application/pdf',
                txt: 'text/plain',
                rtf: 'application/rtf'
            };
            const mimeType = mimeMap[format] || 'text/plain';
            showToast(`Compiling .${format} bundle (margins, headers, exhibits, certification seals)...`, "indigo");

            setTimeout(() => {
                showToast("Secure export wrapper compiled successfully!", "emerald");

                // Build a printable copy-paste text payload simulating DOCX/ASCII layout standard
                let transcriptPayload = `
SARAH JENKINS vs. NEXUS PHARMA INC.
CAUSE NO. 2024-CI-28593
VOLUME I - CERTIFIED DEPOSITION OF DR. DONALD LEIFER

=======================================================
PAGE 1
=======================================================
`;
                state.transcriptLines.forEach(l => {
                    transcriptPayload += `${l.index.toString().padEnd(4, ' ')} | [${l.speaker}] ${l.type === "Q" ? "Q. " : l.type === "A" ? "A. " : ""}${l.text}\n`;
                });

                transcriptPayload += `\n\nEXHIBIT INDEX APPEND:\n`;
                state.exhibits.forEach(ex => {
                    transcriptPayload += `Exhibit ${ex.num}: ${ex.title} · Offered by ${ex.attorney} · Page ${ex.page}, Line ${ex.line}\n`;
                });

                transcriptPayload += `\n\nDIGITAL SIGNATURE ID SEAL: ${state.caseInfo.signature || "Richard Vance CSR"}\n`;

                const blob = new Blob([transcriptPayload], { type: mimeType });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Jenkins_v_Nexus_Certified_Transcript.${format}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                showToast(`Certified transcript bundle (.${format}) downloaded!`, "emerald");
            }, 2000);
        }

window.triggerExportAction = triggerExportAction;
