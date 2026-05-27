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
  }
  appendChild(child) {
    this.children.push(child);
    return child;
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
}

function createContext() {
  const elements = new Map();
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
    getTranscriptContent: async () => ({
      job: { job_id: 'job-1', source_filename: 'sample.mp3' },
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

(async () => {
  await testWorkspaceLoadPreservesOneLinePerUtteranceAndGroupsHeadersAtRender();
  await testCrossSpeakerBannerAndLockedReviewFlagsRender();
  console.log('stage_3 frontend contract checks passed');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
