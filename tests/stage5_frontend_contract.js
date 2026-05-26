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
}

class FakeElement {
  constructor(id = '') {
    this.id = id;
    this.value = '';
    this.checked = false;
    this.innerText = '';
    this.innerHTML = '';
    this.disabled = false;
    this.className = '';
    this.classList = new ClassList();
  }
}

function createContext() {
  const elements = new Map();
  const ensure = (id) => {
    if (!elements.has(id)) {
      elements.set(id, new FakeElement(id));
    }
    return elements.get(id);
  };

  const document = {
    getElementById(id) {
      return ensure(id);
    },
  };

  const toasts = [];
  const provenance = [];
  const fetchCalls = [];

  const context = {
    console,
    setTimeout(fn) {
      if (typeof fn === 'function') fn();
      return 1;
    },
    clearTimeout() {},
    Date,
    Promise,
    document,
    state: {
      activeTranscriptJobIds: ['job-1'],
      caseInfo: {
        certified: false,
        packageId: '',
        certifiedSnapshotId: '',
        signature: '',
      },
      certificationHistory: {
        jobId: null,
        packages: [],
        snapshots: [],
        lastLoadedAt: null,
        lastError: null,
      },
    },
    showToast(message, tone) {
      toasts.push({ message, tone });
    },
    addProvenanceRecord(title, detail, actor) {
      provenance.push({ title, detail, actor });
    },
    fetch: async (url, options = {}) => {
      fetchCalls.push({ url, options });
      if (options.method === 'PUT') {
        return { ok: true, json: async () => ({ ok: true }) };
      }
      return {
        ok: true,
        json: async () => ({
          examination_disposition: 'waived',
          volume: '1',
          officer_charges_amount: '450.00',
          charges_party: 'Plaintiff',
          certificate_service_date: 'June 5, 2026',
          time_per_party: [{ party: 'Plaintiff', duration: '1:30' }],
        }),
      };
    },
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
  context.__toasts = toasts;
  context.__provenance = provenance;
  context.__fetchCalls = fetchCalls;
  return context;
}

function seedStage5Elements(context) {
  [
    'certLineageStatus',
    'certHistoryList',
    'certPackageCount',
    'certSnapshotCount',
    'certLatestVersion',
    'badgeWorking',
    'badgeCertified',
    'certPreLock',
    'certPostLock',
    'lockTimestamp',
    'packageIdDisplay',
    'manifestHashDisplay',
    'renderedSignatory',
    'certExaminationDisposition',
    'certVolume',
    'certChargesAmount',
    'certChargesParty',
    'certServiceDate',
    'certTimePerParty',
    'certMetaSaveStatus',
    'reporterSignatureInput',
    'certCheck1',
    'certCheck2',
    'certCheck3',
    'signBtn',
    'certErrorArea',
  ].forEach((id) => context.document.getElementById(id));

  context.document.getElementById('badgeCertified').classList.add('hidden');
  context.document.getElementById('certPostLock').classList.add('hidden');
}

function loadStage5Script(context) {
  const scriptPath = path.join(process.cwd(), 'frontend', 'assets', 'js', 'screens', 'stage_5.js');
  const source = fs.readFileSync(scriptPath, 'utf8');
  vm.createContext(context);
  vm.runInContext(source, context, { filename: 'stage_5.js' });
}

async function testRenderCertificationHistory() {
  const context = createContext();
  seedStage5Elements(context);
  loadStage5Script(context);

  context.state.certificationHistory = {
    jobId: 'job-1',
    packages: [
      {
        package_id: 'pkg-latest-12345678',
        package_state: 'CERTIFIED',
        snapshot_id: 'snap-2',
        certified_at: '2026-05-25T12:00:00',
        manifest_hash: 'abcdef1234567890abcdef1234567890',
      },
    ],
    snapshots: [
      {
        snapshot_id: 'snap-2',
        locked: true,
        created_by: 'CSR Jane',
      },
    ],
    lastLoadedAt: '2026-05-25T12:05:00',
    lastError: null,
  };

  context.renderCertificationHistory();

  assert.strictEqual(context.state.caseInfo.certified, true);
  assert.strictEqual(context.state.caseInfo.packageId, 'pkg-latest-12345678');
  assert.strictEqual(context.state.caseInfo.certifiedSnapshotId, 'snap-2');
  assert.strictEqual(context.document.getElementById('renderedSignatory').innerText, 'CSR Jane');
  assert.strictEqual(context.document.getElementById('certPackageCount').innerText, '1');
  assert.strictEqual(context.document.getElementById('certSnapshotCount').innerText, '1');
  assert.strictEqual(context.document.getElementById('certLatestVersion').innerText, 'v1');
  assert.ok(context.document.getElementById('badgeCertified').classList.contains('hidden') === false);
  assert.ok(context.document.getElementById('certHistoryList').innerHTML.includes('Current Working Transcript'));
}

async function testSignTranscriptUsesSignatureForSnapshotAndLoadsLineage() {
  const context = createContext();
  seedStage5Elements(context);
  context.document.getElementById('reporterSignatureInput').value = 'Reporter CSR';
  context.document.getElementById('certCheck1').checked = true;
  context.document.getElementById('certCheck2').checked = true;
  context.document.getElementById('certCheck3').checked = true;

  const apiCalls = [];
  const packageHistory = [{
    package_id: 'pkg-001',
    package_state: 'CERTIFIED',
    snapshot_id: 'snap-001',
    certified_at: '2026-05-25T15:42:00',
    manifest_hash: '1234567890abcdef1234567890abcdef',
  }];
  const snapshotHistory = [{
    snapshot_id: 'snap-001',
    locked: true,
    created_by: 'Reporter CSR',
  }];

  context.window.api = {
    createSnapshot: async (jobId, category, note, createdBy) => {
      apiCalls.push(['createSnapshot', jobId, category, note, createdBy]);
      return { snapshot_id: 'snap-001' };
    },
    lockSnapshot: async (snapshotId) => {
      apiCalls.push(['lockSnapshot', snapshotId]);
      return { snapshot_id: snapshotId, locked: true };
    },
    assemblePackage: async (jobId, snapshotId) => {
      apiCalls.push(['assemblePackage', jobId, snapshotId]);
      return { package_id: 'pkg-001' };
    },
    certifyPackage: async (packageId) => {
      apiCalls.push(['certifyPackage', packageId]);
      return {
        package_id: packageId,
        certified_at: '2026-05-25T15:42:00',
        manifest_hash: '1234567890abcdef1234567890abcdef',
      };
    },
    listPackages: async (jobId) => {
      apiCalls.push(['listPackages', jobId]);
      return { packages: packageHistory };
    },
    listSnapshots: async (jobId) => {
      apiCalls.push(['listSnapshots', jobId]);
      return { snapshots: snapshotHistory };
    },
  };
  context.api = context.window.api;

  loadStage5Script(context);
  await context.signTranscript();

  assert.deepStrictEqual(apiCalls[0], ['createSnapshot', 'job-1', 'CERTIFIED', 'Certification snapshot', 'Reporter CSR']);
  assert.strictEqual(context.state.caseInfo.packageId, 'pkg-001');
  assert.strictEqual(context.state.caseInfo.certifiedSnapshotId, 'snap-001');
  assert.strictEqual(context.document.getElementById('renderedSignatory').innerText, 'Reporter CSR');
  assert.ok(context.__toasts.some((t) => t.message.includes('Working transcript remains editable for future versions.')));
  assert.ok(context.__fetchCalls.some((c) => c.url === '/api/depo-meta/jobs/job-1' && c.options.method === 'PUT'));
  assert.ok(context.__provenance.some((p) => p.title === 'Case Bundle Certified'));
}

(async () => {
  await testRenderCertificationHistory();
  await testSignTranscriptUsesSignatureForSnapshotAndLoadsLineage();
  console.log('stage_5 frontend contract checks passed');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
