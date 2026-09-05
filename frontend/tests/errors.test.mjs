import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import test from 'node:test'

const require = createRequire(import.meta.url)

async function loadErrorsModule() {
  const ts = require('typescript')
  const source = await readFile(new URL('../src/lib/errors.ts', import.meta.url), 'utf8')
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
      verbatimModuleSyntax: true,
    },
    fileName: 'errors.ts',
  })
  const encoded = encodeURIComponent(transpiled.outputText)
  return import(`data:text/javascript;charset=utf-8,${encoded}#${Date.now()}-${Math.random()}`)
}

test('classifyRequestError maps offline network failures to retryable diagnostics', async () => {
  const { classifyRequestError } = await loadErrorsModule()

  const error = classifyRequestError(new TypeError('Failed to fetch'))

  assert.equal(error.kind, 'offline')
  assert.equal(error.retryable, true)
  assert.match(error.title, /无法连接/)
  assert.match(error.diagnostic, /后端服务/)
})

test('classifyRequestError maps auth failures without treating them as empty data', async () => {
  const { classifyRequestError } = await loadErrorsModule()

  assert.deepEqual(classifyRequestError(new Error('Request failed: 401')).kind, 'unauthorized')
  assert.deepEqual(classifyRequestError(new Error('403 Forbidden')).kind, 'forbidden')
})

test('classifyRequestError prioritizes typed API error codes over localized messages', async () => {
  const { classifyRequestError } = await loadErrorsModule()

  assert.equal(classifyRequestError({ code: 'OFFLINE', message: '无法连接后端 API' }).kind, 'offline')
  assert.equal(classifyRequestError({ code: 'TIMEOUT', message: '请求超时，请稍后重试' }).kind, 'timeout')
  assert.equal(classifyRequestError({ code: 'UNAUTHORIZED', message: '未认证' }).kind, 'unauthorized')
  assert.equal(classifyRequestError({ code: 'FORBIDDEN', message: '禁止访问' }).kind, 'forbidden')
})

test('classifyRequestError maps timeout and server errors to actionable classes', async () => {
  const { classifyRequestError } = await loadErrorsModule()

  assert.equal(classifyRequestError(new DOMException('aborted', 'AbortError')).kind, 'cancelled')
  const gateway = classifyRequestError({ status: 502, message: 'Request failed: 502' })
  assert.equal(gateway.kind, 'gateway')
  assert.match(gateway.title, /网关|后端不可用/)
  assert.match(gateway.diagnostic, /启动|代理/)
  assert.equal(classifyRequestError(new Error('Request failed: 503')).kind, 'server')
  assert.equal(classifyRequestError(new Error('unexpected parser failure')).kind, 'unknown')
})

async function readFrontendPage(name) {
  return readFile(new URL(`../src/pages/${name}`, import.meta.url), 'utf8')
}

test('RequestErrorState invokes retry without forwarding the React click event', async () => {
  const source = await readFile(new URL('../src/components/ui/RequestErrorState.tsx', import.meta.url), 'utf8')

  assert.match(source, /onClick=\{\(\) => onRetry\(\)\}/)
  assert.doesNotMatch(source, /onClick=\{onRetry\}/)
})

test('FilesPage preserves initial request failures in a visible error state', async () => {
  const source = await readFrontendPage('FilesPage.tsx')

  assert.match(source, /classifyRequestError/)
  assert.match(source, /setLoadError\(classifyRequestError\(e\)\)/)
  assert.match(source, /void loadFiles\(/)
  assert.match(source, /<RequestErrorState[\s\S]*onRetry=\{load\}/)
})

test('QualityPage preserves initial request failures in a visible error state', async () => {
  const source = await readFrontendPage('QualityPage.tsx')

  assert.match(source, /classifyRequestError/)
  assert.match(source, /setLoadError\(classifyRequestError\(e\)\)/)
  assert.match(source, /void loadQualityData\(/)
  assert.match(source, /<RequestErrorState[\s\S]*onRetry=\{load\}/)
})

test('QualityPage hides quality metrics while a request error is active', async () => {
  const source = await readFrontendPage('QualityPage.tsx')
  const errorBranch = source.indexOf('if (loadError) return (')
  const metricsSection = source.indexOf('<SectionHeader title="质量概览" />')

  assert.notEqual(errorBranch, -1)
  assert.notEqual(metricsSection, -1)
  assert.ok(errorBranch < metricsSection)
})

test('QualityPage separates compilation coverage from actual quality signals', async () => {
  const source = await readFrontendPage('QualityPage.tsx')

  assert.match(source, /<SectionHeader title="编译状态分布" \/>/)
  assert.match(source, /平均质量分/)
  assert.match(source, /编译覆盖率/)
  assert.match(source, /已评分文件达标率/)
  assert.doesNotMatch(source, /整体质量优秀|整体质量良好/)
})

test('StatusPage labels filesystem artifact counts without implying graph node counts', async () => {
  const source = await readFrontendPage('StatusPage.tsx')

  assert.match(source, /<Row label="概念文件"/)
  assert.match(source, /<Row label="摘要文件"/)
  assert.doesNotMatch(source, /<Row label="概念数"|<Row label="摘要数"/)
})

for (const [page, retryHandler, contentMarker] of [
  ['DashboardPage.tsx', 'load', '<SectionHeader title="数据概览" />'],
  ['GraphPage.tsx', 'loadGraph', '<div className="graph-layout"'],
]) {
  test(`${page} uses classified request errors instead of hard-coded diagnostics`, async () => {
    const source = await readFrontendPage(page)
    const errorBranch = source.indexOf('if (loadError) return (')
    const content = source.indexOf(contentMarker)

    assert.match(source, /classifyRequestError/)
    assert.match(source, /setLoadError\(classifyRequestError\(e\)\)/)
    assert.match(source, new RegExp(`<RequestErrorState[\\s\\S]*onRetry=\\{${retryHandler}\\}`))
    assert.notEqual(errorBranch, -1)
    assert.notEqual(content, -1)
    assert.ok(errorBranch < content)
  })
}

for (const [page, retryHandler, contentMarker] of [
  ['SettingsPage.tsx', 'loadConfig', '<SectionHeader title="可观测性" />'],
  ['CompilePage.tsx', 'loadData', '<SectionHeader title="编译概览" />'],
  ['CandidatesPage.tsx', 'load', '{/* 过滤器 */}'],
  ['StatusPage.tsx', 'load', '<div className="status-grid"'],
]) {
  test(`${page} keeps request failures out of fake empty/default states`, async () => {
    const source = await readFrontendPage(page)
    const errorBranch = source.indexOf('if (loadError) return (')
    const content = source.indexOf(contentMarker)

    assert.match(source, /classifyRequestError/)
    assert.match(source, /setLoadError\(classifyRequestError\(e\)\)/)
    assert.match(source, new RegExp(`<RequestErrorState[\\s\\S]*onRetry=\\{${retryHandler}\\}`))
    assert.notEqual(errorBranch, -1)
    assert.notEqual(content, -1)
    assert.ok(errorBranch < content)
  })
}
