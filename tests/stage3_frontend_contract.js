const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

class ClassList {
  constructor() {
    this._set = new Set();
  }
  add(...names) {
    names.forEach((n) => this._set.add(n));
  }
  remove(...names) {
    names.forEach((n) => this._set.delete(n));
  }
  contains(name) {
    return this._set.has(name);
  }
  toggle(name) {
    if (this._set.has(name)) {
      this._set.delete(name);
      return false;
    }
    this._set.add(name);
    return true;
  }
}

class FakeElement {
  constructor(tagName = 'div', id = '') {
    this.tagName = tagName.toUpperCase();
    this.id = id;
    this.value = '';
    this.checked = false;
    this.innerText = '';
    this.innerHTML = '';
    this.disabled = false;
    this.className = '';
    this.classList = new ClassList();
    this.children = [];
    this.style = {};
    this.attributes = {};
    this._listeners = new Map();
  }
  appendChild(child) {
    this.children.push(child);
    return child;
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
  removeAttribute(name) {
    delete this.attributes[name];
    if (name === 'src') this.src = '';
  }
  addEventListener(name, handler) {
    if (!this._listeners.has(name)) {
      this._listeners.set(name, []);
    }
    this._listeners.get(name).push(handler);
  }
  dispatchEvent(event) {
    const type = typeof event === 'string' ? event : event.type;
    const handlers = this._listeners.get(type) || [];
    handlers.forEach((handler) => handler({ type, target: this }));
  }
}

class FakeMediaElement extends FakeElement {
  constructor(context, tagName = 'audio') {
    super(tagName);
    this._context = context;
    this.currentTime = 0;
    this.duration = 0;
    this.playbackRate = 1.0;
    this.paused = true;
    this.src = '';
  }
  load() {
    const config = this._context.__mediaRegistry[this.src] || null;
    if (!this.src || (config && config.missing)) {
      this.dispatchEvent('error');
      return;
    }
    this.duration = config && Number.isFinite(config.duration) ? config.duration : 0;
    this.currentTime = config && Number.isFinite(config.currentTime) ? config.currentTime : this.currentTime;
    this.dispatchEvent('loadedmetadata');
  }
  play() {
    this.paused = false;
    this.dispatchEvent('play');
    return Promise.resolve();
  }
  pause() {
    this.paused = true;
    this.dispatchEvent('pause');
  }
}

function createContext() {
  const elements = new Map();
  const mediaRegistry = {};
  const ensure = (id) => {
    if (!elements.has(id)) {
      elements.set(id, new FakeElement('div', id));
    }
    return elements.get(id);
  };

  const document = {
    getElementById(id) {
      return ensure(id);
    },
    createElement(tag) {
      if (String(tag).toLowerCase() === 'audio' || String(tag).toLowerCase() === 'video') {
        return new FakeMediaElement(context, tag);
      }
      return new FakeElement(tag);
    },
    body: new FakeElement('body'),
  };

  const context = {
    console,
    setTimeout(fn) {
      if (typeof fn === 'function') fn();
      return 1;
    },
    clearTimeout() {},
    setInterval() { return 1; },
    clearInterval() {},
    Date,
    Promise,
    document,
    navigator: {
      clipboard: {
        writeText: async () => {},
      },
    },
    state: {
      canvasTheme: 'dark',
      workspaceMode: 'edit',
      transcriptLines: [],
      activeTranscriptJobIds: [],
      focusedLineId: null,
      correctionsMemory: [],
      caseInfo: {
        strictLineLock: false,
      },
      workspaceSave: {
        dirty: false,
        pending: false,
        saving: false,
        lastError: null,
        lastSavedAt: null,
      },
      activePlayback: false,
    },
    showToast() {},
    addProvenanceRecord() {},
    updateStatsBar() {},
    loadWorkspaceJobContext: async () => {},
    window: {
      addEventListener() {},
    },
  };
  context.window.document = document;
  context.window.state = context.state;
  context.window.showToast = context.showToast;
  context.window.addProvenanceRecord = context.addProvenanceRecord;
  context.globalThis = context;
  context.__elements = elements;
  context.__mediaRegistry = mediaRegistry;
  return context;
}

function seedStage3Elements(context) {
  [
    'transcriptLinesContainer',
    'compiledUFMTranscriptContainer',
    'transcriptCanvas',
    'lineRuleLeft',
    'lineRuleRight',
    'livePaginationStats',
    'workspaceSaveStatus',
    'workspaceSaveStatusDot',
    'workspaceSaveHint',
    'workspaceSaveBtn',
    'workspaceSpeakerMappingRoot',
    'workspaceSpeakerMappingStatus',
    'aiSuggestionsList',
    'flagCount',
    'audioTimeLabel',
    'playheadIndicator',
    'confidenceScoreLabel',
    'cursorLineTracker',
    'modeBannerText',
    'toolSectionAudio',
    'toolSectionSuggestions',
    'toolSectionFormatting',
    'rightPanelTitle',
    'modeBtnEdit',
    'modeBtnSuggestions',
    'modeBtnAudio',
    'modeBtnFormatting',
    'audioPlaybackNote',
    'workspaceMediaMount',
    'audioSpeedLabel',
    'playIconSvg',
  ].forEach((id) => context.document.getElementById(id));
}

function loadScript(context, relativePath) {
  const scriptPath = path.join(process.cwd(), ...relativePath.split('/'));
  const source = fs.readFileSync(scriptPath, 'utf8');
  vm.createContext(context);
  vm.runInContext(source, context, { filename: path.basename(scriptPath) });
}

async function testWorkspaceLoadPreservesOneLinePerUtteranceAndGroupsHeadersAtRender() {
  const context = createContext();
  seedStage3Elements(context);

  context.window.api = {
    getTranscriptMediaUrl: (jobId) => {
      const url = `/api/transcripts/jobs/${jobId}/media`;
      context.__mediaRegistry[url] = { duration: 8838 };
      return url;
    },
    getTranscriptContent: async () => ({
      job: { job_id: 'job-1', source_filename: 'sample.mp3', duration_seconds: 8838 },
      speakers: [
        { speaker_index: 0, speaker_label: 'Speaker 0' },
        { speaker_index: 1, speaker_label: 'Speaker 1' },
      ],
      participants: [],
      utterances: [
        {
          utterance_id: 'utt-1',
          speaker_index: 0,
          speaker_label: 'Speaker 0',
          text: 'First fragment.',
          raw_text: 'First fragment.',
          working_text: null,
          is_working_override: false,
          working_source: '',
          working_updated_at: '',
          avg_confidence: 0.97,
          start_time: 1.0,
          end_time: 2.0,
        },
        {
          utterance_id: 'utt-2',
          speaker_index: 0,
          speaker_label: 'Speaker 0',
          text: 'Second fragment.',
          raw_text: 'Second fragment.',
          working_text: null,
          is_working_override: false,
          working_source: '',
          working_updated_at: '',
          avg_confidence: 0.96,
          start_time: 2.2,
          end_time: 3.0,
        },
        {
          utterance_id: 'utt-3',
          speaker_index: 1,
          speaker_label: 'Speaker 1',
          text: 'Third fragment.',
          raw_text: 'Third fragment.',
          working_text: null,
          is_working_override: false,
          working_source: '',
          working_updated_at: '',
          avg_confidence: 0.95,
          start_time: 3.5,
          end_time: 4.2,
        },
      ],
      words: [],
    }),
  };
  context.api = context.window.api;

  loadScript(context, 'frontend/assets/js/screens/stage_3.js');
  loadScript(context, 'frontend/assets/js/screens/stage_2.js');

  await context.loadTranscriptResultsIntoWorkspace(['job-1']);

  assert.strictEqual(context.state.transcriptLines.length, 3);

  const container = context.document.getElementById('transcriptLinesContainer');
  assert.strictEqual(container.children.length, 3);

  const firstHtml = container.children[0].children[2].innerHTML;
  const secondHtml = container.children[1].children[2].innerHTML;
  const thirdHtml = container.children[2].children[2].innerHTML;

  assert.ok(firstHtml.includes('Speaker 0'));
  assert.ok(!secondHtml.includes('Speaker 0'));
  assert.ok(thirdHtml.includes('Speaker 1'));

  context.focusLineRow('utt-3');
  assert.strictEqual(
    context.document.getElementById('audioTimeLabel').innerText,
    '00:00 / 02:27:18',
  );
}

async function testCrossSpeakerBannerAndLockedReviewFlagsRender() {
  const context = createContext();
  seedStage3Elements(context);
  context.state.activeTranscriptJobIds = ['job-1'];
  context.updateStatsBar = function () {
    const count = Number.isInteger(context.state.reviewFlagCount)
      ? context.state.reviewFlagCount
      : 0;
    context.document.getElementById('flagCount').innerText = `${count} review flags`;
  };
  context.window.updateStatsBar = context.updateStatsBar;
  context.window.api = {
    getSpeakerMapping: async () => ({
      job_id: 'job-1',
      source_filename: 'sample.mp3',
      detected_speakers: [
        { speaker_index: 0, speaker_label: 'Speaker 0', word_count: 10, utterance_count: 2, sample: 'Sample' },
      ],
      participants: [],
      roles: [{ value: 'other', label: 'Other' }],
      is_prefill: true,
      candidate_names: [],
      cross_speaker_flags: {
        total: 3,
        mid_utterance_change: 1,
        flicker: 1,
        short_turn: 1,
        certified_locked: true,
        informational_only: true,
      },
    }),
    listAISuggestions: async () => ({
      suggestions: [
        {
          suggestion_id: 's-1',
          kind: 'flag',
          reason: 'Cross-speaker flag',
          is_applicable_edit: false,
          status: 'informational',
          payload: {
            locked_informational: true,
            word_excerpt: ['0:Question', '1:Answer'],
          },
        },
        {
          suggestion_id: 's-2',
          kind: 'speaker_map',
          reason: 'AI proposed mapping',
          is_applicable_edit: false,
          status: 'pending',
          payload: {},
        },
      ],
    }),
  };
  context.api = context.window.api;

  loadScript(context, 'frontend/assets/js/screens/stage_3.js');

  await context.loadWorkspaceSpeakerMapping();
  const mappingHtml = context.document.getElementById('workspaceSpeakerMappingRoot').innerHTML;
  assert.ok(mappingHtml.includes('high-confidence cross-speaker'));
  assert.ok(mappingHtml.includes('locked certification snapshot'));

  await context.loadAISuggestions('job-1');
  assert.strictEqual(context.document.getElementById('flagCount').innerText, '0 review flags');
  const cardHtml = context.document.getElementById('aiSuggestionsList').children[0].innerHTML;
  assert.ok(cardHtml.includes('Locked certification audit metadata'));
  assert.ok(cardHtml.includes('AUDIT LOCKED'));
  assert.ok(cardHtml.includes('LOCKED'));
  assert.ok(!cardHtml.includes('Approve</button>'));
  assert.ok(!cardHtml.includes('Reject</button>'));
}

async function testTranscriptNavigationRelabelsRender() {
  const context = createContext();
  seedStage3Elements(context);

  loadScript(context, 'frontend/assets/js/screens/stage_3.js');

  context.setWorkspaceMode('edit');
  assert.strictEqual(
    context.document.getElementById('rightPanelTitle').innerText,
    'Transcript Navigation Preview',
  );

  context.setWorkspaceMode('audio');
  assert.strictEqual(
    context.document.getElementById('rightPanelTitle').innerText,
    'Transcript Navigation Preview',
  );
  assert.strictEqual(
    context.document.getElementById('modeBannerText').innerText,
    'Transcript Navigation Preview: click a line to seek retained media and follow playback in real time.',
  );
}

async function testRealPlaybackControlsAndHighlighting() {
  const context = createContext();
  seedStage3Elements(context);

  context.window.api = {
    getTranscriptMediaUrl: (jobId) => {
      const url = `/api/transcripts/jobs/${jobId}/media`;
      context.__mediaRegistry[url] = { duration: 8838 };
      return url;
    },
    getTranscriptContent: async () => ({
      job: { job_id: 'job-1', source_filename: 'sample.mp3', duration_seconds: 8838 },
      speakers: [],
      participants: [],
      utterances: [
        {
          utterance_id: 'utt-1',
          speaker_index: 0,
          speaker_label: 'Speaker 0',
          text: 'First fragment.',
          raw_text: 'First fragment.',
          working_text: null,
          is_working_override: false,
          working_source: '',
          working_updated_at: '',
          avg_confidence: 0.97,
          start_time: 1.0,
          end_time: 2.0,
        },
        {
          utterance_id: 'utt-2',
          speaker_index: 0,
          speaker_label: 'Speaker 0',
          text: 'Second fragment.',
          raw_text: 'Second fragment.',
          working_text: null,
          is_working_override: false,
          working_source: '',
          working_updated_at: '',
          avg_confidence: 0.96,
          start_time: 2.2,
          end_time: 3.0,
        },
      ],
      words: [
        { utterance_id: 'utt-1', start_time: 1.0, end_time: 1.4 },
        { utterance_id: 'utt-1', start_time: 1.4, end_time: 1.9 },
        { utterance_id: 'utt-2', start_time: 2.2, end_time: 2.6 },
      ],
    }),
  };
  context.api = context.window.api;

  loadScript(context, 'frontend/assets/js/screens/stage_3.js');
  loadScript(context, 'frontend/assets/js/screens/stage_2.js');

  await context.loadTranscriptResultsIntoWorkspace(['job-1']);
  context.focusLineRow('utt-2', true);

  const media = context.document.getElementById('workspaceMediaMount').children[0];
  assert.ok(media);
  assert.strictEqual(media.currentTime, 2.2);

  await context.toggleAudioPlayback();
  assert.strictEqual(media.paused, false);
  assert.strictEqual(context.state.activePlayback, true);

  context.changeAudioSpeed('1.5');
  assert.strictEqual(media.playbackRate, 1.5);

  context.skipAudio(-1);
  assert.ok(Math.abs(media.currentTime - 1.2) < 0.0001);

  media.currentTime = 2.3;
  media.dispatchEvent('timeupdate');
  assert.strictEqual(context.state.focusedLineId, 'utt-2');
  assert.strictEqual(
    context.document.getElementById('audioTimeLabel').innerText,
    '00:02 / 02:27:18',
  );

  await context.toggleAudioPlayback();
  assert.strictEqual(media.paused, true);
}

async function testMissingAudioShowsExplicitUnavailableState() {
  const context = createContext();
  seedStage3Elements(context);

  context.window.api = {
    getTranscriptMediaUrl: (jobId) => {
      const url = `/api/transcripts/jobs/${jobId}/media`;
      context.__mediaRegistry[url] = { missing: true };
      return url;
    },
    getTranscriptContent: async () => ({
      job: { job_id: 'job-1', source_filename: 'sample.mp3', duration_seconds: 8838 },
      speakers: [],
      participants: [],
      utterances: [
        {
          utterance_id: 'utt-1',
          speaker_index: 0,
          speaker_label: 'Speaker 0',
          text: 'First fragment.',
          raw_text: 'First fragment.',
          working_text: null,
          is_working_override: false,
          working_source: '',
          working_updated_at: '',
          avg_confidence: 0.97,
          start_time: 1.0,
          end_time: 2.0,
        },
      ],
      words: [],
    }),
  };
  context.api = context.window.api;

  loadScript(context, 'frontend/assets/js/screens/stage_3.js');
  loadScript(context, 'frontend/assets/js/screens/stage_2.js');

  await context.loadTranscriptResultsIntoWorkspace(['job-1']);
  context.focusLineRow('utt-1', true);

  assert.strictEqual(
    context.document.getElementById('audioTimeLabel').innerText,
    'Audio no longer retained for this job',
  );
  assert.ok(
    context.document.getElementById('audioPlaybackNote').innerText.includes('Audio no longer retained for this job'),
  );
  assert.strictEqual(context.document.getElementById('playAudioBtn').disabled, true);
}

(async () => {
  await testWorkspaceLoadPreservesOneLinePerUtteranceAndGroupsHeadersAtRender();
  await testCrossSpeakerBannerAndLockedReviewFlagsRender();
  await testTranscriptNavigationRelabelsRender();
  await testRealPlaybackControlsAndHighlighting();
  await testMissingAudioShowsExplicitUnavailableState();
  const stage3Html = fs.readFileSync(path.join(process.cwd(), 'frontend', 'screens', 'stage_3_workspace.html'), 'utf8');
  assert.ok(stage3Html.includes('audioPlaybackNote'));
  const stage3Js = fs.readFileSync(path.join(process.cwd(), 'frontend', 'assets', 'js', 'screens', 'stage_3.js'), 'utf8');
  assert.ok(!stage3Js.includes('playbackLineIdx'));
  assert.ok(!stage3Js.includes('playbackInterval'));
  console.log('stage_3 frontend contract checks passed');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
