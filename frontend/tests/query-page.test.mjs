import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const sourceUrl = new URL('../src/pages/QueryPage.tsx', import.meta.url)

test('QueryPage exposes a cancel action wired to the active stream AbortController', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /const handleCancelQuery\s*=/)
  assert.match(source, /abortRef\.current\?\.abort\(\)/)
  assert.match(source, />\s*取消\s*</)
  assert.match(source, /查询已取消/)
  assert.match(source, /setQueryError\(null\)/)
  assert.match(source, /setError\(''\)/)
  assert.match(source, /setResult\(null\)/)
  assert.match(source, /setElapsed\(0\)/)
  assert.match(source, /setContributionReceipt\(null\)/)
  assert.match(source, /setPhaseTimings\(null\)/)
  assert.doesNotMatch(source, /handleCancelQuery[\s\S]*showQueryError\(new ApiError\('查询已取消'/)
})

test('QueryPage renders structured phase timings from stream done metadata', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /phaseTimings/)
  assert.match(source, /setPhaseTimings/)
  assert.match(source, /阶段耗时/)
  assert.match(source, /检索/)
  assert.match(source, /生成/)
  assert.match(source, /retrieval_seconds/)
  assert.match(source, /generation_seconds/)
  assert.match(source, /contribution_seconds/)
  assert.match(source, /total_seconds/)
  assert.match(source, /first_token_seconds/)
})

test('QueryPage classifies query errors for offline, auth, timeout, and HTTP failures', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /formatQueryError/)
  assert.match(source, /OFFLINE/)
  assert.match(source, /UNAUTHORIZED/)
  assert.match(source, /TIMEOUT/)
  assert.match(source, /HTTP/)
})

test('QueryPage performs contribution as a separate explicit mutation', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /contributeQueryResult/)
  assert.match(source, /await contributeQueryResult\(queryResult\)/)
  assert.doesNotMatch(source, /queryKnowledge\([^\n]+contribute\)/)
  assert.doesNotMatch(source, /queryKnowledgeStream\([\s\S]{0,500}contribute,/)
})

test('QueryPage keeps a stable accessible name while document availability loads', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /aria-label=["']查询知识库["']/)
  assert.match(source, /aria-describedby=["']query-availability-status["']/)
  assert.match(source, /id=["']query-availability-status["']/)
  assert.match(source, /role=["']status["']/)
  assert.match(source, /正在读取可查询文档/)
})

test('QueryPage mode selector exposes a keyboard-operable listbox contract', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /aria-haspopup="listbox"/)
  assert.match(source, /aria-expanded=\{showModeDropdown\}/)
  assert.match(source, /aria-controls="query-mode-listbox"/)
  assert.match(source, /role="listbox"/)
  assert.match(source, /role="option" aria-selected=\{mode === m\.value\}/)
  assert.match(source, /event\.key === 'ArrowDown'/)
  assert.match(source, /event\.key === 'ArrowUp'/)
  assert.match(source, /event\.key === 'Escape'/)
  assert.match(source, /modeTriggerRef\.current\?\.focus\(\)/)
})

test('QueryPage renders saved history and favorites as named native buttons', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /aria-label=\{`重新运行历史查询：\$\{h\.query\}`\}/)
  assert.match(source, /aria-label=\{`运行收藏查询：\$\{f\.query\}`\}/)
})
