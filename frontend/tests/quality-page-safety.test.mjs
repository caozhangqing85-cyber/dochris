import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const sourceUrl = new URL('../src/pages/QualityPage.tsx', import.meta.url)

test('QualityPage matches the backend reset scope and confirms the mutation', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /const resettableCount = manifests\.filter/)
  assert.match(source, /manifest\.quality_score < threshold/)
  assert.match(source, /manifest\.status === 'compiled' \|\| manifest\.status === 'compile_failed'/)
  assert.match(source, /disabled=\{resetting \|\| resettableCount === 0\}/)
  assert.match(source, /window\.confirm\(`/)
  assert.match(source, /源文件不会被删除/)
  assert.match(source, /重置低质量 \(\$\{resettableCount\}\)/)
})
