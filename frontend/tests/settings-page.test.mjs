import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const sourceUrl = new URL('../src/pages/SettingsPage.tsx', import.meta.url)

test('SettingsPage exposes a distinct Dochris gateway key control', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /getApiAccessKey/)
  assert.match(source, /setApiAccessKey/)
  assert.match(source, /Dochris 服务访问/)
  assert.match(source, /网关访问密钥/)
  assert.match(source, /DOCHRIS_API_KEY/)
  assert.match(source, /handleSaveAccessKey/)
})

test('SettingsPage keeps the gateway key recovery control visible after auth failure', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /loadError[\s\S]*renderAccessKeyCard\(\)[\s\S]*RequestErrorState/)
})

test('SettingsPage confirms manifest-wide schema mutations before API calls', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /handleSchemaEnrich[\s\S]*window\.confirm\([\s\S]*manifest 关系元数据[\s\S]*enrichSchemaFromGraph\(\)/)
  assert.match(source, /handleAutoTag[\s\S]*window\.confirm\([\s\S]*人工标签会保留[\s\S]*autoTagSchema\(\)/)
  assert.match(source, /现有源文件不会被删除/)
  assert.match(source, /manifest 内容会发生变更/)
})
