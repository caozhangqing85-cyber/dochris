import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { access, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url))
const DIST_ROOT = path.resolve(SCRIPT_DIR, '../dist')
const INDEX_PATH = path.join(DIST_ROOT, 'index.html')
const TEST_TIMEOUT_MS = 15_000

const manifests = [
  {
    id: 'manifest-high',
    title: '高质量文档.md',
    type: 'markdown',
    status: 'compiled',
    quality_score: 92,
    file_path: '/fixtures/高质量文档.md',
    size_bytes: 2048,
    original_filename: '高质量文档.md',
    compiled_summary: {
      one_line: '用于浏览器验收的高质量只读样例。',
      key_points: ['真实 React 页面', '隔离 mock API'],
      detailed_summary: '此数据仅存在于端到端测试进程。',
      concepts: ['浏览器验收'],
      quality_score: 92,
      provenance: {
        overall_label: 'extracted',
        confidence: 0.98,
        summary_label: 'extracted',
        concepts: [],
        signals: [],
      },
      lint: {
        passed: true,
        score: 100,
        error_count: 0,
        warning_count: 0,
        info_count: 0,
        issues: [],
      },
    },
  },
  {
    id: 'manifest-low',
    title: '低质量文档.md',
    type: 'markdown',
    status: 'compiled',
    quality_score: 70,
    file_path: '/fixtures/低质量文档.md',
    size_bytes: 1024,
    original_filename: '低质量文档.md',
    compiled_summary: {
      one_line: '用于验证低质量重置确认的隔离样例。',
      key_points: [],
      detailed_summary: '此数据仅存在于端到端测试进程。',
      concepts: [],
      quality_score: 70,
    },
  },
]

const statusFixture = {
  workspace: '/fixtures/dochris-smoke',
  version: 'e2e-smoke',
  manifests: {
    total: 2,
    ingested: 0,
    compiled: 2,
    failed: 0,
    promoted_to_wiki: 0,
    promoted: 0,
    by_type: { markdown: 2 },
    trust_levels: {},
    concepts_count: 1,
    summaries_count: 2,
  },
  config: {
    model: 'fixture-model',
    api_base: 'http://fixture.invalid/v1',
    max_concurrency: 1,
    min_quality_score: 85,
    has_api_key: false,
    query_model: 'fixture-query-model',
    llm_provider: 'openai_compat',
    workspace: '/fixtures/dochris-smoke',
    temperature: 0.1,
  },
  system: {
    python_version: 'fixture',
    platform: 'browser-e2e',
    disk_usage_bytes: 1024,
    disk_total_bytes: 2048,
  },
}

const configFixture = {
  api_base: 'http://fixture.invalid/v1',
  api_key: '',
  model: 'fixture-model',
  query_model: 'fixture-query-model',
  llm_provider: 'openai_compat',
  temperature: 0.1,
  workspace: '/fixtures/dochris-smoke',
  vector_store: 'chromadb',
}

const candidatesFixture = {
  candidates: [
    {
      id: 'candidate-browser-smoke',
      title: '浏览器验收候选',
      query: '如何验证危险操作确认？',
      quality_score: 92,
      status: 'candidate',
      needs_review: true,
      source_manifest_ids: ['manifest-high'],
      answer: '所有写操作都必须先清楚说明影响并允许用户取消。',
    },
  ],
  total: 1,
}

const graphFixture = {
  success: true,
  data: {
    nodes: [
      { id: 'concept-browser', label: '浏览器验收', node_type: 'concept' },
      { id: 'source-browser', label: '高质量文档.md', node_type: 'source' },
      { id: 'summary-browser', label: '高质量文档摘要', node_type: 'summary' },
    ],
    edges: [
      { source: 'source-browser', target: 'concept-browser', relation: 'mentions', weight: 0.9 },
      { source: 'source-browser', target: 'summary-browser', relation: 'summarizes', weight: 1 },
    ],
  },
  version: 'e2e-smoke',
}

const emptyGraphFixture = {
  success: true,
  data: { nodes: [], edges: [] },
  version: 'e2e-empty',
}

function createLargeGraphFixture() {
  const nodes = [
    ...Array.from({ length: 80 }, (_, index) => ({
      id: `concept-large-${index}`,
      label: index === 0
        ? '移动端节点详情需要完整可见且可以安全关闭'
        : `规模化概念 ${index + 1}`,
      node_type: 'concept',
      metadata: {
        category: index % 2 === 0 ? '浏览器验收' : '规模测试',
        source: `large-graph-fixture-${index}`,
      },
    })),
    ...Array.from({ length: 20 }, (_, index) => ({
      id: `source-large-${index}`,
      label: `规模化源文档 ${index + 1}.md`,
      node_type: 'source',
    })),
    ...Array.from({ length: 20 }, (_, index) => ({
      id: `summary-large-${index}`,
      label: `规模化摘要 ${index + 1}`,
      node_type: 'summary',
    })),
  ]
  const edges = nodes.map((node, index) => ({
    source: node.id,
    target: nodes[(index + 1) % nodes.length].id,
    relation: 'related_to',
    weight: 0.75,
  }))

  return {
    success: true,
    data: { nodes, edges },
    version: 'e2e-large',
  }
}

const BROWSER_E2E_ACCESS_KEY = 'browser-e2e-secret'

const contentTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.ico', 'image/x-icon'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.map', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml'],
  ['.webp', 'image/webp'],
])

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

function formatSse(eventName, data) {
  const payload = typeof data === 'string' ? data : JSON.stringify(data)
  return `event: ${eventName}\ndata: ${payload}\n\n`
}

async function readRequestBody(request) {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  return Buffer.concat(chunks).toString('utf8')
}

function buildStatusFixture(fixtureManifests) {
  const statusCounts = fixtureManifests.reduce((counts, manifest) => {
    counts[manifest.status] = (counts[manifest.status] ?? 0) + 1
    return counts
  }, {})
  const byType = fixtureManifests.reduce((counts, manifest) => {
    counts[manifest.type] = (counts[manifest.type] ?? 0) + 1
    return counts
  }, {})
  const compiledManifests = fixtureManifests.filter((manifest) => (
    manifest.status === 'compiled'
    || manifest.status === 'promoted'
    || manifest.status === 'promoted_to_wiki'
  ))

  return {
    ...statusFixture,
    manifests: {
      ...statusFixture.manifests,
      total: fixtureManifests.length,
      ingested: statusCounts.ingested ?? 0,
      compiled: statusCounts.compiled ?? 0,
      failed: (statusCounts.failed ?? 0) + (statusCounts.compile_failed ?? 0),
      promoted_to_wiki: statusCounts.promoted_to_wiki ?? 0,
      promoted: statusCounts.promoted ?? 0,
      by_type: byType,
      concepts_count: compiledManifests.reduce(
        (total, manifest) => total + (manifest.compiled_summary?.concepts?.length ?? 0),
        0,
      ),
      summaries_count: compiledManifests.length,
    },
  }
}

function sendJson(response, statusCode, body) {
  response.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
  })
  response.end(JSON.stringify(body))
}

