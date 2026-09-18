import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/secureApi.ts', import.meta.url), 'utf8')
  .replaceAll('import.meta.env', '({ DEV: false })');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
const exports = {};
const requests = [];
vm.runInNewContext(outputText, {
  exports,
  require: () => ({}),
  console: { log() {}, warn() {}, error() {} },
  URLSearchParams,
  fetch: (url, options) => new Promise((resolve) => requests.push({ url, options, resolve })),
});
const api = exports.SecureAPI;
api.setAccessToken('account-a');
const first = api.getDashboardSummary('prop-001', 2024, 3);
api.setAccessToken('account-b');
const second = api.getDashboardSummary('prop-001', 2024, 3);
await Promise.resolve();
assert.equal(requests.length, 2);
assert.equal(requests[0].options.headers.Authorization, 'Bearer account-a');
assert.equal(requests[1].options.headers.Authorization, 'Bearer account-b');
assert.equal(requests[1].options.cache, 'no-store');
assert.match(requests[1].url, /property_id=prop-001&year=2024&month=3$/);
requests[1].resolve(new Response(JSON.stringify({ total: '0.00' }), { headers: { 'Content-Type': 'application/json' } }));
assert.equal((await second).total, '0.00');
requests[0].resolve(new Response(JSON.stringify({ total: '2250.00' }), { headers: { 'Content-Type': 'application/json' } }));
assert.equal((await first).total, '2250.00');
assert.equal(api.getCacheDiagnostics().totalCacheEntries, 0);
console.log('Dashboard reads keep account tokens separate and bypass browser cache/deduplication.');
