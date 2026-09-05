import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import test from 'node:test'

const require = createRequire(import.meta.url)

async function loadApiModule() {
  try {
    const ts = require('typescript')
    const source = await readFile(new URL('../src/lib/api.ts', import.meta.url), 'utf8')
    const transpiled = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
        moduleResolution: ts.ModuleResolutionKind.Bundler,
        verbatimModuleSyntax: true,
      },
      fileName: 'api.ts',
    })
    const encoded = encodeURIComponent(transpiled.outputText)
    return import(`data:text/javascript;charset=utf-8,${encoded}#${Date.now()}-${Math.random()}`)
  } catch (error) {
    if (error?.code !== 'MODULE_NOT_FOUND') throw error
  }

  return import(`../src/lib/api.ts?test=${Date.now()}-${Math.random()}`)
}

function installBrowserMocks(apiKey = 'secret-key') {
  const calls = []

  globalThis.localStorage = {
    getItem(key) {
      return key === 'dochris_api_key' ? apiKey : null
    },
  }

  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, init })
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  return calls
}

test('JSON requests preserve default content type and API key', async () => {
  const calls = installBrowserMocks()
  const api = await loadApiModule()

  await api.startCompile({ source_dir: 'docs' })

  assert.equal(calls[0].url, '/api/v1/compile')
  assert.equal(calls[0].init.headers['Content-Type'], 'application/json')
  assert.equal(calls[0].init.headers['X-API-Key'], 'secret-key')
})

test('compile job API helpers target lifecycle, history, retry, and cancellation endpoints', async () => {
  const calls = installBrowserMocks()
  const api = await loadApiModule()

  await api.getCurrentCompileJob()
  await api.getCompileJobs(7)
  await api.getCompileJob('job id')
  await api.retryCompileJob('job id')
  await api.cancelCompileJob('job id')

  assert.equal(calls[0].url, '/api/v1/compile/jobs/current')
  assert.equal(calls[0].init.method, undefined)
  assert.equal(calls[1].url, '/api/v1/compile/jobs?limit=7')
  assert.equal(calls[1].init.method, undefined)
  assert.equal(calls[2].url, '/api/v1/compile/jobs/job%20id')
  assert.equal(calls[2].init.method, undefined)
  assert.equal(calls[3].url, '/api/v1/compile/jobs/job%20id/retry')
  assert.equal(calls[3].init.method, 'POST')
  assert.equal(calls[4].url, '/api/v1/compile/jobs/job%20id/cancel')
  assert.equal(calls[4].init.method, 'POST')
})

test('API access key can be managed without browser developer tools', async () => {
  const values = new Map([['dochris_api_key', 'old-key']])
  globalThis.localStorage = {
    getItem(key) { return values.get(key) ?? null },
    setItem(key, value) { values.set(key, value) },
    removeItem(key) { values.delete(key) },
  }
  const api = await loadApiModule()

  assert.equal(api.getApiAccessKey(), 'old-key')
  api.setApiAccessKey('  new-key  ')
  assert.equal(values.get('dochris_api_key'), 'new-key')
  assert.equal(api.getApiAccessKey(), 'new-key')
  api.setApiAccessKey('   ')
  assert.equal(values.has('dochris_api_key'), false)
})

test('query contribution is an explicit authenticated POST mutation', async () => {
  const calls = installBrowserMocks()
  const api = await loadApiModule()
  const queryResult = {
    query: '费曼技巧',
    mode: 'combined',
    concepts: [],
    summaries: [],
    vector_results: [],
    search_sources: [],
    answer: '足够长的回答'.repeat(30),
    time_seconds: 0.4,
  }

  await api.contributeQueryResult(queryResult)

  assert.equal(calls[0].url, '/api/v1/query/contribution')
  assert.equal(calls[0].init.method, 'POST')
  assert.equal(calls[0].init.headers['Content-Type'], 'application/json')
  assert.equal(calls[0].init.headers['X-API-Key'], 'secret-key')
  assert.deepEqual(JSON.parse(calls[0].init.body), queryResult)
})

test('SSE, upload, and metrics requests include API key without forcing JSON content type', async () => {
  const calls = installBrowserMocks()
  const api = await loadApiModule()

  await api.queryKnowledgeStream('hello')
  await api.uploadFiles([new File(['x'], 'x.txt')])
  await api.getMetrics()

  assert.equal(calls[0].url, '/api/v1/query/stream?q=hello&mode=combined&top_k=5')
  assert.equal(calls[0].init.headers.Accept, 'text/event-stream')
  assert.equal(calls[0].init.headers['X-API-Key'], 'secret-key')
  assert.equal(calls[0].init.headers['Content-Type'], undefined)

  assert.equal(calls[1].url, '/api/v1/files/upload')
  assert.equal(calls[1].init.headers['X-API-Key'], 'secret-key')
  assert.equal(calls[1].init.headers['Content-Type'], undefined)

  assert.equal(calls[2].url, '/api/v1/metrics')
  assert.equal(calls[2].init.headers.Accept, 'text/plain')
  assert.equal(calls[2].init.headers['X-API-Key'], 'secret-key')
  assert.equal(calls[2].init.headers['Content-Type'], undefined)
})