async function createFixtureServer() {
  await access(INDEX_PATH)
  const indexHtml = await readFile(INDEX_PATH)
  const mutationRequests = []
  const telemetry = {
    startedQueries: [],
    cancelledQueries: [],
    completedQueries: [],
    timedOutQueries: [],
    authFailures: [],
    authenticatedRequests: [],
    networkDrops: [],
  }
  let mode = 'safety'
  let offlineRestored = false
  let fixtureManifests = structuredClone(manifests)
  let fixtureCandidates = structuredClone(candidatesFixture.candidates)
  let fixtureGraph = structuredClone(graphFixture)
  let compileJob = null
  let compileHistory = []

  const recordCompileJob = (job) => {
    compileHistory = [
      structuredClone(job),
      ...compileHistory.filter((item) => item.job_id !== job.job_id),
    ]
  }

  const server = http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url ?? '/', 'http://127.0.0.1')

      if (url.pathname.startsWith('/api/v1/')) {
        if (mode === 'auth' && request.method === 'GET') {
          if (request.headers['x-api-key'] !== BROWSER_E2E_ACCESS_KEY) {
            telemetry.authFailures.push(url.pathname)
            sendJson(response, 401, { detail: 'Missing or invalid API key', code: 'UNAUTHORIZED' })
            return
          }
          telemetry.authenticatedRequests.push(url.pathname)
        }

        if (request.method !== 'GET') {
          const mutation = { method: request.method, path: `${url.pathname}${url.search}` }
          mutationRequests.push(mutation)
          if (mode !== 'journey' && mode !== 'compile-job') {
            sendJson(response, 409, { detail: 'Mutation blocked by browser smoke fixture' })
            return
          }

          const compileCancellation = url.pathname.match(
            /^\/api\/v1\/compile\/jobs\/([^/]+)\/cancel$/,
          )
          if (compileCancellation && request.method === 'POST') {
            const jobId = decodeURIComponent(compileCancellation[1])
            assert.equal(jobId, compileJob?.job_id)
            compileJob = {
              ...compileJob,
              status: 'cancelled',
              message: '编译已取消',
              current_files: [],
              cancel_requested: true,
              retryable: true,
              finished_at: new Date().toISOString(),
            }
            recordCompileJob(compileJob)
            sendJson(response, 200, compileJob)
            return
          }

          const compileRetry = url.pathname.match(
            /^\/api\/v1\/compile\/jobs\/([^/]+)\/retry$/,
          )
          if (compileRetry && request.method === 'POST') {
            const sourceId = decodeURIComponent(compileRetry[1])
            const sourceJob = compileHistory.find((item) => item.job_id === sourceId)
            assert(sourceJob?.retryable, `Compile job ${sourceId} is not retryable`)
            const now = new Date().toISOString()
            compileJob = {
              ...sourceJob,
              job_id: 'compile-retry',
              status: 'completed',
              message: '编译完成',
              processed: sourceJob.total,
              compiled: sourceJob.total,
              failed: 0,
              current_files: [],
              cancel_requested: false,
              attempt: sourceJob.attempt + 1,
              retry_of: sourceId,
              retryable: false,
              error: null,
              created_at: now,
              started_at: now,
              finished_at: now,
            }
            recordCompileJob(compileJob)
            sendJson(response, 200, {
              ...compileJob,
              status: 'accepted',
              message: '已提交重试任务: 1 个文档',
              processed: 0,
              compiled: 0,
              finished_at: null,
            })
            return
          }

          if (url.pathname === '/api/v1/files/upload' && request.method === 'POST') {
            await readRequestBody(request)
            fixtureManifests.push({
              id: 'manifest-browser-journey',
              title: 'browser-journey.md',
              type: 'markdown',
              status: 'ingested',
              quality_score: null,
              file_path: '/fixtures/browser-journey.md',
              size_bytes: 180,
              original_filename: 'browser-journey.md',
            })
            sendJson(response, 200, { saved: 1, ingested: 1, failed: 0 })
            return
          }

          if (url.pathname === '/api/v1/compile' && request.method === 'POST') {
            const body = JSON.parse(await readRequestBody(request))
            assert.equal(body.dry_run, false)
            const pending = fixtureManifests.filter((manifest) => manifest.status === 'ingested')
            for (const manifest of pending) {
              manifest.status = 'compiled'
              manifest.quality_score = 93
              manifest.compiled_summary = {
                one_line: 'Dochris 浏览器完整旅程的隔离编译结果。',
                key_points: ['上传', '编译', '查询', '贡献', '晋升'],
                detailed_summary: 'fixture server 只在测试进程内维护这份状态。',
                concepts: ['完整浏览器旅程'],
                quality_score: 93,
              }
            }
            compileJob = {
              job_id: 'compile-journey',
              status: 'completed',
              message: '编译完成',
              total: pending.length,
              processed: pending.length,
              compiled: pending.length,
              failed: 0,
              current_files: [],
              cancel_requested: false,
              concurrency: body.concurrency,
              limit: body.limit,
              attempt: 1,
              retry_of: null,
              retryable: false,
              error: null,
              created_at: new Date().toISOString(),
              started_at: new Date().toISOString(),
              finished_at: new Date().toISOString(),
            }
            recordCompileJob(compileJob)
            sendJson(response, 200, {
              ...compileJob,
              status: 'accepted',
              message: `已提交 ${pending.length} 个文件编译`,
              processed: 0,
              compiled: 0,
            })
            return
          }

          if (url.pathname === '/api/v1/query/contribution' && request.method === 'POST') {
            const queryResult = JSON.parse(await readRequestBody(request))
            fixtureCandidates.push({
              id: 'candidate-journey',
              title: '完整浏览器旅程贡献',
              query: queryResult.query,
              quality_score: 92,
              status: 'candidate',
              needs_review: true,
              source_manifest_ids: ['manifest-browser-journey'],
              answer: queryResult.answer,
            })
            sendJson(response, 200, {
              id: 'candidate-journey',
              quality_score: 92,
              needs_review: true,
              auto_promoted: false,
            })
            return
          }

          const candidatePromotion = url.pathname.match(/^\/api\/v1\/candidates\/([^/]+)\/promote$/)
          if (candidatePromotion && request.method === 'POST') {
            await readRequestBody(request)
            const candidateId = decodeURIComponent(candidatePromotion[1])
            const candidate = fixtureCandidates.find((item) => item.id === candidateId)
            assert(candidate, `Unknown candidate ${candidateId}`)
            candidate.status = 'promoted'
            sendJson(response, 200, { success: true })
            return
          }

          sendJson(response, 409, { detail: `Unexpected journey mutation ${mutation.path}` })
          return
        }

        if (url.pathname === '/api/v1/compile/jobs/current') {
          if (!compileJob) {
            sendJson(response, 404, { detail: '暂无编译任务' })
          } else {
            sendJson(response, 200, compileJob)
          }
          return
        }
        if (url.pathname === '/api/v1/compile/jobs') {
          const limit = Number.parseInt(url.searchParams.get('limit') ?? '20', 10)
          sendJson(response, 200, compileHistory.slice(0, limit))
          return
        }
        const compileJobStatus = url.pathname.match(/^\/api\/v1\/compile\/jobs\/([^/]+)$/)
        if (compileJobStatus) {
          const jobId = decodeURIComponent(compileJobStatus[1])
          if (!compileJob || compileJob.job_id !== jobId) {
            sendJson(response, 404, { detail: '编译任务不存在' })
          } else {
            sendJson(response, 200, compileJob)
          }
          return
        }
        if (url.pathname === '/api/v1/status') {
          sendJson(response, 200, buildStatusFixture(fixtureManifests))
          return
        }
        if (url.pathname === '/api/v1/manifests') {
          if (mode === 'offline' && !offlineRestored) {
            telemetry.networkDrops.push(url.pathname)
            request.socket.destroy()
            return
          }
          sendJson(response, 200, fixtureManifests)
          return
        }
        if (url.pathname === '/api/v1/config') {
          sendJson(response, 200, configFixture)
          return
        }
        if (url.pathname === '/api/v1/candidates') {
          const requestedStatus = url.searchParams.get('status')
          const filteredCandidates = requestedStatus
            ? fixtureCandidates.filter((candidate) => candidate.status === requestedStatus)
            : fixtureCandidates
          sendJson(response, 200, { candidates: filteredCandidates, total: filteredCandidates.length })
          return
        }
        if (url.pathname === '/api/v1/graph') {
          sendJson(response, 200, fixtureGraph)
          return
        }
        const graphNodeDetail = url.pathname.match(/^\/api\/v1\/graph\/node\/([^/]+)$/)
        if (graphNodeDetail) {
          const nodeId = decodeURIComponent(graphNodeDetail[1])
          const node = fixtureGraph.data.nodes.find((item) => item.id === nodeId)
          if (!node) {
            sendJson(response, 404, { detail: `Unknown graph node ${nodeId}` })
            return
          }
          const neighborIds = new Set()
          for (const edge of fixtureGraph.data.edges) {
            if (edge.source === nodeId) neighborIds.add(edge.target)
            if (edge.target === nodeId) neighborIds.add(edge.source)
          }
          const neighbors = fixtureGraph.data.nodes.filter((item) => neighborIds.has(item.id))
          sendJson(response, 200, {
            success: true,
            data: { node, neighbors, neighbor_count: neighbors.length },
            version: fixtureGraph.version,
          })
          return
        }
        if (url.pathname === '/api/v1/query/stream') {
          const query = url.searchParams.get('q') ?? ''
          telemetry.startedQueries.push(query)
          response.writeHead(200, {
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Content-Type': 'text/event-stream; charset=utf-8',
          })
          response.write(formatSse('meta', {
            query,
            mode: url.searchParams.get('mode') ?? 'combined',
            search_sources: ['summary'],
            time_seconds: 0.01,
          }))
          response.write(formatSse('retrieval', {
            concepts: [{
              title: '完整浏览器旅程',
              content: '覆盖上传、编译、查询、贡献与候选晋升。',
              source: 'concept',
              file_path: '/fixtures/browser-journey.md',
              manifest_id: 'manifest-browser-journey',
            }],
            summaries: [{
              title: 'browser-journey.md',
              content: 'Dochris 浏览器完整旅程的隔离编译结果。',
              source: 'summary',
              file_path: '/fixtures/browser-journey.md',
              manifest_id: 'manifest-browser-journey',
            }],
            vector_results: [],
          }))

          if (query.includes('超时')) {
            telemetry.timedOutQueries.push(query)
            response.end(formatSse('error', {
              code: 'TIMEOUT',
              message: '模拟的 provider 总预算已耗尽',
              retryable: true,
              phase_timings: { retrieval: 0.01, generation: 15, total: 15.01 },
            }))
            return
          }

          if (query.includes('取消')) {
            let completionTimer
            response.once('close', () => {
              clearTimeout(completionTimer)
              if (!response.writableEnded && !telemetry.cancelledQueries.includes(query)) {
                telemetry.cancelledQueries.push(query)
              }
            })
            completionTimer = setTimeout(() => {
              if (response.destroyed) return
              response.write(formatSse('answer_delta', '不应抵达客户端的延迟回答'))
              response.end(formatSse('done', { time_seconds: 30 }))
            }, 30_000)
            completionTimer.unref()
            return
          }

          response.write(formatSse('answer_delta', '隔离浏览器完整旅程'))
          response.write(formatSse('answer_delta', '已经通过。'))
          telemetry.completedQueries.push(query)
          response.end(formatSse('done', {
            time_seconds: 0.12,
            trace_id: 'trace-browser-journey',
            phase_timings: { retrieval: 0.01, generation: 0.08, total: 0.12 },
          }))
          return
        }
        if (url.pathname === '/api/v1/recompile/status') {
          sendJson(response, 200, { running: false, stale_count: 0, status: 'idle' })
          return
        }
        if (url.pathname === '/api/v1/schema/stale') {
          sendJson(response, 200, { stale: [] })
          return
        }

        sendJson(response, 404, { detail: `No fixture for ${url.pathname}` })
        return
      }

      const decodedPath = decodeURIComponent(url.pathname)
      const relativePath = decodedPath.replace(/^\/+/, '')
      const requestedPath = path.resolve(DIST_ROOT, relativePath)
      const isWithinDist = requestedPath === DIST_ROOT || requestedPath.startsWith(`${DIST_ROOT}${path.sep}`)

      if (!isWithinDist) {
        response.writeHead(403)
        response.end('Forbidden')
        return
      }

      try {
        const fileStat = await stat(requestedPath)
        if (fileStat.isFile()) {
          const extension = path.extname(requestedPath).toLowerCase()
          response.writeHead(200, {
            'Cache-Control': 'no-store',
            'Content-Type': contentTypes.get(extension) ?? 'application/octet-stream',
          })
          response.end(await readFile(requestedPath))
          return
        }
      } catch {
        // BrowserRouter paths deliberately fall through to index.html.
      }

      response.writeHead(200, {
        'Cache-Control': 'no-store',
        'Content-Type': 'text/html; charset=utf-8',
      })
      response.end(indexHtml)
    } catch (error) {
      response.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
      response.end(error instanceof Error ? error.stack : String(error))
    }
  })

  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })

  const address = server.address()
  assert(address && typeof address === 'object', 'Fixture server did not expose a TCP address')

  const resetFixtureState = (nextMode, { empty = false, graph = graphFixture } = {}) => {
    mode = nextMode
    offlineRestored = false
    fixtureManifests = empty ? [] : structuredClone(manifests)
    fixtureCandidates = empty ? [] : structuredClone(candidatesFixture.candidates)
    fixtureGraph = structuredClone(graph)
    compileJob = null
    compileHistory = []
    mutationRequests.length = 0
    for (const values of Object.values(telemetry)) values.length = 0
  }

  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    close: () => new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve()))),
    mutationRequests,
    startJourney() {
      resetFixtureState('journey', { empty: true })
    },
    startCompileJobLifecycle() {
      resetFixtureState('compile-job', { empty: true })
      fixtureManifests.push({
        id: 'manifest-compile-active',
        title: '正在编译的浏览器夹具.md',
        type: 'markdown',
        status: 'compiling',
        quality_score: null,
        file_path: '/fixtures/正在编译的浏览器夹具.md',
        size_bytes: 512,
        original_filename: '正在编译的浏览器夹具.md',
      })
      compileJob = {
        job_id: 'compile-active',
        status: 'running',
        message: '编译进行中',
        total: 1,
        processed: 0,
        compiled: 0,
        failed: 0,
        current_files: ['manifest-compile-active'],
        cancel_requested: false,
        concurrency: 1,
        limit: 1,
        attempt: 1,
        retry_of: null,
        retryable: false,
        error: null,
        created_at: new Date().toISOString(),
        started_at: new Date().toISOString(),
        finished_at: null,
      }
      recordCompileJob(compileJob)
    },
    simulateCompileServiceRestart() {
      const now = new Date().toISOString()
      compileJob = {
        ...compileJob,
        job_id: 'compile-interrupted',
        status: 'interrupted',
        message: '服务重启，编译任务已中断',
        current_files: [],
        cancel_requested: false,
        retryable: true,
        error: 'ServiceRestart: 编译服务在任务完成前退出',
        created_at: now,
        started_at: now,
        finished_at: now,
      }
      recordCompileJob(compileJob)
    },
    startAuthRecovery() {
      resetFixtureState('auth')
    },
    startOfflineRecovery() {
      resetFixtureState('offline')
    },
    restoreNetwork() {
      offlineRestored = true
    },
    startResponsive() {
      resetFixtureState('responsive')
    },
    startEmptyWorkspace() {
      resetFixtureState('empty', { empty: true, graph: emptyGraphFixture })
    },
    startLargeGraph() {
      resetFixtureState('large-graph', { empty: true, graph: createLargeGraphFixture() })
    },
    telemetry,
  }
}

