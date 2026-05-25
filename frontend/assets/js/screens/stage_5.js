        function _parseTimePerParty(raw) {
            if (!raw || !raw.trim()) return [];
            return raw.trim().split('\n').map(line => {
                const idx = line.lastIndexOf('-');
                if (idx === -1) return { party: line.trim(), duration: '' };
                return {
                    party: line.slice(0, idx).trim(),
                    duration: line.slice(idx + 1).trim()
                };
            }).filter(e => e.party);
        }

        function _activeJobId() {
            const ids = (state && state.activeTranscriptJobIds) || [];
            return ids.length > 0 ? ids[0] : null;
        }

        async function _saveCertFields() {
            const jobId = _activeJobId();
            if (!jobId) return;

            const disposition = document.getElementById('certExaminationDisposition').value;
            const volume = document.getElementById('certVolume').value.trim();
            const chargesAmount = document.getElementById('certChargesAmount').value.trim();
            const chargesParty = document.getElementById('certChargesParty').value.trim();
            const serviceDate = document.getElementById('certServiceDate').value.trim();
            const tppRaw = document.getElementById('certTimePerParty').value;

            const payload = {};
            if (disposition) payload.examination_disposition = disposition;
            if (volume) payload.volume = volume;
            if (chargesAmount) payload.officer_charges_amount = chargesAmount;
            if (chargesParty) payload.charges_party = chargesParty;
            if (serviceDate) payload.certificate_service_date = serviceDate;
            const tpp = _parseTimePerParty(tppRaw);
            if (tpp.length > 0) payload.time_per_party = tpp;

            try {
                const res = await fetch(`/api/depo-meta/jobs/${jobId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const statusEl = document.getElementById('certMetaSaveStatus');
                if (res.ok && statusEl) {
                    statusEl.classList.remove('hidden');
                    setTimeout(() => statusEl.classList.add('hidden'), 2000);
                }
            } catch (e) {
                console.warn('Could not save certificate fields:', e);
            }
        }

        async function loadCertFields() {
            const jobId = _activeJobId();
            if (!jobId) return;
            try {
                const res = await fetch(`/api/depo-meta/jobs/${jobId}`);
                if (!res.ok) return;
                const data = await res.json();
                if (data.examination_disposition)
                    document.getElementById('certExaminationDisposition').value = data.examination_disposition;
                if (data.volume)
                    document.getElementById('certVolume').value = data.volume;
                if (data.officer_charges_amount)
                    document.getElementById('certChargesAmount').value = data.officer_charges_amount;
                if (data.charges_party)
                    document.getElementById('certChargesParty').value = data.charges_party;
                if (data.certificate_service_date)
                    document.getElementById('certServiceDate').value = data.certificate_service_date;
                if (data.time_per_party && data.time_per_party.length > 0)
                    document.getElementById('certTimePerParty').value =
                        data.time_per_party.map(e => `${e.party} - ${e.duration}`).join('\n');
            } catch (e) {
                console.warn('Could not load certificate fields:', e);
            }
        }

        async function signTranscript() {
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

            const jobId = _activeJobId();
            if (!jobId) {
                showToast("No active job — cannot certify.", "red");
                return;
            }

            const btn = document.getElementById('signBtn');
            const errorArea = document.getElementById('certErrorArea');
            if (btn) btn.disabled = true;
            if (errorArea) {
                errorArea.classList.add('hidden');
                errorArea.innerHTML = '';
            }

            try {
                // 1. Persist the certificate data fields before signing.
                await _saveCertFields();

                // 2. Create and lock a certification snapshot.
                const snapRes = await api.createSnapshot(jobId, 'CERTIFIED', 'Certification snapshot', 'certification');
                const snapshotId = snapRes.snapshot_id;
                await api.lockSnapshot(snapshotId);

                // 3. Assemble the DRAFT package from the locked snapshot.
                const assembled = await api.assemblePackage(jobId, snapshotId);
                const packageId = assembled.package_id;

                // 4. Certify the package — the one-way finalization step.
                const certified = await api.certifyPackage(packageId);

                // Success — populate UI with real API response data.
                state.caseInfo.certified = true;
                state.caseInfo.signature = sig;
                state.caseInfo.packageId = packageId;
                state.caseInfo.certifiedSnapshotId = snapshotId;

                document.getElementById('badgeWorking').classList.add('hidden');
                document.getElementById('badgeCertified').classList.remove('hidden');

                document.getElementById('renderedSignatory').innerText = sig;
                document.getElementById('lockTimestamp').innerText =
                    certified.certified_at
                        ? new Date(certified.certified_at).toLocaleString()
                        : new Date().toLocaleString();
                document.getElementById('packageIdDisplay').innerText =
                    certified.package_id || packageId;
                document.getElementById('manifestHashDisplay').innerText =
                    certified.manifest_hash
                        ? certified.manifest_hash.slice(0, 20) + '...'
                        : '—';

                document.getElementById('certPreLock').classList.add('hidden');
                document.getElementById('certPostLock').classList.remove('hidden');

                addProvenanceRecord(
                    "Case Bundle Certified",
                    `Package ${packageId} CERTIFIED — manifest hash ${(certified.manifest_hash || '').slice(0, 16)}`,
                    "system"
                );
                showToast("Deposition successfully locked and certified!", "emerald");

            } catch (err) {
                if (btn) btn.disabled = false;
                const detail = err.message || 'Certification failed.';
                if (errorArea) {
                    errorArea.classList.remove('hidden');
                    errorArea.innerHTML =
                        '<p class="font-semibold mb-1">Certification failed:</p>' +
                        '<p class="text-red-300">' + detail + '</p>';
                }
                showToast('Certification failed: ' + detail, 'red');
                addProvenanceRecord("Certification Failed", detail, "system");
            }
        }


window.signTranscript = signTranscript;
window.loadCertFields = loadCertFields;
