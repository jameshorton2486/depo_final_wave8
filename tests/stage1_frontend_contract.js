const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

function loadApiContext() {
  const context = {
    console,
    fetch: async () => ({ ok: true, json: async () => ({}) }),
    window: {},
  };
  context.globalThis = context;
  vm.createContext(context);
  const scriptPath = path.join(process.cwd(), 'frontend', 'assets', 'js', 'api.js');
  const source = fs.readFileSync(scriptPath, 'utf8');
  vm.runInContext(source, context, { filename: 'api.js' });
  return context;
}

function buildState() {
  return {
    caseId: 'case-1',
    sessionId: 'session-1',
    caseInfo: {
      cause: '2025CI11923',
      caption: 'Pavan v. Benitez',
      court: '408th Judicial District',
      county: 'Bexar County',
      state: 'Texas',
      deponent: 'Frank Benitez',
      date: '2026-04-16',
      startTime: '',
      endTime: '',
      address: '',
      csrName: '',
      csrLicense: '',
      firmReg: '',
      csrCertExp: '',
    },
    stage1: {
      rawIntakeNotes: '',
      parserMetadata: {
        jurisdiction_type: 'texas_state',
        location_type: 'unknown',
      },
      keytermEntries: [],
      field_confirmations: {},
    },
  };
}

function testBuildStage1PayloadMapsOrigins() {
  const context = loadApiContext();
  const api = context.window.api;
  const parsePayload = api.buildStage1SyncPayload(buildState(), 'nod-parser');
  assert.strictEqual(parsePayload.origin, 'parse');

  const textPayload = api.buildStage1SyncPayload(buildState(), 'text-parser');
  assert.strictEqual(textPayload.origin, 'parse');

  const operatorPayload = api.buildStage1SyncPayload(buildState(), 'field-confirmed');
  assert.strictEqual(operatorPayload.origin, 'operator');

  const savePayload = api.buildStage1SyncPayload(buildState(), 'operator');
  assert.strictEqual(savePayload.origin, 'operator');

  const defaultPayload = api.buildStage1SyncPayload(buildState());
  assert.strictEqual(defaultPayload.origin, 'parse');

  const unknownPayload = api.buildStage1SyncPayload(buildState(), 'mystery-origin');
  assert.strictEqual(unknownPayload.origin, 'parse');
}

function testSourceThreadingAtCallsites() {
  const stage1Js = fs.readFileSync(
    path.join(process.cwd(), 'frontend', 'assets', 'js', 'screens', 'stage_1.js'),
    'utf8',
  );
  const appJs = fs.readFileSync(
    path.join(process.cwd(), 'frontend', 'assets', 'js', 'app.js'),
    'utf8',
  );

  assert.ok(stage1Js.includes('window.api.syncStage1Artifacts(state, reason)'));
  assert.ok(appJs.includes("window.api.syncStage1Artifacts(state, 'operator')"));
}

testBuildStage1PayloadMapsOrigins();
testSourceThreadingAtCallsites();
console.log('stage_1 frontend contract checks passed');