async function findChromeExecutable() {
  const candidates = [
    process.env.CHROME_BIN,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter(Boolean)

  for (const candidate of candidates) {
    try {
      await access(candidate)
      return candidate
    } catch {
      // Try the next conventional Chrome/Chromium location.
    }
  }

  throw new Error(`Chrome/Chromium not found. Checked: ${candidates.join(', ')}`)
}

async function waitForDevTools(profileDirectory, chromeProcess, stderrLines) {
  const activePortPath = path.join(profileDirectory, 'DevToolsActivePort')
  const deadline = Date.now() + TEST_TIMEOUT_MS

  while (Date.now() < deadline) {
    if (chromeProcess.exitCode !== null) {
      throw new Error(`Chrome exited before DevTools became ready (code ${chromeProcess.exitCode}).\n${stderrLines.join('')}`)
    }

    try {
      const [port, browserPath] = (await readFile(activePortPath, 'utf8')).trim().split(/\r?\n/)
      if (port && browserPath) return `ws://127.0.0.1:${port}${browserPath}`
    } catch {
      // Chrome creates DevToolsActivePort after its browser process is ready.
    }

    await delay(50)
  }

  throw new Error(`Timed out waiting for Chrome DevTools.\n${stderrLines.join('')}`)
}

async function launchChrome() {
  const executable = await findChromeExecutable()
  const profileDirectory = await mkdtemp(path.join(os.tmpdir(), 'dochris-chrome-e2e-'))
  const args = [
    '--headless=new',
    '--remote-debugging-port=0',
    `--user-data-dir=${profileDirectory}`,
    '--disable-background-networking',
    '--disable-component-update',
    '--disable-default-apps',
    '--disable-dev-shm-usage',
    '--disable-extensions',
    '--disable-features=MediaRouter,Translate',
    '--disable-gpu',
    '--disable-sync',
    '--metrics-recording-only',
    '--no-default-browser-check',
    '--no-first-run',
    'about:blank',
  ]
  if (process.platform === 'linux') args.unshift('--no-sandbox')

  const chromeProcess = spawn(executable, args, { stdio: ['ignore', 'ignore', 'pipe'] })
  const stderrLines = []
  chromeProcess.stderr.setEncoding('utf8')
  chromeProcess.stderr.on('data', (chunk) => stderrLines.push(chunk))

  try {
    const webSocketUrl = await waitForDevTools(profileDirectory, chromeProcess, stderrLines)
    return { chromeProcess, profileDirectory, webSocketUrl }
  } catch (error) {
    chromeProcess.kill('SIGTERM')
    await removeProfileDirectory(profileDirectory)
    throw error
  }
}

async function stopChrome(chromeProcess, profileDirectory) {
  if (chromeProcess.exitCode === null) {
    chromeProcess.kill('SIGTERM')
    await Promise.race([once(chromeProcess, 'exit'), delay(3_000)])
  }
  if (chromeProcess.exitCode === null) chromeProcess.kill('SIGKILL')
  await removeProfileDirectory(profileDirectory)
}

// Chrome 退出后可能仍短暂持有 profile 文件句柄，rm 需要重试兜底
async function removeProfileDirectory(profileDirectory) {
  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      await rm(profileDirectory, { recursive: true, force: true })
      return
    } catch (error) {
      if (attempt === 5) throw error
      await delay(500 * attempt)
    }
  }
}

class DevToolsClient {
  constructor(webSocketUrl) {
    this.nextId = 1
    this.pending = new Map()
    this.waiters = []
    this.listeners = new Map()
    this.socket = new WebSocket(webSocketUrl)
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true })
      this.socket.addEventListener('error', () => reject(new Error('Failed to connect to Chrome DevTools')), { once: true })
    })
    this.socket.addEventListener('message', (event) => this.handleMessage(event.data))
  }

  handleMessage(rawMessage) {
    const message = JSON.parse(String(rawMessage))
    if (message.id) {
      const pending = this.pending.get(message.id)
      if (!pending) return
      this.pending.delete(message.id)
      if (message.error) pending.reject(new Error(`${message.error.message} (${message.error.code})`))
      else pending.resolve(message.result ?? {})
      return
    }

    const listeners = this.listeners.get(message.method) ?? []
    for (const listener of listeners) listener(message.params ?? {}, message.sessionId)

    for (const waiter of [...this.waiters]) {
      if (waiter.method !== message.method) continue
      if (waiter.sessionId && waiter.sessionId !== message.sessionId) continue
      if (!waiter.predicate(message.params ?? {})) continue
      clearTimeout(waiter.timer)
      this.waiters.splice(this.waiters.indexOf(waiter), 1)
      waiter.resolve(message.params ?? {})
    }
  }

  async send(method, params = {}, sessionId) {
    await this.ready
    const id = this.nextId++
    const message = { id, method, params }
    if (sessionId) message.sessionId = sessionId

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.socket.send(JSON.stringify(message))
    })
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) ?? []
    listeners.push(listener)
    this.listeners.set(method, listeners)
  }

  waitForEvent(method, { sessionId, predicate = () => true, timeoutMs = TEST_TIMEOUT_MS } = {}) {
    return new Promise((resolve, reject) => {
      const waiter = { method, sessionId, predicate, resolve, reject, timer: undefined }
      waiter.timer = setTimeout(() => {
        this.waiters.splice(this.waiters.indexOf(waiter), 1)
        reject(new Error(`Timed out waiting for DevTools event ${method}`))
      }, timeoutMs)
      this.waiters.push(waiter)
    })
  }

  close() {
    this.socket.close()
  }
}

async function createBrowserSession(client) {
  const { targetId } = await client.send('Target.createTarget', { url: 'about:blank' })
  const { sessionId } = await client.send('Target.attachToTarget', { targetId, flatten: true })
  await client.send('DOM.enable', {}, sessionId)
  await client.send('Page.enable', {}, sessionId)
  await client.send('Runtime.enable', {}, sessionId)
  return sessionId
}

async function evaluate(client, sessionId, expression) {
  const result = await client.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true,
  }, sessionId)

  if (result.exceptionDetails) {
    const description = result.exceptionDetails.exception?.description
      ?? result.exceptionDetails.text
      ?? 'Unknown browser evaluation failure'
    throw new Error(description)
  }
  return result.result?.value
}

async function navigate(client, sessionId, url) {
  const loaded = client.waitForEvent('Page.loadEventFired', { sessionId })
  await client.send('Page.navigate', { url }, sessionId)
  await loaded
}

async function pressKey(client, sessionId, key, { shift = false } = {}) {
  const definitions = {
    Enter: { code: 'Enter', windowsVirtualKeyCode: 13 },
    Escape: { code: 'Escape', windowsVirtualKeyCode: 27 },
    Tab: { code: 'Tab', windowsVirtualKeyCode: 9 },
    ArrowDown: { code: 'ArrowDown', windowsVirtualKeyCode: 40 },
    ArrowUp: { code: 'ArrowUp', windowsVirtualKeyCode: 38 },
  }
  const definition = definitions[key]
  assert(definition, `Unsupported browser smoke key: ${key}`)
  const event = {
    key,
    code: definition.code,
    windowsVirtualKeyCode: definition.windowsVirtualKeyCode,
    nativeVirtualKeyCode: definition.windowsVirtualKeyCode,
    modifiers: shift ? 8 : 0,
  }
  const keyDownEvent = key === 'Enter'
    ? { ...event, text: '\r', unmodifiedText: '\r' }
    : event
  await client.send('Input.dispatchKeyEvent', { type: 'keyDown', ...keyDownEvent }, sessionId)
  await client.send('Input.dispatchKeyEvent', { type: 'keyUp', ...event }, sessionId)
}

async function waitForExpression(client, sessionId, expression, label) {
  const deadline = Date.now() + TEST_TIMEOUT_MS
  while (Date.now() < deadline) {
    if (await evaluate(client, sessionId, `Boolean(${expression})`)) return
    await delay(75)
  }
  const pageText = await evaluate(
    client,
    sessionId,
    `document.body?.innerText?.replace(/\\s+/g, ' ').slice(0, 1200) ?? '<no body>'`,
  )
  throw new Error(`Timed out waiting for ${label}. Page text: ${pageText}`)
}