test('non-2xx errors surface backend detail consistently', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'not authorized' }), { status: 401 })
  const api = await loadApiModule()

  await assert.rejects(api.getStatus(), /not authorized/)
  await assert.rejects(api.getMetrics(), /not authorized/)
})

test('plain-text backend errors are preserved after parsing', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response('upstream unavailable', { status: 502 })
  const api = await loadApiModule()

  await assert.rejects(api.getStatus(), /upstream unavailable/)
})

test('stream done callback exposes contribution metadata', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response([
    'event: done',
    'data: {"time_seconds":1.2,"trace_id":"trace-1","contribution":{"id":"QAC-1","quality_score":88,"needs_review":true,"auto_promoted":false}}',
    '',
    '',
  ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  const api = await loadApiModule()
  let done

  await api.queryKnowledgeStream('hello', 'combined', 5, {
    onDone(finalTime, traceId, contribution) {
      done = { finalTime, traceId, contribution }
    },
  })

  assert.deepEqual(done, {
    finalTime: 1.2,
    traceId: 'trace-1',
    contribution: {
      id: 'QAC-1',
      quality_score: 88,
      needs_review: true,
      auto_promoted: false,
    },
  })
})

test('stream options API forwards read-only flags but never contribution intent', async () => {
  installBrowserMocks()
  const controller = new AbortController()
  const originalTimeout = AbortSignal.timeout
  let timeoutMs
  const timeoutController = new AbortController()
  AbortSignal.timeout = (ms) => {
    timeoutMs = ms
    return timeoutController.signal
  }
  const calls = []
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, init })
    return new Response([
      'event: done',
      'data: {"time_seconds":0.4}',
      '',
      '',
    ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  }
  const api = await loadApiModule()

  try {
    await api.queryKnowledgeStream('hello world', {
      mode: 'all',
      topK: 8,
      rerank: true,
      contribute: true,
      signal: controller.signal,
      timeoutMs: 1500,
      callbacks: {},
    })
  } finally {
    AbortSignal.timeout = originalTimeout
  }

  assert.equal(calls[0].url, '/api/v1/query/stream?q=hello%20world&mode=all&top_k=8&rerank=true')
  assert.notEqual(calls[0].init.signal, controller.signal)
  assert.equal(timeoutMs, 1500)
  assert.equal(calls[0].init.signal.aborted, false)
  timeoutController.abort('stream-timeout')
  assert.equal(calls[0].init.signal.aborted, true)
  assert.equal(calls[0].init.signal.reason, 'stream-timeout')
})

test('stream composed signal still aborts from the caller signal', async () => {
  installBrowserMocks()
  const controller = new AbortController()
  const calls = []
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, init })
    return new Response([
      'event: done',
      'data: {"time_seconds":0.4}',
      '',
      '',
    ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  }
  const api = await loadApiModule()

  await api.queryKnowledgeStream('hello world', {
    signal: controller.signal,
    callbacks: {},
  })

  assert.equal(calls[0].init.signal.aborted, false)
  controller.abort()
  assert.equal(calls[0].init.signal.aborted, true)
})

test('stream done exposes structured phase timings without losing contribution metadata', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response([
    'event: done',
    'data: {"time_seconds":1.2,"trace_id":"trace-1","phase_timings":{"retrieval":0.3,"generation":0.9},"contribution":{"id":"QAC-1","quality_score":88,"needs_review":true,"auto_promoted":false}}',
    '',
    '',
  ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  const api = await loadApiModule()
  let positional
  let detailed

  await api.queryKnowledgeStream('hello', {
    callbacks: {
      onDone(finalTime, traceId, contribution, phaseTimings) {
        positional = { finalTime, traceId, contribution, phaseTimings }
      },
      onDoneDetailed(done) {
        detailed = done
      },
    },
  })

  assert.deepEqual(positional, {
    finalTime: 1.2,
    traceId: 'trace-1',
    contribution: {
      id: 'QAC-1',
      quality_score: 88,
      needs_review: true,
      auto_promoted: false,
    },
    phaseTimings: {
      retrieval: 0.3,
      generation: 0.9,
    },
  })
  assert.deepEqual(detailed, {
    time_seconds: 1.2,
    trace_id: 'trace-1',
    contribution: positional.contribution,
    phase_timings: positional.phaseTimings,
  })
})

test('API errors carry status and code while preserving message', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'not authorized', code: 'AUTH_REQUIRED' }), { status: 401 })
  const api = await loadApiModule()

  await assert.rejects(
    api.getStatus(),
    (error) => error instanceof Error
      && error.message === 'not authorized'
      && error.status === 401
      && error.code === 'AUTH_REQUIRED',
  )
})

