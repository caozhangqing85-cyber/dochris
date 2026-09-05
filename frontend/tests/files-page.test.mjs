import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const sourceUrl = new URL('../src/pages/FilesPage.tsx', import.meta.url)

test('FilesPage disables no-op failed resets and confirms real mutations', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /const failedCount = files\.filter\(\(file\) => file\.status === 'failed'\)\.length/)
  assert.match(source, /disabled=\{resetting \|\| failedCount === 0\}/)
  assert.match(source, /window\.confirm\(`/)
  assert.match(source, /此操作不会删除源文件/)
  assert.match(source, /重置失败 \(\{failedCount\}\)/)
})

test('FilesPage exposes keyboard-operable rows and an accessible details dialog', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /tabIndex=\{0\}/)
  assert.match(source, /aria-haspopup="dialog"/)
  assert.match(source, /event\.key !== 'Enter' && event\.key !== ' '/)
  assert.match(source, /role="dialog" aria-modal="true"/)
  assert.match(source, /aria-labelledby="file-details-title" aria-describedby="file-details-description"/)
  assert.match(source, /aria-label="关闭文件详情"/)
  assert.match(source, /aria-label="刷新文件列表"/)
  assert.match(source, /event\.key === 'Escape'/)
  assert.match(source, /event\.key !== 'Tab'/)
  assert.match(source, /detailsDialogRef\.current/)
  assert.match(source, /dialog\.querySelectorAll<HTMLElement>/)
  assert.match(source, /document\.activeElement === first/)
  assert.match(source, /document\.activeElement === last/)
  assert.match(source, /detailsCloseRef\.current\?\.focus\(\)/)
  assert.match(source, /selectedTriggerRef\.current\?\.focus\(\)/)
})