async function waitForCondition(predicate, label) {
  const deadline = Date.now() + TEST_TIMEOUT_MS
  while (Date.now() < deadline) {
    if (predicate()) return
    await delay(75)
  }
  throw new Error(`Timed out waiting for ${label}`)
}

async function rejectConfirmation(client, sessionId, actionExpression, expectedMessage, label) {
  const dialogOpening = client.waitForEvent('Page.javascriptDialogOpening', { sessionId })
    .catch((error) => {
      throw new Error(`${label}: ${error.message}`)
    })
  const action = evaluate(client, sessionId, actionExpression)
  const dialog = await dialogOpening
  assert.match(dialog.message, expectedMessage)
  await client.send('Page.handleJavaScriptDialog', { accept: false }, sessionId)
  await action
}

async function acceptConfirmation(client, sessionId, actionExpression, expectedMessage, label) {
  const dialogOpening = client.waitForEvent('Page.javascriptDialogOpening', { sessionId })
    .catch((error) => {
      throw new Error(`${label}: ${error.message}`)
    })
  const action = evaluate(client, sessionId, actionExpression)
  const dialog = await dialogOpening
  assert.match(dialog.message, expectedMessage)
  await client.send('Page.handleJavaScriptDialog', { accept: true }, sessionId)
  await action
}

async function setTextareaValue(client, sessionId, value) {
  const actualValue = await evaluate(client, sessionId, `(() => {
    const textarea = document.querySelector('textarea[aria-label="查询知识库"]')
    if (!textarea) throw new Error('Query textarea not found')
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
    setter.call(textarea, ${JSON.stringify(value)})
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    return textarea.value
  })()`)
  assert.equal(actualValue, value)
}

async function setInputValue(client, sessionId, selector, value) {
  const actualValue = await evaluate(client, sessionId, `(() => {
    const input = document.querySelector(${JSON.stringify(selector)})
    if (!input) throw new Error('Input not found: ' + ${JSON.stringify(selector)})
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    setter.call(input, ${JSON.stringify(value)})
    input.dispatchEvent(new Event('input', { bubbles: true }))
    return input.value
  })()`)
  assert.equal(actualValue, value)
}

async function setFileInputFiles(client, sessionId, files) {
  const { root } = await client.send('DOM.getDocument', { depth: -1, pierce: true }, sessionId)
  const { nodeId } = await client.send('DOM.querySelector', {
    nodeId: root.nodeId,
    selector: 'input[type="file"]',
  }, sessionId)
  assert(nodeId, 'Upload file input not found')
  await client.send('DOM.setFileInputFiles', { files, nodeId }, sessionId)
}

async function runCompileJobLifecycleJourney(client, sessionId, fixtureServer) {
  fixtureServer.startCompileJobLifecycle()

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/compile`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('manifest-compile-active')
      && [...document.querySelectorAll('button')]
        .some((item) => item.textContent.trim() === '取消编译' && !item.disabled)`,
    'the recovered server-backed compile job',
  )

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/compile`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('manifest-compile-active')
      && [...document.querySelectorAll('button')]
        .some((item) => item.textContent.trim() === '取消编译' && !item.disabled)`,
    'the compile job after a page reload',
  )

  await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
    .find((item) => item.textContent.trim() === '取消编译' && !item.disabled).click())()`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('编译已取消')
      && ![...document.querySelectorAll('button')]
        .some((item) => item.textContent.trim() === '取消编译' && !item.disabled)`,
    'the cancelled compile job to settle',
  )

  fixtureServer.simulateCompileServiceRestart()
  await navigate(client, sessionId, `${fixtureServer.baseUrl}/compile`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('ServiceRestart: 编译服务在任务完成前退出')
      && [...document.querySelectorAll('button')]
        .some((item) => item.textContent.trim() === '重试任务' && !item.disabled)`,
    'the interrupted compile job after a service restart',
  )

  await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
    .find((item) => item.textContent.trim() === '重试任务' && !item.disabled).click())()`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('重试自 compile-')
      && document.body.textContent.includes('2 次尝试')
      && document.body.textContent.includes('已完成')`,
    'the linked retry to complete',
  )

  assert.deepEqual(
    fixtureServer.mutationRequests.map(
      ({ method, path: requestPath }) => `${method} ${requestPath}`,
    ),
    [
      'POST /api/v1/compile/jobs/compile-active/cancel',
      'POST /api/v1/compile/jobs/compile-interrupted/retry',
    ],
  )
  console.log('✓ Compile: reload recovery, interruption history, cancellation, and retry')
}

async function runFullJourney(client, sessionId, fixtureServer) {
  fixtureServer.startJourney()
  const uploadDirectory = await mkdtemp(path.join(os.tmpdir(), 'dochris-browser-journey-'))
  const uploadPath = path.join(uploadDirectory, 'browser-journey.md')

  try {
    await writeFile(uploadPath, [
      '# Dochris browser journey',
      '',
      'This isolated fixture covers upload, compile, streaming query, contribution, and promotion.',
    ].join('\n'))

    await navigate(client, sessionId, `${fixtureServer.baseUrl}/files`)
    await waitForExpression(
      client,
      sessionId,
      `document.querySelector('input[type="file"]')`,
      'the upload file input',
    )
    await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
      .find((item) => item.textContent.trim() === '上传文件').click())()`)
    await setFileInputFiles(client, sessionId, [uploadPath])
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('成功上传 1 个文件')
        && document.body.textContent.includes('browser-journey.md')`,
      'the uploaded journey manifest',
    )
    console.log('✓ Journey: isolated Markdown upload ingested one manifest')

    await navigate(client, sessionId, `${fixtureServer.baseUrl}/compile`)
    await waitForExpression(
      client,
      sessionId,
      `[...document.querySelectorAll('button')].some((item) => item.textContent.includes('开始编译') && !item.disabled)`,
      'the enabled compile action',
    )
    await evaluate(client, sessionId, `(() => {
      const button = [...document.querySelectorAll('button')]
        .find((item) => item.textContent.includes('开始编译') && !item.disabled)
      button.click()
    })()`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('编译完成：1 个成功')
        && document.body.textContent.includes('browser-journey.md')
        && document.body.textContent.includes('93')`,
      'the completed compile result',
    )
    console.log('✓ Journey: accepted compile completed through the polling UI')

    await navigate(client, sessionId, `${fixtureServer.baseUrl}/query`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('1 个已编译文档可查询')`,
      'one queryable compiled document',
    )
    await evaluate(client, sessionId, `(() => {
      const button = [...document.querySelectorAll('button')]
        .find((item) => item.textContent.includes('贡献模式'))
      button.click()
    })()`)

    const cancelledQuery = '取消这次隔离查询'
    await setTextareaValue(client, sessionId, cancelledQuery)
    await waitForExpression(
      client,
      sessionId,
      `[...document.querySelectorAll('button')]
        .some((item) => item.textContent.trim() === '查询' && !item.disabled)`,
      'the enabled query action',
    )
    await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
      .find((item) => item.textContent.trim() === '查询' && !item.disabled).click())()`)
    await waitForCondition(
      () => fixtureServer.telemetry.startedQueries.includes(cancelledQuery),
      'the cancellation query to reach the fixture',
    )
    await waitForExpression(
      client,
      sessionId,
      `[...document.querySelectorAll('button')].some((item) => item.textContent.trim() === '取消')`,
      'the query cancellation control',
    )
    await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
      .find((item) => item.textContent.trim() === '取消').click())()`)
    await waitForCondition(
      () => fixtureServer.telemetry.cancelledQueries.includes(cancelledQuery),
      'the aborted SSE connection',
    )
    await waitForExpression(
      client,
      sessionId,
      `![...document.querySelectorAll('button')].some((item) => item.textContent.trim() === '取消')`,
      'the cancelled query UI to settle',
    )
    assert.deepEqual(
      fixtureServer.mutationRequests.map(({ method, path: requestPath }) => `${method} ${requestPath}`),
      ['POST /api/v1/files/upload', 'POST /api/v1/compile'],
      'Cancelled query unexpectedly contributed a candidate',
    )
    console.log('✓ Journey: streaming query cancellation aborted transport and wrote no candidate')

    const timedOutQuery = '模拟 provider 超时'
    await setTextareaValue(client, sessionId, timedOutQuery)
    await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
      .find((item) => item.textContent.trim() === '查询' && !item.disabled).click())()`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('查询超时')
        && document.body.textContent.includes('模拟的 provider 总预算已耗尽')
        && document.body.textContent.includes('可重试')`,
      'the retryable provider timeout state',
    )
    assert.deepEqual(
      fixtureServer.mutationRequests.map(({ method, path: requestPath }) => `${method} ${requestPath}`),
      ['POST /api/v1/files/upload', 'POST /api/v1/compile'],
      'Timed-out query unexpectedly contributed a candidate',
    )
    console.log('✓ Journey: provider timeout surfaced a retryable error and wrote no candidate')

    const successfulQuery = 'Dochris 完整旅程如何工作？'
    await setTextareaValue(client, sessionId, successfulQuery)
    await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
      .find((item) => item.textContent.trim() === '查询' && !item.disabled).click())()`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('隔离浏览器完整旅程已经通过。')
        && document.body.textContent.includes('回答已写入候选区')
        && document.body.textContent.includes('candidate-journey')`,
      'the streamed answer and contribution receipt',
    )
    assert(fixtureServer.telemetry.completedQueries.includes(successfulQuery))
    console.log('✓ Journey: streamed answer persisted an isolated review candidate')

    await navigate(client, sessionId, `${fixtureServer.baseUrl}/candidates`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('${successfulQuery}')
        && [...document.querySelectorAll('button')].some((item) => item.textContent.trim() === '确认')`,
      'the generated candidate promotion action',
    )
    await acceptConfirmation(
      client,
      sessionId,
      `(() => [...document.querySelectorAll('button')]
        .find((item) => item.textContent.trim() === '确认').click())()`,
      /写入 wiki 摘要和概念文件/,
      'Journey candidate promotion',
    )
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('已晋升 candidate-journey')`,
      'the candidate promotion acknowledgement',
    )
    await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
      .find((item) => item.textContent.trim() === '已晋升').click())()`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('${successfulQuery}')
        && document.body.textContent.includes('candidate-journey')
        && document.body.textContent.includes('已晋升')`,
      'the promoted candidate filter result',
    )

    assert.deepEqual(
      fixtureServer.mutationRequests.map(({ method, path: requestPath }) => `${method} ${requestPath}`),
      [
        'POST /api/v1/files/upload',
        'POST /api/v1/compile',
        'POST /api/v1/query/contribution',
        'POST /api/v1/candidates/candidate-journey/promote',
      ],
    )
    assert.deepEqual(fixtureServer.telemetry.startedQueries, [cancelledQuery, timedOutQuery, successfulQuery])
    assert.deepEqual(fixtureServer.telemetry.cancelledQueries, [cancelledQuery])
    assert.deepEqual(fixtureServer.telemetry.timedOutQueries, [timedOutQuery])
    assert.deepEqual(fixtureServer.telemetry.completedQueries, [successfulQuery])
    console.log('✓ Journey: promoted candidate is visible under the promoted filter')
  } finally {
    await rm(uploadDirectory, { recursive: true, force: true })
  }
}

async function runAuthRecovery(client, sessionId, fixtureServer) {
  fixtureServer.startAuthRecovery()
  await evaluate(client, sessionId, `localStorage.removeItem('dochris_api_key')`)
  await navigate(client, sessionId, `${fixtureServer.baseUrl}/settings`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('认证失败')
      && document.body.textContent.includes('网关访问密钥')
      && document.body.textContent.includes('保存并重试')`,
    'the unauthorized settings recovery state',
  )
  const unauthorizedState = await evaluate(client, sessionId, `(() => ({
    exactRetryButtons: [...document.querySelectorAll('button')]
      .filter((item) => item.textContent.trim() === '重试').length,
    exposesConfig: document.body.textContent.includes('API 配置'),
  }))()`)
  assert.deepEqual(unauthorizedState, { exactRetryButtons: 0, exposesConfig: false })

  await setInputValue(client, sessionId, 'input[type="password"]', BROWSER_E2E_ACCESS_KEY)
  await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
    .find((item) => item.textContent.trim() === '保存并重试').click())()`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('访问密钥已保存，连接成功')
      && document.body.textContent.includes('API 配置')`,
    'the authenticated settings recovery',
  )
  assert.equal(
    await evaluate(client, sessionId, `localStorage.getItem('dochris_api_key')`),
    BROWSER_E2E_ACCESS_KEY,
  )
  // AppLayout 侧栏版本号与 SettingsPage 空库检查都会探测 /api/v1/status：
  // [AppLayout 401, 配置加载 401, 保存密钥后已认证重载]
  assert.deepEqual(
    fixtureServer.telemetry.authFailures,
    ['/api/v1/status', '/api/v1/config', '/api/v1/status'],
  )
  assert.deepEqual(
    fixtureServer.telemetry.authenticatedRequests,
    ['/api/v1/status', '/api/v1/config'],
  )
  assert.deepEqual(fixtureServer.mutationRequests, [])
  console.log('✓ Recovery: 401 settings state accepted a local access key and reloaded config')
}

