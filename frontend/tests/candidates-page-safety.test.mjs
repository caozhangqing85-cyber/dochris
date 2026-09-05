import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const sourceUrl = new URL('../src/pages/CandidatesPage.tsx', import.meta.url)

test('CandidatesPage confirms the real effects of promote and discard', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /handlePromote[\s\S]*window\.confirm\([\s\S]*写入 wiki 摘要和概念文件[\s\S]*promoteCandidate\(id\)/)
  assert.match(source, /handleDiscard[\s\S]*window\.confirm\([\s\S]*候选内容文件会被永久删除[\s\S]*discardCandidate\(id\)/)
  assert.match(source, /元数据将保留为已丢弃状态/)
})
