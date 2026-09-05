import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import test from 'node:test'

const require = createRequire(import.meta.url)

async function loadCompileJobModule() {
  const ts = require('typescript')
  const source = await readFile(
    new URL('../src/lib/compileJob.ts', import.meta.url),
    'utf8',
  )
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
      verbatimModuleSyntax: true,
    },
    fileName: 'compileJob.ts',
  })
  return import(
    `data:text/javascript;charset=utf-8,${encodeURIComponent(transpiled.outputText)}#${Date.now()}-${Math.random()}`
  )
}

test('compile job activity follows server lifecycle states', async () => {
  const jobs = await loadCompileJobModule()

  for (const status of ['accepted', 'queued', 'running', 'cancelling']) {
    assert.equal(jobs.isCompileJobActive(status), true, status)
  }
  for (const status of ['completed', 'failed', 'cancelled', 'interrupted', 'dry_run', 'no_work']) {
    assert.equal(jobs.isCompileJobActive(status), false, status)
  }
})

test('compile progress uses exact processed count and stays within 0-100', async () => {
  const jobs = await loadCompileJobModule()

  assert.equal(jobs.compileJobPercent({ total: 8, processed: 3 }), 38)
  assert.equal(jobs.compileJobPercent({ total: 0, processed: 0 }), 0)
  assert.equal(jobs.compileJobPercent({ total: 2, processed: 5 }), 100)
  assert.equal(jobs.compileJobPercent({ total: 2, processed: -1 }), 0)
})