async function runOfflineRecovery(client, sessionId, fixtureServer) {
  fixtureServer.startOfflineRecovery()
  await navigate(client, sessionId, `${fixtureServer.baseUrl}/files`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('无法连接后端服务')
      && [...document.querySelectorAll('button')]
        .some((item) => item.textContent.trim() === '重试')`,
    'the offline files recovery state',
  )
  assert.equal(
    await evaluate(client, sessionId, `document.body.textContent.includes('暂无文件')`),
    false,
    'Offline state was incorrectly rendered as an empty knowledge base',
  )
  fixtureServer.restoreNetwork()
  await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
    .find((item) => item.textContent.trim() === '重试').click())()`)
  await waitForExpression(
    client,
    sessionId,
    `document.querySelector('tr[aria-label="查看 高质量文档.md 详情"]')`,
    'the recovered Files page fixture row',
  )
  assert(fixtureServer.telemetry.networkDrops.length >= 1)
  assert(fixtureServer.telemetry.networkDrops.every((requestPath) => requestPath === '/api/v1/manifests'))
  assert.deepEqual(fixtureServer.mutationRequests, [])
  console.log('✓ Recovery: dropped manifest request showed an offline state and retry restored data')
}

async function setViewport(client, sessionId, width, height = 900) {
  await client.send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width <= 768,
    screenWidth: width,
    screenHeight: height,
  }, sessionId)
  await evaluate(client, sessionId, `window.dispatchEvent(new Event('resize'))`)
}

async function runEmptyWorkspaceJourney(client, sessionId, fixtureServer) {
  fixtureServer.startEmptyWorkspace()
  await evaluate(client, sessionId, `localStorage.removeItem('dochris_api_key')`)

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('总文件')
      && document.body.textContent.includes('上传文件')`,
    'the empty dashboard quick start actions',
  )

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/files`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('暂无文件')
      && [...document.querySelectorAll('button')].some((item) => item.textContent.includes('上传文件'))`,
    'the empty Files first-start state',
  )

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/compile`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('暂无文件，请先在文件管理页面上传文件')`,
    'the empty Compile first-start state',
  )
  const emptyCompileActions = await evaluate(client, sessionId, `(() => {
    const buttons = [...document.querySelectorAll('button')]
    const compile = buttons.find((item) => item.textContent.trim() === '开始编译')
    const recompile = buttons.find((item) => item.textContent.trim() === '重编译过时')
    return {
      compile: { exists: Boolean(compile), disabled: compile?.disabled ?? false },
      recompile: { exists: Boolean(recompile), disabled: recompile?.disabled ?? false },
    }
  })()`)

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/query`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('暂无已编译文档，请先前往文件编译页')
      && document.body.textContent.includes('知识库为空')`,
    'the empty Query first-start state',
  )
  const emptyQueryAction = await evaluate(client, sessionId, `(() => {
    const query = [...document.querySelectorAll('button')]
      .find((item) => item.textContent.trim() === '查询')
    return { exists: Boolean(query), disabled: query?.disabled ?? false }
  })()`)

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/candidates`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('暂无候选知识')`,
    'the empty Candidates state',
  )

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/quality`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('暂无质量评分')`,
    'the empty Quality state',
  )
  const emptyQualityAction = await evaluate(client, sessionId, `(() => {
    const reset = [...document.querySelectorAll('button')]
      .find((item) => item.textContent.includes('重置低质量 (0)'))
    return { exists: Boolean(reset), disabled: reset?.disabled ?? false }
  })()`)

  await navigate(client, sessionId, `${fixtureServer.baseUrl}/graph`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('知识图谱为空')
      || document.body.textContent.includes('节点 0')`,
    'the empty Graph response',
  )
  const emptyGraphState = await evaluate(client, sessionId, `(() => ({
    guidance: document.body.textContent.includes('知识图谱为空'),
    rendersGraphWorkspace: Boolean(document.querySelector('input[placeholder="搜索概念或文档..."]')),
  }))()`)

  assert.deepEqual(emptyCompileActions, {
    compile: { exists: true, disabled: true },
    recompile: { exists: true, disabled: true },
  })
  assert.deepEqual(emptyQueryAction, { exists: true, disabled: true })
  assert.deepEqual(emptyQualityAction, { exists: true, disabled: true })
  assert.deepEqual(emptyGraphState, { guidance: true, rendersGraphWorkspace: false })
  assert.deepEqual(fixtureServer.mutationRequests, [])
  console.log('✓ First start: empty workspace guides each core workflow and disables no-op writes')
}

async function runLargeGraphDetailJourney(client, sessionId, fixtureServer) {
  fixtureServer.startLargeGraph()
  await evaluate(client, sessionId, `localStorage.removeItem('dochris_api_key')`)

  try {
    await setViewport(client, sessionId, 375)
    await navigate(client, sessionId, `${fixtureServer.baseUrl}/graph`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('节点 120')
        && document.querySelectorAll('svg g.nodes > g').length >= 80`,
      'the large concept graph',
    )
    await evaluate(client, sessionId, `(() => {
      const node = [...document.querySelectorAll('svg g.nodes > g')]
        .find((item) => item.__data__?.id === 'concept-large-0')
      if (!node) throw new Error('Large graph target node was not rendered')
      node.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })()`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('移动端节点详情需要完整可见且可以安全关闭')
        && document.body.textContent.includes('关联节点 (2)')`,
      'the mobile graph node detail panel',
    )

    const detailLayout = await evaluate(client, sessionId, `(() => {
      const title = [...document.querySelectorAll('div')]
        .find((item) => item.children.length === 0
          && item.textContent.trim() === '移动端节点详情需要完整可见且可以安全关闭')
      const panel = document.querySelector('[aria-label="节点详情"]')
        || title?.parentElement?.parentElement?.parentElement
      if (!panel) throw new Error('Graph detail panel was not found')
      const close = panel.querySelector('button')
      const rect = panel.getBoundingClientRect()
      return {
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
        viewport: window.innerWidth,
        closeLabel: close?.getAttribute('aria-label') ?? null,
        documentWidth: document.documentElement.scrollWidth,
      }
    })()`)
    assert(detailLayout.left >= 0, `Graph detail starts outside viewport: ${JSON.stringify(detailLayout)}`)
    assert(detailLayout.right <= detailLayout.viewport + 1, `Graph detail ends outside viewport: ${JSON.stringify(detailLayout)}`)
    assert(detailLayout.width <= detailLayout.viewport - 24, `Graph detail is too wide: ${JSON.stringify(detailLayout)}`)
    assert.equal(detailLayout.closeLabel, '关闭节点详情')
    assert(detailLayout.documentWidth <= detailLayout.viewport + 1)

    await evaluate(client, sessionId, `document.querySelector('button[aria-label="关闭节点详情"]').click()`)
    await waitForExpression(
      client,
      sessionId,
      `!document.querySelector('[aria-label="节点详情"]')`,
      'the closed graph node detail panel',
    )
    assert.deepEqual(fixtureServer.mutationRequests, [])
    console.log('✓ Graph scale: 120-node graph opens and closes a fully visible mobile detail panel')
  } finally {
    await client.send('Emulation.clearDeviceMetricsOverride', {}, sessionId)
  }
}