test('network failures are normalized as offline API errors', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch') }
  const api = await loadApiModule()

  await assert.rejects(
    api.queryKnowledgeStream('hello', { callbacks: {} }),
    (error) => error instanceof Error
      && error.message === '无法连接后端 API'
      && error.code === 'OFFLINE',
  )
})

test('stream reader abort failures are normalized as cancelled API errors', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response(new ReadableStream({
    pull(controller) {
      controller.error(new DOMException('The operation was aborted.', 'AbortError'))
    },
  }), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  const api = await loadApiModule()

  await assert.rejects(
    api.queryKnowledgeStream('hello', { callbacks: {} }),
    (error) => error instanceof Error
      && error.message === '请求已取消'
      && error.code === 'ABORTED',
  )
})

test('stream reader timeout failures are normalized as timeout API errors', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response(new ReadableStream({
    pull(controller) {
      controller.error(new DOMException('The operation timed out.', 'TimeoutError'))
    },
  }), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  const api = await loadApiModule()

  await assert.rejects(
    api.queryKnowledgeStream('hello', { callbacks: {} }),
    (error) => error instanceof Error
      && error.message === '请求超时，请稍后重试'
      && error.code === 'TIMEOUT',
  )
})

test('stream parser dispatches only the first terminal event', async () => {
  installBrowserMocks()
  const api = await loadApiModule()

  globalThis.fetch = async () => new Response([
    'event: error',
    'data: {"message":"boom","code":"SERVER_ERROR"}',
    '',
    'event: done',
    'data: {"time_seconds":9}',
    '',
    '',
  ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  let errors = 0
  let done = 0
  await api.queryKnowledgeStream('hello', {
    callbacks: {
      onError() { errors += 1 },
      onDone() { done += 1 },
    },
  })
  assert.equal(errors, 1)
  assert.equal(done, 0)

  globalThis.fetch = async () => new Response([
    'event: done',
    'data: {"time_seconds":1}',
    '',
    'event: error',
    'data: {"message":"late error","code":"SERVER_ERROR"}',
    '',
    '',
  ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  errors = 0
  done = 0
  await api.queryKnowledgeStream('hello', {
    callbacks: {
      onError() { errors += 1 },
      onDone() { done += 1 },
    },
  })
  assert.equal(done, 1)
  assert.equal(errors, 0)
})

test('stream error exposes stable code trace and phase timings', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response([
    'event: error',
    'data: {"message":"deadline","code":"TIMEOUT","trace_id":"trace-err","phase_timings":{"retrieval_seconds":0.2,"generation_seconds":2.5}}',
    '',
    '',
  ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  const api = await loadApiModule()
  let received

  await api.queryKnowledgeStream('hello', {
    callbacks: {
      onError(message, detail) {
        received = { message, detail }
      },
    },
  })

  assert.deepEqual(received, {
    message: 'deadline',
    detail: {
      message: 'deadline',
      code: 'TIMEOUT',
      trace_id: 'trace-err',
      phase_timings: {
        retrieval_seconds: 0.2,
        generation_seconds: 2.5,
      },
    },
  })
})

test('malformed terminal stream events surface a typed parse error once', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response([
    'event: done',
    'data: {"time_seconds":',
    '',
    'event: error',
    'data: {"message":"late"}',
    '',
    '',
  ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  const api = await loadApiModule()
  let errors = 0
  let detail
  let done = 0

  await api.queryKnowledgeStream('hello', {
    callbacks: {
      onDone() { done += 1 },
      onError(_message, nextDetail) {
        errors += 1
        detail = nextDetail
      },
    },
  })

  assert.equal(done, 0)
  assert.equal(errors, 1)
  assert.equal(detail.code, 'PARSE_ERROR')

  globalThis.fetch = async () => new Response([
    'event: error',
    'data: {"message":',
    '',
    '',
  ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  errors = 0
  detail = undefined

  await api.queryKnowledgeStream('hello', {
    callbacks: {
      onError(_message, nextDetail) {
        errors += 1
        detail = nextDetail
      },
    },
  })

  assert.equal(errors, 1)
  assert.equal(detail.code, 'PARSE_ERROR')
})

test('stream EOF without a terminal event surfaces an incomplete stream error', async () => {
  installBrowserMocks()
  globalThis.fetch = async () => new Response([
    'event: meta',
    'data: {"query":"hello","mode":"combined","search_sources":[],"time_seconds":0}',
    '',
    '',
  ].join('\n'), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
  const api = await loadApiModule()
  let detail

  await api.queryKnowledgeStream('hello', {
    callbacks: {
      onError(_message, nextDetail) {
        detail = nextDetail
      },
    },
  })

  assert.equal(detail.code, 'STREAM_INCOMPLETE')
})
