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

        function _certHistoryState() {
            if (!state.certificationHistory) {
                state.certificationHistory = {
                    jobId: null,
                    packages: [],
                    snapshots: [],
                    lastLoadedAt: null,
                    lastError: null,
                };
            }
            return state.certificationHistory;
        }

        function _setCertLineageStatus(text, tone) {
            const el = document.getElementById('certLineageStatus');
            if (!el) return;
            const map = {
                idle: 'text-[10px] font-mono text-slate-500',
                loading: 'text-[10px] font-mono text-indigo-400',
                ready: 'text-[10px] font-mono text-emerald-400',
                warning: 'text-[10px] font-mono text-amber-400',
                error: 'text-[10px] font-mono text-red-400',
            };
            el.className = map[tone] || map.idle;
            el.innerText = text;
        }

        function renderCertificationHistory() {
            const list = document.getElementById('certHistoryList');
            const packageCount = document.getElementById('certPackageCount');
            const snapshotCount = document.getElementById('certSnapshotCount');
            const latestVersion = document.getElementById('certLatestVersion');
            if (!list || !packageCount || !snapshotCount || !latestVersion) return;

            const hist = _certHistoryState();
            const packages = [...(hist.packages || [])];
            const snapshots = [...(hist.snapshots || [])];
            const certifiedPackages = packages.filter(p => p.package_state === 'CERTIFIED');
            const lockedSnapshots = snapshots.filter(s => s.locked);

            packageCount.innerText = String(certifiedPackages.length);
            snapshotCount.innerText = String(lockedSnapshots.length);
            latestVersion.innerText = certifiedPackages.length
                ? `v${certifiedPackages.length}`
                : 'None';

            if (!hist.jobId) {
                list.innerHTML = `<div class="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-xs text-slate-500 italic">Certification history will appear here after a transcript job is loaded.</div>`;
                _setCertLineageStatus('No transcript job loaded.', 'idle');
                return;
            }
            if (!packages.length && !snapshots.length) {
                list.innerHTML = `<div class="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-xs text-slate-500 italic">No certified lineage yet. The working transcript is still the only authoritative editable layer.</div>`;
                _setCertLineageStatus('Working transcript only.', 'warning');
                return;
            }

            const latestCertified = certifiedPackages[0] || null;
            if (latestCertified) {
                state.caseInfo.certified = true;
                state.caseInfo.packageId = latestCertified.package_id;
                const linked = lockedSnapshots.find(s => s.snapshot_id === latestCertified.snapshot_id);
                if (linked) state.caseInfo.certifiedSnapshotId = linked.snapshot_id;
                document.getElementById('badgeWorking')?.classList.remove('hidden');
                document.getElementById('badgeCertified')?.classList.remove('hidden');
                const pre = document.getElementById('certPreLock');
                const post = document.getElementById('certPostLock');
                if (pre) pre.classList.add('hidden');
                if (post) post.classList.remove('hidden');
                const lockTimestamp = document.getElementById('lockTimestamp');
                const packageIdDisplay = document.getElementById('packageIdDisplay');
                const manifestHashDisplay = document.getElementById('manifestHashDisplay');
                const renderedSignatory = document.getElementById('renderedSignatory');
                if (lockTimestamp) lockTimestamp.innerText = latestCertified.certified_at
                    ? new Date(latestCertified.certified_at).toLocaleString()
                    : '—';
                if (packageIdDisplay) packageIdDisplay.innerText = latestCertified.package_id || '—';
                if (manifestHashDisplay) manifestHashDisplay.innerText = latestCertified.manifest_hash
                    ? `${latestCertified.manifest_hash.slice(0, 20)}...`
                    : '—';
                if (renderedSignatory) renderedSignatory.innerText = linked && linked.created_by
                    ? linked.created_by
                    : (state.caseInfo.signature || '—');
            } else {
                state.caseInfo.certified = false;
                state.caseInfo.packageId = '';
                state.caseInfo.certifiedSnapshotId = '';
                document.getElementById('badgeCertified')?.classList.add('hidden');
                document.getElementById('badgeWorking')?.classList.remove('hidden');
                document.getElementById('certPreLock')?.classList.remove('hidden');
                document.getElementById('certPostLock')?.classList.add('hidden');
            }

            const rows = [];
            certifiedPackages.forEach((pkg, idx) => {
                const snapshot = lockedSnapshots.find(s => s.snapshot_id === pkg.snapshot_id);
                rows.push(`
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-3">
                        <div class="flex items-center justify-between gap-2 mb-1">
                            <div class="text-xs font-semibold text-white">Certified Package ${idx === 0 ? '(Latest)' : ''}</div>
                            <span class="text-[10px] font-mono text-emerald-400">PACKAGE ${pkg.package_id.slice(0, 8)}</span>
                        </div>
                        <div class="text-[11px] text-slate-400 font-mono">Snapshot: ${(snapshot && snapshot.snapshot_id) ? snapshot.snapshot_id.slice(0, 12) : pkg.snapshot_id}</div>
                        <div class="text-[11px] text-slate-500 font-mono">Certified: ${pkg.certified_at ? new Date(pkg.certified_at).toLocaleString() : 'pending'}</div>
                        <div class="text-[11px] text-slate-500 font-mono">Manifest: ${pkg.manifest_hash ? pkg.manifest_hash.slice(0, 20) + '...' : '—'}</div>
                    </div>
                `);
            });
            const workingCard = `
                <div class="bg-indigo-950/20 border border-indigo-500/20 rounded-xl p-3">
                    <div class="flex items-center justify-between gap-2 mb-1">
                        <div class="text-xs font-semibold text-white">Current Working Transcript</div>
                        <span class="text-[10px] font-mono text-amber-400">EDITABLE</span>
                    </div>
                    <div class="text-[11px] text-slate-400">Edits made after certification create future lineage only. Older certified packages remain immutable.</div>
                </div>
            `;
            list.innerHTML = workingCard + rows.join('');
            _setCertLineageStatus(
                certifiedPackages.length
                    ? `${certifiedPackages.length} certified package(s), ${lockedSnapshots.length} locked snapshot(s).`
                    : `${lockedSnapshots.length} locked snapshot(s); no certified packages yet.`,
                certifiedPackages.length ? 'ready' : 'warning'
            );
        }

        async function loadCertificationHistory() {
            const jobId = _activeJobId();
            const hist = _certHistoryState();
            hist.jobId = jobId || null;
            hist.packages = [];
            hist.snapshots = [];
            renderCertificationHistory();
            if (!jobId || !window.api) return;
            _setCertLineageStatus('Loading certification lineage…', 'loading');
            try {
                const [packagesRes, snapshotsRes] = await Promise.all([
                    window.api.listPackages(jobId),
                    window.api.listSnapshots(jobId),
                ]);
                hist.packages = (packagesRes && packagesRes.packages) || [];
                hist.snapshots = (snapshotsRes && snapshotsRes.snapshots) || [];
                hist.lastLoadedAt = new Date().toISOString();
                hist.lastError = null;
                renderCertificationHistory();
            } catch (err) {
                hist.lastError = err.message || String(err);
                renderCertificationHistory();
                _setCertLineageStatus(`Lineage load failed: ${hist.lastError}`, 'error');
            }
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
                const snapRes = await api.createSnapshot(jobId, 'CERTIFIED', 'Certification snapshot', sig);
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

                document.getElementById('badgeWorking').classList.remove('hidden');
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
                await loadCertificationHistory();
                showToast("Certified snapshot and package created. Working transcript remains editable for future versions.", "emerald");

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
window.loadCertificationHistory = loadCertificationHistory;