async function runKeyboardOnlyJourney(client, sessionId, fixtureServer) {
  fixtureServer.startLargeGraph()
  await evaluate(client, sessionId, `localStorage.removeItem('dochris_api_key')`)
  await navigate(client, sessionId, `${fixtureServer.baseUrl}/graph`)
  await waitForExpression(
    client,
    sessionId,
    `document.querySelectorAll('svg g.nodes > g').length >= 80`,
    'the keyboard graph fixture',
  )
  await evaluate(client, sessionId, `(() => {
    const page = document.querySelector('.page-container')
    page.setAttribute('tabindex', '-1')
    page.focus()
  })()`)

  const focusTrail = []
  let focusedNode = null
  for (let index = 0; index < 60; index += 1) {
    await pressKey(client, sessionId, 'Tab')
    const active = await evaluate(client, sessionId, `(() => ({
      tag: document.activeElement?.tagName ?? null,
      text: document.activeElement?.textContent?.trim().slice(0, 40) ?? '',
      role: document.activeElement?.getAttribute('role') ?? null,
      label: document.activeElement?.getAttribute('aria-label') ?? null,
      nodeId: document.activeElement?.__data__?.id ?? null,
    }))()`)
    focusTrail.push(active)
    if (active.nodeId) {
      focusedNode = active
      break
    }
  }
  assert(focusedNode, `Tab never reached a graph node: ${JSON.stringify(focusTrail)}`)
  assert.equal(focusedNode.role, 'button')
  assert.match(focusedNode.label, /概念|文档|摘要/)

  await pressKey(client, sessionId, 'Enter')
  await waitForExpression(
    client,
    sessionId,
    `document.activeElement?.getAttribute('aria-label') === '关闭节点详情'
      && document.querySelector('[aria-label="节点详情"]')`,
    'keyboard focus in the graph detail panel',
  )
  await pressKey(client, sessionId, 'Escape')
  await waitForExpression(
    client,
    sessionId,
    `!document.querySelector('[aria-label="节点详情"]')
      && document.activeElement?.__data__?.id === '${focusedNode.nodeId}'`,
    'keyboard graph detail close and focus restoration',
  )

  assert.deepEqual(fixtureServer.mutationRequests, [])
  console.log('✓ Keyboard: Tab, Enter, and Escape operate Graph detail with focus restoration')
}

