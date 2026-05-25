        const state = {
            currentStage: 1,
            workspaceMode: 'edit', // edit, suggestions, audio, formatting
            canvasTheme: 'dark', // dark, word (MS Word Mockup)

            // Server-side identity for the case being edited. Null until the
            // first save (POST). On subsequent saves we PUT to /api/cases/{caseId}.
            caseId: null,
            sessionId: null,
            reporterId: null,
            stage1: {
                rawIntakeNotes: "",
                keytermEntries: [],
                parserMetadata: {
                    appearances: [],
                    speaker_hints: [],
                    deepgram_config: {},
                    jurisdiction_type: "texas_state",
                    location_type: "unknown",
                    detected_types: [],
                    warnings: [],
                    field_sources: {},
                },
                workspace: {
                    sessions: {},
                },
            },

            // Texas UFM Mandatory Schema Mapping (Binds directly to verified input UI)
            caseInfo: {
                cause: "",
                caption: "",
                court: "",
                county: "",
                state: "",
                deponent: "",
                date: "",
                startTime: "",
                endTime: "",
                address: "",
                csrName: "",
                csrLicense: "",
                firmReg: "",
                csrCertExp: "",
                custodialName: "",
                requestingParty: "",
                strictLineLock: true,
                signature: "",
                certified: false
            },

            // Multiple Files Processing Sequence Queue State
            fileQueue: [],
            isQueueProcessing: false,
            elapsedProcessTime: 0,
            elapsedTimerInterval: null,

            // Sequence of transcript lines containing alignments, confidence arrays, and metadata
            // Populated from real ingested transcripts (Stage 2 -> Stage 3).
            transcriptLines: [],
            exhibits: [],
            correctionsMemory: [],
            provenance: [],
            activePlayback: false,
            playbackInterval: null,
            playbackLineIdx: 0,
            playbackSpeed: 1.0,
            focusedLineId: null,

            // Audio input streaming configuration
            isStreaming: false,
            audioContext: null,
            audioAnalyser: null,
            micStream: null,
            visualizerTimer: null,
            liveTranscriptCounter: 10,
            liveSearchQuery: "",

            // Stage 2 transcripts engine — real server-backed ingestion.
            // transcriptJobs holds the persisted jobs loaded from the
            // backend; readbackTimer debounces the read-back search.
            transcriptJobs: [],
            readbackTimer: null,

            // Transcript workflow bindings.
            activeTranscriptJobIds: [],
            workspaceJob: {
                jobId: null,
            },
            workspaceSpeakerMapping: {
                jobs: [],
                assignments: {},
            },
            workspaceSnapshots: {
                jobId: null,
                items: [],
                selectedSnapshotId: null,
                lastLoadedAt: null,
            },
            workspaceSave: {
                dirty: false,
                pending: false,
                saving: false,
                lastSavedAt: null,
                lastError: null,
                timer: null,
            }
        };
window.state = state;
