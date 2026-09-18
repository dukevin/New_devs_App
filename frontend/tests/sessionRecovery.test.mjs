import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

let session = null;
let storedSession;
let removedKey;
const errors = [];
const auth = {
  getSession: async () => ({ data: { session } }),
  setSession: async (value) => { storedSession = value; },
};
const source = readFileSync(new URL('../src/utils/sessionRecovery.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
const exports = {};
vm.runInNewContext(outputText, {
  exports,
  require: () => ({ supabase: { auth } }),
  console: { log() {}, error: (...args) => errors.push(args) },
  setTimeout,
  clearTimeout,
  localStorage: { removeItem: (key) => { removedKey = key; } },
});
const recovery = exports.sessionRecovery;
assert.equal(await recovery.recoverSession(), null);
session = { access_token: 'validated-token', token_type: 'bearer', user: { id: 'user-a' } };
assert.equal(await recovery.recoverSession(), session);
await recovery.persistSession(session);
assert.equal(storedSession, session);
recovery.clearStoredSession();
assert.equal(removedKey, 'base360-auth-token');
assert.deepEqual(errors, []);
console.log('Session recovery handles empty storage and preserves the local auth contract.');