async function runMobileNavigationKeyboardJourney(client, sessionId, fixtureServer) {
  fixtureServer.startResponsive()
  await evaluate(client, sessionId, `localStorage.removeItem('dochris_api_key')`)

  try {
    await setViewport(client, sessionId, 375)
    await navigate(client, sessionId, `${fixtureServer.baseUrl}/`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('仪表盘')
        && getComputedStyle(document.querySelector('.mobile-header')).display !== 'none'`,
      'the mobile dashboard shell',
    )
    await evaluate(client, sessionId, `(() => {
      document.body.setAttribute('tabindex', '-1')
      document.body.focus()
    })()`)

    await pressKey(client, sessionId, 'Tab')
    const initialFocus = await evaluate(client, sessionId, `(() => {
      const active = document.activeElement
      const rect = active?.getBoundingClientRect()
      return {
        label: active?.getAttribute('aria-label') ?? null,
        visible: Boolean(rect && rect.width > 0 && rect.height > 0
          && rect.right > 0 && rect.left < window.innerWidth
          && rect.bottom > 0 && rect.top < window.innerHeight),
      }
    })()`)
    assert.deepEqual(initialFocus, { label: '打开导航菜单', visible: true })

    await pressKey(client, sessionId, 'Enter')
    await waitForExpression(
      client,
      sessionId,
      `document.querySelector('.sidebar-mobile').getBoundingClientRect().left >= -1
        && document.activeElement?.getAttribute('aria-label') === '关闭导航菜单'`,
      'keyboard-opened mobile navigation',
    )
    const openContract = await evaluate(client, sessionId, `(() => {
      const sidebar = document.querySelector('.sidebar-mobile')
      return {
        role: sidebar.getAttribute('role'),
        modal: sidebar.getAttribute('aria-modal'),
        hidden: sidebar.getAttribute('aria-hidden'),
        mainInert: document.querySelector('main').inert,
      }
    })()`)
    assert.deepEqual(openContract, {
      role: 'dialog',
      modal: 'true',
      hidden: 'false',
      mainInert: true,
    })

    await pressKey(client, sessionId, 'Tab', { shift: true })
    const backwardTrap = await evaluate(
      client,
      sessionId,
      `document.querySelector('.sidebar-mobile').contains(document.activeElement)`,
    )
    assert.equal(backwardTrap, true)

    await evaluate(client, sessionId, `(() => {
      const sidebar = document.querySelector('.sidebar-mobile')
      const focusable = [...sidebar.querySelectorAll('button:not([disabled]), a[href]')]
      focusable.at(-1).focus()
    })()`)
    await pressKey(client, sessionId, 'Tab')
    const forwardTrap = await evaluate(
      client,
      sessionId,
      `document.activeElement?.getAttribute('aria-label') === '关闭导航菜单'`,
    )
    assert.equal(forwardTrap, true)

    await pressKey(client, sessionId, 'Escape')
    await waitForExpression(
      client,
      sessionId,
      `document.querySelector('.sidebar-mobile').getBoundingClientRect().right <= 1
        && document.activeElement?.getAttribute('aria-label') === '打开导航菜单'`,
      'closed mobile navigation with restored focus',
    )
    const closedContract = await evaluate(client, sessionId, `(() => {
      const sidebar = document.querySelector('.sidebar-mobile')
      return {
        hidden: sidebar.getAttribute('aria-hidden'),
        inert: sidebar.inert,
        mainInert: document.querySelector('main').inert,
      }
    })()`)
    assert.deepEqual(closedContract, { hidden: 'true', inert: true, mainInert: false })
    assert.deepEqual(fixtureServer.mutationRequests, [])
    console.log('✓ Keyboard: mobile navigation excludes hidden controls, traps focus, and restores the opener')
  } finally {
    await client.send('Emulation.clearDeviceMetricsOverride', {}, sessionId)
  }
}

async function runCrossPageKeyboardJourney(client, sessionId, fixtureServer) {
  fixtureServer.startResponsive()
  await evaluate(client, sessionId, `(() => {
    localStorage.removeItem('dochris_api_key')
    localStorage.removeItem('dochris-query-history')
    localStorage.removeItem('dochris-query-favorites')
  })()`)

  try {
    await setViewport(client, sessionId, 1024)
    await navigate(client, sessionId, `${fixtureServer.baseUrl}/`)
    await waitForExpression(
      client,
      sessionId,
      `document.body.textContent.includes('数据概览')`,
      'the keyboard dashboard fixture',
    )
    await evaluate(client, sessionId, `(() => {
      document.body.setAttribute('tabindex', '-1')
      document.body.focus()
    })()`)

    await pressKey(client, sessionId, 'Tab')
    assert.equal(
      await evaluate(client, sessionId, `document.activeElement?.getAttribute('href')`),
      '/',
    )
    await pressKey(client, sessionId, 'Tab')
    assert.equal(
      await evaluate(client, sessionId, `document.activeElement?.getAttribute('href')`),
      '/files',
    )
    await pressKey(client, sessionId, 'Enter')
    await waitForExpression(
      client,
      sessionId,
      `location.pathname === '/files'
        && document.activeElement?.tagName === 'H1'
        && document.activeElement?.textContent.includes('文件管理')`,
      'keyboard navigation from Dashboard to Files',
    )

    const keyboardRoutes = [
      { path: '/compile', heading: '编译控制', ready: `document.body.textContent.includes('编译概览')` },
      { path: '/candidates', heading: '候选知识管理', ready: `document.body.textContent.includes('候选知识管理')` },
      { path: '/quality', heading: '质量监控', ready: `document.body.textContent.includes('质量概览')` },
      { path: '/graph', heading: '知识图谱', ready: `document.body.textContent.includes('知识图谱')` },
      { path: '/status', heading: '系统状态', ready: `document.body.textContent.includes('系统信息')` },
      { path: '/settings', heading: '系统设置', ready: `document.body.textContent.includes('API 配置')` },
      { path: '/', heading: '仪表盘', ready: `document.body.textContent.includes('数据概览')` },
      { path: '/query', heading: '知识查询', ready: `document.body.textContent.includes('2 个已编译文档可查询')` },
    ]

    for (const route of keyboardRoutes) {
      const navigationFocusTrail = []
      let reachedNavigationLink = false
      for (let index = 0; index < 12; index += 1) {
        await pressKey(client, sessionId, 'Tab', { shift: true })
        const active = await evaluate(client, sessionId, `(() => ({
          tag: document.activeElement?.tagName ?? null,
          href: document.activeElement?.getAttribute('href') ?? null,
          label: document.activeElement?.getAttribute('aria-label') ?? null,
          text: document.activeElement?.textContent?.trim().slice(0, 30) ?? '',
        }))()`)
        navigationFocusTrail.push(active)
        if (active.href === route.path) {
          reachedNavigationLink = true
          break
        }
      }
      assert(
        reachedNavigationLink,
        `Tab did not reach ${route.path}: ${JSON.stringify(navigationFocusTrail)}`,
      )
      await pressKey(client, sessionId, 'Enter')
      await waitForExpression(
        client,
        sessionId,
        `location.pathname === ${JSON.stringify(route.path)}
          && document.activeElement?.tagName === 'H1'
          && document.activeElement?.textContent.includes(${JSON.stringify(route.heading)})
          && ${route.ready}`,
        `keyboard navigation to ${route.path}`,
      )
    }

    let reachedQueryInput = false
    const focusTrail = []
    for (let index = 0; index < 12; index += 1) {
      await pressKey(client, sessionId, 'Tab')
      const active = await evaluate(client, sessionId, `(() => ({
        tag: document.activeElement?.tagName ?? null,
        href: document.activeElement?.getAttribute('href') ?? null,
        label: document.activeElement?.getAttribute('aria-label') ?? null,
        text: document.activeElement?.textContent?.trim().slice(0, 30) ?? '',
      }))()`)
      focusTrail.push(active)
      if (active.label === '查询知识库') {
        reachedQueryInput = true
        break
      }
    }
    assert(reachedQueryInput, `Tab did not reach the Query input: ${JSON.stringify(focusTrail)}`)
    assert.deepEqual(fixtureServer.mutationRequests, [])
    console.log('✓ Keyboard: all nine pages and the Query input work without pointer input')
  } finally {
    await client.send('Emulation.clearDeviceMetricsOverride', {}, sessionId)
  }
}

async function runQueryModeKeyboardJourney(client, sessionId, fixtureServer) {
  fixtureServer.startResponsive()
  await evaluate(client, sessionId, `localStorage.removeItem('dochris_api_key')`)
  await navigate(client, sessionId, `${fixtureServer.baseUrl}/query`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('2 个已编译文档可查询')`,
    'the keyboard query mode fixture',
  )

  const initialContract = await evaluate(client, sessionId, `(() => {
    const trigger = document.querySelector('button[aria-controls="query-mode-listbox"]')
    trigger?.focus()
    return {
      exists: Boolean(trigger),
      popup: trigger?.getAttribute('aria-haspopup') ?? null,
      expanded: trigger?.getAttribute('aria-expanded') ?? null,
      label: trigger?.getAttribute('aria-label') ?? null,
    }
  })()`)
  assert.deepEqual(initialContract, {
    exists: true,
    popup: 'listbox',
    expanded: 'false',
    label: '选择查询模式，当前综合',
  })

  await pressKey(client, sessionId, 'Enter')
  await waitForExpression(
    client,
    sessionId,
    `document.activeElement?.getAttribute('role') === 'option'
      && document.activeElement?.getAttribute('aria-selected') === 'true'`,
    'the opened query mode listbox',
  )
  assert.equal(
    await evaluate(client, sessionId, `document.activeElement?.textContent.includes('综合')`),
    true,
  )

  await pressKey(client, sessionId, 'ArrowDown')
  assert.equal(
    await evaluate(client, sessionId, `document.activeElement?.textContent.includes('概念')`),
    true,
  )
  await pressKey(client, sessionId, 'Enter')
  await waitForExpression(
    client,
    sessionId,
    `document.querySelector('button[aria-controls="query-mode-listbox"]')
        ?.getAttribute('aria-expanded') === 'false'
      && document.activeElement?.getAttribute('aria-controls') === 'query-mode-listbox'`,
    'the selected query mode and restored trigger focus',
  )
  assert.equal(
    await evaluate(client, sessionId, `document.activeElement?.textContent.includes('概念')`),
    true,
  )

  await pressKey(client, sessionId, 'Enter')
  await waitForExpression(
    client,
    sessionId,
    `document.activeElement?.getAttribute('role') === 'option'`,
    'the reopened query mode listbox',
  )
  await pressKey(client, sessionId, 'Escape')
  await waitForExpression(
    client,
    sessionId,
    `document.querySelector('button[aria-controls="query-mode-listbox"]')
        ?.getAttribute('aria-expanded') === 'false'
      && document.activeElement?.getAttribute('aria-controls') === 'query-mode-listbox'`,
    'the escaped query mode listbox',
  )
  assert.deepEqual(fixtureServer.mutationRequests, [])
  console.log('✓ Keyboard: Query mode listbox supports Enter, arrows, Escape, and focus restoration')
}

async function runQuerySavedItemsKeyboardJourney(client, sessionId, fixtureServer) {
  fixtureServer.startResponsive()
  await evaluate(client, sessionId, `(() => {
    localStorage.removeItem('dochris_api_key')
    localStorage.setItem('dochris-query-history', JSON.stringify([{
      query: '键盘历史问题',
      mode: 'combined',
      timestamp: 1788192000000,
      answerPreview: '历史回答预览',
    }]))
    localStorage.setItem('dochris-query-favorites', JSON.stringify([{
      query: '键盘收藏问题',
      mode: 'combined',
      answer: '收藏回答',
      timestamp: 1788192001000,
    }]))
  })()`)
  await navigate(client, sessionId, `${fixtureServer.baseUrl}/query`)
  await waitForExpression(
    client,
    sessionId,
    `document.body.textContent.includes('2 个已编译文档可查询')`,
    'the keyboard query history fixture',
  )
  await evaluate(client, sessionId, `(() => {
    const trigger = [...document.querySelectorAll('button')]
      .find((item) => item.textContent.includes('查询历史'))
    trigger?.click()
  })()`)

  const savedItemContract = await evaluate(client, sessionId, `(() => ({
    history: Boolean(document.querySelector('button[aria-label="重新运行历史查询：键盘历史问题"]')),
    favorite: Boolean(document.querySelector('button[aria-label="运行收藏查询：键盘收藏问题"]')),
  }))()`)
  assert.deepEqual(savedItemContract, { history: true, favorite: true })

  await evaluate(
    client,
    sessionId,
    `document.querySelector('button[aria-label="重新运行历史查询：键盘历史问题"]').focus()`,
  )
  await pressKey(client, sessionId, 'Enter')
  await waitForCondition(
    () => fixtureServer.telemetry.completedQueries.includes('键盘历史问题'),
    'the keyboard-triggered history query',
  )

  await evaluate(
    client,
    sessionId,
    `document.querySelector('button[aria-label="运行收藏查询：键盘收藏问题"]').focus()`,
  )
  await pressKey(client, sessionId, 'Enter')
  await waitForCondition(
    () => fixtureServer.telemetry.completedQueries.includes('键盘收藏问题'),
    'the keyboard-triggered favorite query',
  )

  assert.deepEqual(fixtureServer.mutationRequests, [])
  console.log('✓ Keyboard: Query history and favorites are named buttons operable with Enter')
}

async function runAccessibleNameAudit(client, sessionId, fixtureServer) {
  fixtureServer.startResponsive()
  await evaluate(client, sessionId, `localStorage.removeItem('dochris_api_key')`)
  const routes = [
    { path: '/', ready: `document.body.textContent.includes('数据概览')` },
    { path: '/files', ready: `document.body.textContent.includes('文件管理')` },
    { path: '/compile', ready: `document.body.textContent.includes('编译控制')` },
    { path: '/query', ready: `document.body.textContent.includes('2 个已编译文档可查询')` },
    { path: '/candidates', ready: `document.body.textContent.includes('候选知识')` },
    { path: '/quality', ready: `document.body.textContent.includes('质量监控')` },
    { path: '/graph', ready: `document.body.textContent.includes('知识图谱')` },
    { path: '/status', ready: `document.body.textContent.includes('系统状态')` },
    { path: '/settings', ready: `document.body.textContent.includes('API 配置')` },
  ]
  const violations = []

  try {
    for (const width of [1024, 375]) {
      await setViewport(client, sessionId, width)
      for (const route of routes) {
        await navigate(client, sessionId, `${fixtureServer.baseUrl}${route.path}`)
        await waitForExpression(client, sessionId, route.ready, `${route.path} accessibility audit at ${width}px`)
        const unnamedButtons = await evaluate(client, sessionId, `(() => [...document.querySelectorAll('button')]
          .filter((button) => {
            const rect = button.getBoundingClientRect()
            const style = getComputedStyle(button)
            return rect.width > 0 && rect.height > 0
              && rect.right > 0 && rect.left < window.innerWidth
              && rect.bottom > 0 && rect.top < window.innerHeight
              && style.visibility !== 'hidden' && style.display !== 'none'
          })
          .filter((button) => {
            const labelledBy = button.getAttribute('aria-labelledby')
            const labelledText = labelledBy
              ? document.getElementById(labelledBy)?.textContent?.trim()
              : ''
            return !button.getAttribute('aria-label')
              && !button.getAttribute('title')
              && !button.textContent.trim()
              && !labelledText
          })
          .map((button) => ({
            html: button.outerHTML.slice(0, 240),
            className: button.className,
          })))()`)
        if (unnamedButtons.length > 0) {
          violations.push({ width, route: route.path, buttons: unnamedButtons })
        }
      }
    }
    assert.deepEqual(violations, [], `Visible unnamed buttons: ${JSON.stringify(violations)}`)
    assert.deepEqual(fixtureServer.mutationRequests, [])
    console.log('✓ Accessibility: all visible buttons have names across nine pages at 1024px and 375px')
  } finally {
    await client.send('Emulation.clearDeviceMetricsOverride', {}, sessionId)
  }
}

async function assertResponsiveShell(client, sessionId, width, route) {
  const shell = await evaluate(client, sessionId, `(() => {
    const desktop = document.querySelector('.sidebar-desktop')
    const mobileHeader = document.querySelector('.mobile-header')
    const page = document.querySelector('.page-container')
    const pageRect = page?.getBoundingClientRect()
    return {
      innerWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      desktopDisplay: getComputedStyle(desktop).display,
      mobileHeaderDisplay: getComputedStyle(mobileHeader).display,
      pageLeft: pageRect?.left ?? null,
      pageRight: pageRect?.right ?? null,
    }
  })()`)
  assert.equal(shell.innerWidth, width)
  assert(shell.documentWidth <= width + 1, `${route} at ${width}px overflows document to ${shell.documentWidth}px`)
  assert(shell.bodyWidth <= width + 1, `${route} at ${width}px overflows body to ${shell.bodyWidth}px`)
  assert(shell.pageLeft !== null && shell.pageLeft >= -1, `${route} page starts outside ${width}px viewport`)
  assert(shell.pageRight !== null && shell.pageRight <= width + 1, `${route} page ends outside ${width}px viewport`)

  if (width <= 768) {
    assert.equal(shell.desktopDisplay, 'none')
    assert.notEqual(shell.mobileHeaderDisplay, 'none')
  } else {
    assert.notEqual(shell.desktopDisplay, 'none')
    assert.equal(shell.mobileHeaderDisplay, 'none')
  }
}

async function assertMobileMenu(client, sessionId) {
  await evaluate(client, sessionId, `document.querySelector('.mobile-header button').click()`)
  await waitForExpression(
    client,
    sessionId,
    `document.querySelector('.sidebar-mobile').getBoundingClientRect().left >= -1`,
    'the opened mobile navigation',
  )
  await evaluate(client, sessionId, `document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`)
  await waitForExpression(
    client,
    sessionId,
    `document.querySelector('.sidebar-mobile').getBoundingClientRect().right <= 1`,
    'the closed mobile navigation',
  )
}

async function runResponsiveCoverage(client, sessionId, fixtureServer) {
  fixtureServer.startResponsive()
  await evaluate(client, sessionId, `localStorage.removeItem('dochris_api_key')`)
  const routes = [
    { path: '/files', ready: `document.querySelector('tr[aria-label="查看 高质量文档.md 详情"]')` },
    { path: '/compile', ready: `document.body.textContent.includes('编译控制')` },
    { path: '/query', ready: `document.body.textContent.includes('2 个已编译文档可查询')` },
    { path: '/settings', ready: `document.body.textContent.includes('API 配置')` },
    { path: '/graph', ready: `document.querySelector('input[placeholder="搜索概念或文档..."]')` },
  ]

  try {
    for (const width of [1024, 768, 375]) {
      await setViewport(client, sessionId, width)
      for (const route of routes) {
        await navigate(client, sessionId, `${fixtureServer.baseUrl}${route.path}`)
        await waitForExpression(client, sessionId, route.ready, `${route.path} at ${width}px`)
        await assertResponsiveShell(client, sessionId, width, route.path)

        if (route.path === '/graph') {
          const graphOverlay = await evaluate(client, sessionId, `(() => {
            const search = document.querySelector('input[placeholder="搜索概念或文档..."]')
              .closest('div').parentElement.getBoundingClientRect()
            const mode = [...document.querySelectorAll('button')]
              .find((item) => item.textContent.trim() === '概念视图')
              .parentElement.getBoundingClientRect()
            const overlaps = !(search.right <= mode.left || mode.right <= search.left
              || search.bottom <= mode.top || mode.bottom <= search.top)
            return { overlaps, search: { left: search.left, right: search.right }, mode: { left: mode.left, right: mode.right } }
          })()`)
          assert.equal(
            graphOverlay.overlaps,
            false,
            `Graph overlays collide at ${width}px: ${JSON.stringify(graphOverlay)}`,
          )
        }
      }
      if (width <= 768) await assertMobileMenu(client, sessionId)
      console.log(`✓ Responsive: core pages fit and navigation works at ${width}px`)
    }
  } finally {
    await client.send('Emulation.clearDeviceMetricsOverride', {}, sessionId)
  }

  assert.deepEqual(fixtureServer.mutationRequests, [])
}

async function runSmokeSuite(fixtureServer) {
  const { baseUrl, mutationRequests } = fixtureServer
  const chrome = await launchChrome()
  const client = new DevToolsClient(chrome.webSocketUrl)
  const browserExceptions = []

  try {
    const sessionId = await createBrowserSession(client)
    client.on('Runtime.exceptionThrown', (event, eventSessionId) => {
      if (eventSessionId === sessionId) browserExceptions.push(event.exceptionDetails?.text ?? 'Unknown exception')
    })

    await navigate(client, sessionId, `${baseUrl}/files`)
    await waitForExpression(
      client,
      sessionId,
      `document.querySelector('tr[aria-label="查看 高质量文档.md 详情"]')`,
      'the Files page fixture row',
    )

    const failedResetState = await evaluate(client, sessionId, `(() => {
      const button = [...document.querySelectorAll('button')].find((item) => item.textContent.includes('重置失败 (0)'))
      return { exists: Boolean(button), disabled: button?.disabled ?? false }
    })()`)
    assert.deepEqual(failedResetState, { exists: true, disabled: true })

    await evaluate(client, sessionId, `(() => {
      const row = document.querySelector('tr[aria-label="查看 高质量文档.md 详情"]')
      row.focus()
      row.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    })()`)
    await waitForExpression(client, sessionId, `document.querySelector('[role="dialog"]')`, 'the file details dialog')

    const dialogState = await evaluate(client, sessionId, `(() => {
      const dialog = document.querySelector('[role="dialog"]')
      const description = document.getElementById(dialog.getAttribute('aria-describedby'))
      return {
        ariaModal: dialog.getAttribute('aria-modal'),
        labelledBy: dialog.getAttribute('aria-labelledby'),
        description: description?.textContent.trim(),
        activeLabel: document.activeElement?.getAttribute('aria-label'),
      }
    })()`)
    assert.equal(dialogState.ariaModal, 'true')
    assert.equal(dialogState.labelledBy, 'file-details-title')
    assert.match(dialogState.description, /按 Escape 关闭并返回文件列表/)
    assert.equal(dialogState.activeLabel, '关闭文件详情')

    await pressKey(client, sessionId, 'Tab')
    const forwardTrap = await evaluate(
      client,
      sessionId,
      `document.querySelector('[role="dialog"]').contains(document.activeElement)`,
    )
    await evaluate(client, sessionId, `document.querySelector('button[aria-label="关闭文件详情"]').focus()`)
    await pressKey(client, sessionId, 'Tab', { shift: true })
    const backwardTrap = await evaluate(
      client,
      sessionId,
      `document.querySelector('[role="dialog"]').contains(document.activeElement)`,
    )
    assert.deepEqual({ forwardTrap, backwardTrap }, { forwardTrap: true, backwardTrap: true })

    await evaluate(client, sessionId, `document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`)
    await waitForExpression(client, sessionId, `!document.querySelector('[role="dialog"]')`, 'the file details dialog to close')
    const restoredFocus = await evaluate(client, sessionId, `document.activeElement?.getAttribute('aria-label')`)
    assert.equal(restoredFocus, '查看 高质量文档.md 详情')
    console.log('✓ Files: disabled reset state and keyboard-accessible dialog contract')

    await navigate(client, sessionId, `${baseUrl}/quality`)
    await waitForExpression(
      client,
      sessionId,
      `[...document.querySelectorAll('button')].some((item) => item.textContent.includes('重置低质量 (1)'))`,
      'the low-quality reset action',
    )
    const lowQualityResetEnabled = await evaluate(client, sessionId, `(() => {
      const button = [...document.querySelectorAll('button')].find((item) => item.textContent.includes('重置低质量 (1)'))
      return Boolean(button && !button.disabled)
    })()`)
    assert.equal(lowQualityResetEnabled, true)
    await rejectConfirmation(
      client,
      sessionId,
      `(() => [...document.querySelectorAll('button')].find((item) => item.textContent.includes('重置低质量 (1)')).click())()`,
      /将 1 个低于 85 分的文件重置为待编译状态/,
      'Quality low-score reset',
    )
    console.log('✓ Quality: exact reset count/threshold warning and safe cancellation')

    await navigate(client, sessionId, `${baseUrl}/settings`)
    await waitForExpression(
      client,
      sessionId,
      `[...document.querySelectorAll('button')].some((item) => item.textContent.includes('从图谱丰富元数据'))`,
      'the schema enrichment action',
    )
    await rejectConfirmation(
      client,
      sessionId,
      `(() => [...document.querySelectorAll('button')].find((item) => item.textContent.includes('从图谱丰富元数据')).click())()`,
      /批量写回 manifest 关系元数据/,
      'Settings schema enrichment',
    )
    console.log('✓ Settings: schema mutation warning and safe cancellation')

    await navigate(client, sessionId, `${baseUrl}/candidates`)
    await waitForExpression(
      client,
      sessionId,
      `[...document.querySelectorAll('button')].some((item) => item.textContent.trim() === '确认')`,
      'the candidate promotion action',
    )
    const candidateActions = await evaluate(client, sessionId, `[...document.querySelectorAll('button')]
      .map((item) => item.textContent.trim())
      .filter((text) => text === '确认' || text === '丢弃')`)
    assert.deepEqual(candidateActions, ['确认', '丢弃'])
    await rejectConfirmation(
      client,
      sessionId,
      `(() => [...document.querySelectorAll('button')].find((item) => item.textContent.trim() === '确认').click())()`,
      /写入 wiki 摘要和概念文件/,
      'Candidate promotion',
    )
    await rejectConfirmation(
      client,
      sessionId,
      `(() => [...document.querySelectorAll('button')].find((item) => item.textContent.trim() === '丢弃').click())()`,
      /候选内容文件会被永久删除/,
      'Candidate discard',
    )
    console.log('✓ Candidates: promotion/deletion impact warnings and safe cancellation')

    await navigate(client, sessionId, `${baseUrl}/compile`)
    await waitForExpression(
      client,
      sessionId,
      `document.querySelector('button[aria-label="晋升 高质量文档.md 到 Wiki"]')`,
      'the file promotion action',
    )
    await rejectConfirmation(
      client,
      sessionId,
      `document.querySelector('button[aria-label="晋升 高质量文档.md 到 Wiki"]').click()`,
      /将“高质量文档\.md”晋升到 wiki/,
      'Compile wiki promotion',
    )
    console.log('✓ Compile: wiki promotion impact warning and safe cancellation')

    assert.deepEqual(mutationRequests, [], `Cancelled UI actions emitted mutations: ${JSON.stringify(mutationRequests)}`)
    console.log('✓ Safety: all cancelled actions emitted zero mutation requests')

    await runCompileJobLifecycleJourney(client, sessionId, fixtureServer)
    await runFullJourney(client, sessionId, fixtureServer)
    await runAuthRecovery(client, sessionId, fixtureServer)
    await runOfflineRecovery(client, sessionId, fixtureServer)
    await runEmptyWorkspaceJourney(client, sessionId, fixtureServer)
    await runLargeGraphDetailJourney(client, sessionId, fixtureServer)
    await runKeyboardOnlyJourney(client, sessionId, fixtureServer)
    await runMobileNavigationKeyboardJourney(client, sessionId, fixtureServer)
    await runCrossPageKeyboardJourney(client, sessionId, fixtureServer)
    await runQueryModeKeyboardJourney(client, sessionId, fixtureServer)
    await runQuerySavedItemsKeyboardJourney(client, sessionId, fixtureServer)
    await runAccessibleNameAudit(client, sessionId, fixtureServer)
    await runResponsiveCoverage(client, sessionId, fixtureServer)
    assert.deepEqual(browserExceptions, [], `Browser exceptions observed: ${browserExceptions.join('; ')}`)
  } finally {
    client.close()
    await stopChrome(chrome.chromeProcess, chrome.profileDirectory)
  }
}

const fixtureServer = await createFixtureServer()
try {
  await runSmokeSuite(fixtureServer)
  console.log('Dochris browser smoke gate passed.')
} finally {
  await fixtureServer.close()
}
