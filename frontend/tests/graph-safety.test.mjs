import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import test from 'node:test'

const require = createRequire(import.meta.url)

async function loadTypesModule() {
  const ts = require('typescript')
  const source = await readFile(new URL('../src/types/index.ts', import.meta.url), 'utf8')
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: 'types.ts',
  })
  const encoded = encodeURIComponent(transpiled.outputText)
  return import(`data:text/javascript;charset=utf-8,${encoded}#${Date.now()}-${Math.random()}`)
}

test('graphRenderer never injects node labels as HTML (XSS guard)', async () => {
  const source = await readFile(new URL('../src/lib/graphRenderer.ts', import.meta.url), 'utf8')

  assert.doesNotMatch(source, /\.html\(/, 'tooltip 必须禁止 .html() 插值，label 来自用户文档')
  assert.match(source, /textContent/)
  assert.match(source, /replaceChildren/)
})

test('graphRenderer tooltip builds content via DOM text nodes', async () => {
  const source = await readFile(new URL('../src/lib/graphRenderer.ts', import.meta.url), 'utf8')

  assert.match(source, /document\.createElement\('div'\)/)
  assert.match(source, /title\.textContent = d\.label/)
})

test('formatMetadataValue renders every JSON shape as a plain string', async () => {
  const { formatMetadataValue } = await loadTypesModule()

  assert.equal(formatMetadataValue('plain'), 'plain')
  assert.equal(formatMetadataValue(0), '0')
  assert.equal(formatMetadataValue(3.14), '3.14')
  assert.equal(formatMetadataValue(true), 'true')
  assert.equal(formatMetadataValue(null), '')
  assert.equal(formatMetadataValue(undefined), '')
  assert.equal(formatMetadataValue(['a', 'b']), '["a","b"]')
  assert.equal(formatMetadataValue({ nested: { depth: 1 } }), '{"nested":{"depth":1}}')
})

test('GraphNode metadata accepts arbitrary JSON values, not just strings', async () => {
  const source = await readFile(new URL('../src/types/index.ts', import.meta.url), 'utf8')

  assert.match(source, /metadata\?: Record<string, unknown>/)
  assert.doesNotMatch(source, /metadata\?: Record<string, string>/)
})
