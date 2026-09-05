import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const sourceUrl = new URL('../src/pages/CompilePage.tsx', import.meta.url)

test('CompilePage uses the server quality threshold for promotion affordances', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /const qualityThreshold = status\?\.config\?\.min_quality_score \?\? 85/)
  assert.match(source, /const promotable = \(f\.quality_score \?\? 0\) >= qualityThreshold/)
  assert.match(source, /disabled=\{promoting \|\| !promotable\}/)
  assert.match(source, /disabled=\{promoting \|\| !selectedFilePromotable\}/)
  assert.match(source, /低于晋升门槛/)
  assert.match(source, /需达到 \{qualityThreshold\}/)
})

test('CompilePage confirms the wiki write before promoting a file', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /handlePromote[\s\S]*window\.confirm\([\s\S]*晋升到 wiki/)
  assert.match(source, /写入知识文件并更新 manifest 状态/)
  assert.match(source, /window\.confirm[\s\S]*promoteFile\(fileId\)/)
})

test('CompilePage exposes durable compile history and retryable failures', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /getCompileJobs/)
  assert.match(source, /retryCompileJob/)
  assert.match(source, /编译历史/)
  assert.match(source, /job\.retryable[\s\S]*重试任务/)
  assert.match(source, /job\.error/)
  assert.match(source, /job\.attempt/)
})
