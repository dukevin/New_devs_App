import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

const source = readFileSync(new URL('../src/utils/formatRevenue.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { formatRevenue } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

assert.equal(formatRevenue('2250.00'), '2,250.00');
assert.equal(formatRevenue('0.00'), '0.00');
assert.equal(formatRevenue('-0.01'), '-0.01');
assert.equal(formatRevenue('-1234567.89'), '-1,234,567.89');
assert.equal(formatRevenue('9007199254740993.01'), '9,007,199,254,740,993.01');
assert.equal(formatRevenue('1.01'), '1.01');
console.log('Revenue formatting preserves exact cents, including beyond Number precision.');
