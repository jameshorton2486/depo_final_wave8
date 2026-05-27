/**
 * HTTP client for the DEPO-PRO backend.
 *
 * The frontend's `state.caseInfo` uses UI field names (cause, caption,
 * deponent, ...). The backend speaks the canonical schema names
 * (case_number_value, witness_name, ...). The translation lives here
 * so the rest of the frontend never has to think about it.
 */
(function () {
    const API_BASE = '/api';

    // ====================================================================
    // CASES (Block 1)
    // ====================================================================

    function caseInfoToCasePayload(caseInfo) {
        return {
            case_number_value: (caseInfo.cause || '').trim() || 'UNSET',
            jurisdiction_type: 'texas_state',
            case_number_label: 'cause_no',
            caption_full: caseInfo.caption || null,
            judicial_district: caseInfo.court || null,
            county: caseInfo.county || null,
            state: caseInfo.state || 'Texas',
        };
    }

    function caseRowToCaseInfo(row) {
        return {
            cause: row.case_number_value === 'UNSET' ? '' : (row.case_number_value || ''),
            caption: row.caption_full || '',
            court: row.judicial_district || row.court_district || '',
            county: row.county || '',
            state: row.state || 'Texas',
        };
    }

    // ====================================================================
    // SESSIONS (Block 2 + Block 4 fields)
    // ====================================================================

    /** Combine date + AM/PM time string into an ISO 8601 datetime (no TZ; backend defaults TZ). */
    function combineDateTime(dateStr, timeStr) {
        if (!dateStr) return null;
        if (!timeStr) return `${dateStr}T00:00:00`;
        // Accept "10:00 AM" or "12:30 PM" or "10:00"
        const m = String(timeStr).trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i);
        if (!m) return `${dateStr}T00:00:00`;
        let hour = parseInt(m[1], 10);
        const minute = m[2];
        const ampm = (m[3] || '').toUpperCase();
        if (ampm === 'PM' && hour < 12) hour += 12;
        if (ampm === 'AM' && hour === 12) hour = 0;
        return `${dateStr}T${String(hour).padStart(2, '0')}:${minute}:00`;
    }

    /** Pull HH:MM AM/PM out of an ISO 8601 string for UI display. */
    function isoToTimeOfDay(iso) {
        if (!iso) return '';
        const m = String(iso).match(/T(\d{2}):(\d{2})/);
        if (!m) return '';
        let hour = parseInt(m[1], 10);
        const minute = m[2];
        const ampm = hour >= 12 ? 'PM' : 'AM';
        if (hour === 0) hour = 12;
        else if (hour > 12) hour -= 12;
        return `${hour}:${minute} ${ampm}`;
    }

    function isoToDate(iso) {
        if (!iso) return '';
        const m = String(iso).match(/^(\d{4}-\d{2}-\d{2})/);
        return m ? m[1] : '';
    }

    function caseInfoToSessionPayload(caseInfo, caseId) {
        return {
            case_id: caseId,
            scheduled_at: combineDateTime(caseInfo.date, caseInfo.startTime),
            scheduled_end_at: combineDateTime(caseInfo.date, caseInfo.endTime),
            witness_name: (caseInfo.deponent || '').trim() || 'UNSET',
            location_type: 'in_person',
            location_address: caseInfo.address || null,
            service_type: 'CR_only',
            custodial_attorney_name: caseInfo.custodialName || null,
            requesting_party_name: caseInfo.requestingParty || null,
        };
    }

    function sessionRowToCaseInfoPatch(row) {
        return {
            deponent: row.witness_name === 'UNSET' ? '' : (row.witness_name || ''),
            date: isoToDate(row.scheduled_at),
            startTime: isoToTimeOfDay(row.scheduled_at),
            endTime: isoToTimeOfDay(row.scheduled_end_at),
            address: row.location_address || '',
            custodialName: row.custodial_attorney_name || '',
            requestingParty: row.requesting_party_name || '',
        };
    }

    // ====================================================================
    // REPORTERS (Block 3)
    // ====================================================================

    function caseInfoToReporterPayload(caseInfo) {
        return {
            full_name: (caseInfo.csrName || '').trim() || 'UNSET',
            csr_number: caseInfo.csrLicense || null,
            csr_expiration: caseInfo.csrCertExp || null,
            firm_registration_number: caseInfo.firmReg || null,
        };
    }

    function reporterRowToCaseInfoPatch(row) {
        return {
            csrName: row.full_name === 'UNSET' ? '' : (row.full_name || ''),
            csrLicense: row.csr_number || '',
            csrCertExp: row.csr_expiration || '',
            firmReg: row.firm_registration_number || '',
        };
    }

    function buildStage1SyncPayload(stateObj) {
        const caseInfo = stateObj.caseInfo || {};
        const stage1 = stateObj.stage1 || {};
        return {
            case_id: stateObj.caseId,
            session_id: stateObj.sessionId,
            reporter_name: (caseInfo.csrName || '').trim() || null,
            ufmCause: caseInfo.cause || null,
            ufmStyle: caseInfo.caption || null,
            ufmCourt: caseInfo.court || null,
            ufmCounty: caseInfo.county || null,
            ufmState: caseInfo.state || 'Texas',
            jurisdiction_type: (stage1.parserMetadata && stage1.parserMetadata.jurisdiction_type) || 'texas_state',
            ufmWitness: caseInfo.deponent || null,
            ufmDate: caseInfo.date || null,
            ufmStartTime: caseInfo.startTime || null,
            ufmEndTime: caseInfo.endTime || null,
            ufmAddress: caseInfo.address || null,
            location_type: (stage1.parserMetadata && stage1.parserMetadata.location_type) || 'unknown',
            ufmCSRName: caseInfo.csrName || null,
            ufmCSRLicense: caseInfo.csrLicense || null,
            ufmFirmReg: caseInfo.firmReg || null,
            ufmCSRCertExp: caseInfo.csrCertExp || null,
            raw_intake_notes: stage1.rawIntakeNotes || '',
            parser_metadata: stage1.parserMetadata || {},
            keyterms: stage1.keytermEntries || [],
        };
    }

    // ====================================================================
    // Generic HTTP helper
    // ====================================================================

    async function _fetch(method, path, body) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body !== undefined) opts.body = JSON.stringify(body);

        let res;
        try {
            res = await fetch(API_BASE + path, opts);
        } catch (networkErr) {
            // fetch() itself rejects (vs. an HTTP error status) when the
            // backend is unreachable -- server not started, wrong port,
            // crashed process. Turn the opaque "Failed to fetch" into
            // something the user can act on.
            console.error('[DEPO-PRO] Network error on', method, path, networkErr);
            const err = new Error(
                'Cannot reach the DEPO-PRO backend. Make sure the server is ' +
                'running, then try again. (' + method + ' ' + path + ')'
            );
            err.status = 0;
            throw err;
        }
        if (res.status === 204) return null;

        let payload = null;
        try {
            payload = await res.json();
        } catch (_) {
            payload = null;
        }

        if (!res.ok) {
            const detail =
                payload && payload.detail
                    ? typeof payload.detail === 'string'
                        ? payload.detail
                        : JSON.stringify(payload.detail)
                    : `HTTP ${res.status}`;
            const err = new Error(detail);
            err.status = res.status;
            err.payload = payload;
            throw err;
        }
        return payload;
    }

    /** Have enough required fields to attempt a session save? */
    function canSaveSession(caseInfo) {
        return !!(caseInfo.date && (caseInfo.deponent || '').trim());
    }

    /** Have enough required fields to attempt a reporter save? */
    function canSaveReporter(caseInfo) {
        return !!(caseInfo.csrName || '').trim();
    }

    // ====================================================================
    // TRANSCRIPTS (Stage 2 engine)
    // ====================================================================

    /**
     * Upload one media file as multipart/form-data and queue a
     * transcription job. Returns the created job (status 'queued').
     * Distinct from _fetch() because this sends FormData, not JSON.
     */
    async function uploadTranscriptFile(file, opts) {
        opts = opts || {};
        const form = new FormData();
        form.append('file', file);
        if (opts.caseId) form.append('case_id', opts.caseId);
        if (opts.sessionId) form.append('session_id', opts.sessionId);
        form.append('sequence_index', String(opts.sequenceIndex || 0));

        let res;
        try {
            res = await fetch(API_BASE + '/transcripts/upload', {
                method: 'POST',
                body: form,
            });
        } catch (networkErr) {
            console.error('[DEPO-PRO] Network error uploading transcript file', networkErr);
            const err = new Error(
                'Cannot reach the DEPO-PRO backend to upload "' +
                (file && file.name ? file.name : 'file') +
                '". Make sure the server is running, then try again.'
            );
            err.status = 0;
            throw err;
        }
        let payload = null;
        try { payload = await res.json(); } catch (_) { payload = null; }
        if (!res.ok) {
            const detail = payload && payload.detail
                ? (typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail))
                : `HTTP ${res.status}`;
            const err = new Error(detail);
            err.status = res.status;
            throw err;
        }
        return payload;
    }

    const api = {
        // Translators (exposed for app.js)
        caseInfoToCasePayload,
        caseRowToCaseInfo,
        caseInfoToSessionPayload,
        sessionRowToCaseInfoPatch,
        caseInfoToReporterPayload,
        reporterRowToCaseInfoPatch,
        canSaveSession,
        canSaveReporter,
        buildStage1SyncPayload,

        // Cases
        listCases() {
            return _fetch('GET', '/cases');
        },
        getCase(caseId) {
            return _fetch('GET', `/cases/${encodeURIComponent(caseId)}`);
        },
        createCase(caseInfo) {
            return _fetch('POST', '/cases', caseInfoToCasePayload(caseInfo));
        },
        updateCase(caseId, caseInfo) {
            return _fetch('PUT', `/cases/${encodeURIComponent(caseId)}`, caseInfoToCasePayload(caseInfo));
        },
        deleteCase(caseId) {
            return _fetch('DELETE', `/cases/${encodeURIComponent(caseId)}`);
        },

        // Sessions
        listSessionsForCase(caseId) {
            return _fetch('GET', `/sessions?case_id=${encodeURIComponent(caseId)}`);
        },
        getSession(sessionId) {
            return _fetch('GET', `/sessions/${encodeURIComponent(sessionId)}`);
        },
        createSession(caseInfo, caseId) {
            return _fetch('POST', '/sessions', caseInfoToSessionPayload(caseInfo, caseId));
        },
        updateSession(sessionId, caseInfo, caseId) {
            const body = caseInfoToSessionPayload(caseInfo, caseId);
            // Update payload does not include case_id
            delete body.case_id;
            return _fetch('PUT', `/sessions/${encodeURIComponent(sessionId)}`, body);
        },

        // Reporters
        listReporters() {
            return _fetch('GET', '/reporters');
        },
        getReporter(reporterId) {
            return _fetch('GET', `/reporters/${encodeURIComponent(reporterId)}`);
        },
        createReporter(caseInfo) {
            return _fetch('POST', '/reporters', caseInfoToReporterPayload(caseInfo));
        },
        updateReporter(reporterId, caseInfo) {
            return _fetch('PUT', `/reporters/${encodeURIComponent(reporterId)}`, caseInfoToReporterPayload(caseInfo));
        },

        // Stage 1 authoritative artifact sync
        syncStage1Artifacts(stateObj) {
            return _fetch('POST', '/intake/workspace', buildStage1SyncPayload(stateObj));
        },
        getStage1Artifacts(caseId) {
            return _fetch('GET', `/intake/cases/${encodeURIComponent(caseId)}`);
        },

        // Transcripts (Stage 2)
        uploadTranscriptFile,
        listTranscriptJobs(caseId) {
            const q = caseId ? `?case_id=${encodeURIComponent(caseId)}` : '';
            return _fetch('GET', `/transcripts/jobs${q}`);
        },
        updateTranscriptJob(jobId, payload) {
            return _fetch('PUT', `/transcripts/jobs/${encodeURIComponent(jobId)}`, payload || {});
        },
        getTranscriptJob(jobId) {
            return _fetch('GET', `/transcripts/jobs/${encodeURIComponent(jobId)}`);
        },
        getTranscriptContent(jobId) {
            return _fetch('GET', `/transcripts/jobs/${encodeURIComponent(jobId)}/content`);
        },
        getTranscriptMediaUrl(jobId) {
            return `${API_BASE}/transcripts/jobs/${encodeURIComponent(jobId)}/media`;
        },
        listTranscriptExhibits(jobId) {
            return _fetch('GET', `/exhibits/jobs/${encodeURIComponent(jobId)}`);
        },
        createTranscriptExhibit(jobId, payload) {
            return _fetch('POST', `/exhibits/jobs/${encodeURIComponent(jobId)}`, payload || {});
        },
        updateTranscriptExhibit(exhibitId, payload) {
            return _fetch('PUT', `/exhibits/${encodeURIComponent(exhibitId)}`, payload || {});
        },
        deleteTranscriptExhibit(exhibitId) {
            return _fetch('DELETE', `/exhibits/${encodeURIComponent(exhibitId)}`);
        },
        saveWorkingTranscript(jobId, utterances, source) {
            return _fetch('PUT', `/transcripts/jobs/${encodeURIComponent(jobId)}/working-transcript`, {
                utterances: utterances || [],
                source: source || 'stage3_workspace',
            });
        },
        listTranscriptProvenance(jobId) {
            return _fetch('GET', `/transcripts/jobs/${encodeURIComponent(jobId)}/provenance`);
        },
        recordTranscriptProvenance(jobId, payload) {
            return _fetch('POST', `/transcripts/jobs/${encodeURIComponent(jobId)}/provenance`, payload || {});
        },
        // Stage 3 Workspace is the authoritative speaker-mapping UI.
        // These APIs remain under /transcripts for compatibility.
        getSpeakerMapping(jobId) {
            return _fetch('GET', `/transcripts/jobs/${encodeURIComponent(jobId)}/speaker-mapping`);
        },
        saveSpeakerMapping(jobId, participants) {
            return _fetch('PUT', `/transcripts/jobs/${encodeURIComponent(jobId)}/speaker-mapping`, { participants });
        },
        applySpeakerMapping(jobId, participants) {
            // Wave 11: persist + re-render WORKING transcript + re-run engine.
            return _fetch('POST', `/transcripts/jobs/${encodeURIComponent(jobId)}/speaker-mapping/apply`, { participants });
        },
        getExportPreview(jobId) {
            // Wave 12: canonical paginated export document for a saved job.
            return _fetch('GET', `/transcripts/jobs/${encodeURIComponent(jobId)}/export-preview`);
        },
        getExportPreviewFallback(payload) {
            // Wave 12: export preview for a transient unsaved transcript.
            return _fetch('POST', '/transcripts/export-preview/fallback', payload);
        },
        exportTranscript(jobId, fmt, destination, explicitPath, snapshotId) {
            // Wave 18: backend renders and writes a real file to disk.
            return _fetch('POST', `/transcripts/jobs/${encodeURIComponent(jobId)}/export`, {
                fmt: fmt,
                destination: destination,
                explicit_path: explicitPath || null,
                snapshot_id: snapshotId || null,
            });
        },
        // --- AI review layer (Wave 15b / 16) ------------------------
        getAIReviewStatus() {
            return _fetch('GET', '/ai-review/status');
        },
        generateAISpeakerMap(jobId) {
            return _fetch('POST', `/ai-review/jobs/${encodeURIComponent(jobId)}/speaker-map`);
        },
        analyzeAIJob(jobId, kinds) {
            // kinds: optional comma-separated subset of boundaries,garbles,flags
            const q = kinds ? `?kinds=${encodeURIComponent(kinds)}` : '';
            return _fetch('POST', `/ai-review/jobs/${encodeURIComponent(jobId)}/analyze${q}`);
        },
        listAISuggestions(jobId) {
            return _fetch('GET', `/ai-review/jobs/${encodeURIComponent(jobId)}/suggestions`);
        },
        approveAISuggestion(suggestionId) {
            return _fetch('POST', `/ai-review/suggestions/${encodeURIComponent(suggestionId)}/approve`);
        },
        applyAISuggestion(suggestionId) {
            return _fetch('POST', `/ai-review/suggestions/${encodeURIComponent(suggestionId)}/apply`);
        },
        rejectAISuggestion(suggestionId) {
            return _fetch('POST', `/ai-review/suggestions/${encodeURIComponent(suggestionId)}/reject`);
        },
        getTranscriptRawPacket(jobId) {
            return _fetch('GET', `/transcripts/jobs/${encodeURIComponent(jobId)}/raw`);
        },
        getTranscriptWorkingPacket(jobId) {
            return _fetch('GET', `/transcripts/jobs/${encodeURIComponent(jobId)}/packet`);
        },
        deleteTranscriptJob(jobId) {
            return _fetch('DELETE', `/transcripts/jobs/${encodeURIComponent(jobId)}`);
        },
        readbackSearch(query, caseId) {
            const body = { query };
            if (caseId) body.case_id = caseId;
            return _fetch('POST', '/transcripts/readback', body);
        },

        // Snapshots (packaging workflow — Wave 18.5)
        createSnapshot(jobId, category, note, createdBy) {
            return _fetch('POST', `/snapshots/jobs/${encodeURIComponent(jobId)}`,
                          {
                              category: category || 'CERTIFIED',
                              note: note || '',
                              created_by: createdBy || '',
                          });
        },
        listSnapshots(jobId) {
            return _fetch('GET', `/snapshots/jobs/${encodeURIComponent(jobId)}`);
        },
        getSnapshot(snapshotId) {
            return _fetch('GET', `/snapshots/${encodeURIComponent(snapshotId)}`);
        },
        lockSnapshot(snapshotId) {
            return _fetch('POST', `/snapshots/${encodeURIComponent(snapshotId)}/lock`);
        },
        rollbackSnapshot(jobId, snapshotId, createdBy) {
            return _fetch('POST', `/snapshots/jobs/${encodeURIComponent(jobId)}/rollback`, {
                snapshot_id: snapshotId,
                created_by: createdBy || 'workspace',
            });
        },

        // Packages (Wave 20)
        assemblePackage(jobId, snapshotId, metadata) {
            return _fetch('POST', `/packages/jobs/${encodeURIComponent(jobId)}`, {
                snapshot_id: snapshotId,
                metadata: metadata || {},
                freelance: true,
            });
        },
        listPackages(jobId) {
            return _fetch('GET', `/packages/jobs/${encodeURIComponent(jobId)}`);
        },
        getPackage(packageId) {
            return _fetch('GET', `/packages/${encodeURIComponent(packageId)}`);
        },
        certifyPackage(packageId, metadata) {
            return _fetch('POST', `/packages/${encodeURIComponent(packageId)}/certify`,
                          { metadata: metadata || {} });
        },

        // Health
        healthCheck() {
            return _fetch('GET', '/health');
        },
    };

    window.api = api;
})();
