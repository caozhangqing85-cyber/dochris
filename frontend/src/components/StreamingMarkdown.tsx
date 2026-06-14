/**
 * StreamingMarkdown — 流式 Markdown 渲染组件
 *
 * 支持流式 LLM 输出的实时 Markdown 渲染，特性：
 * - GFM 语法（表格、任务列表、删除线等，via remark-gfm）
 * - 代码块语法高亮（via rehype-highlight + highlight.js）
 * - wiki-link [[概念名]] 转为可点击的内部概念链接
 * - 流式过程中末尾显示闪烁光标
 * - 样式与项目 CSS 变量体系对齐（--color-primary 等）
 *
 * 用法：
 *   <StreamingMarkdown content={answer} streaming={loading} />
 */

import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github.css'

interface StreamingMarkdownProps {
  /** Markdown 文本（流式过程中持续累加） */
  content: string
  /** 是否正在流式生成（true 时显示末尾光标） */
  streaming?: boolean
  /** wiki-link 点击回调（如跳转到概念页） */
  onWikiLinkClick?: (conceptName: string) => void
}

/** 将 wiki-link [[...]] 转为带特殊协议的 Markdown 链接，便于自定义渲染拦截。
 *
 * [[机器学习]] → [机器学习](dochris-wiki:机器学习)
 * 保留原文本用于显示，链接 href 用 dochris-wiki: 前缀标识。
 */
function preprocessWikiLinks(text: string): string {
  return text.replace(/\[\[([^\]]+)\]\]/g, (_, name: string) => {
    const safe = name.replace(/\s+/g, ' ').trim()
    return `[${safe}](dochris-wiki:${encodeURIComponent(safe)})`
  })
}

function StreamingMarkdownImpl({
  content,
  streaming = false,
  onWikiLinkClick,
}: StreamingMarkdownProps) {
  // 预处理 wiki-link（仅在 content 变化时重算）
  const processed = useMemo(() => preprocessWikiLinks(content), [content])
  // 流式过程中跳过代码高亮（避免每个 chunk 重跑 highlight.js），结束后启用
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rehypePlugins: any[] = streaming ? [] : [[rehypeHighlight, { detect: true, ignoreMissing: true }]]

  return (
    <div className="streaming-markdown" style={markdownContainerStyle}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={rehypePlugins}
        components={{
          // 拦截 <a> 渲染：dochris-wiki: 前缀的链接渲染为可访问的概念胶囊
          a({ href, children }) {
            if (href?.startsWith('dochris-wiki:')) {
              const conceptName = decodeURIComponent(href.slice('dochris-wiki:'.length))
              const handleClick = (e: React.MouseEvent | React.KeyboardEvent) => {
                e.preventDefault()
                onWikiLinkClick?.(conceptName)
              }
              return (
                <a
                  href={`#concept-${encodeURIComponent(conceptName)}`}
                  style={wikiLinkStyle}
                  role="link"
                  tabIndex={0}
                  onClick={handleClick}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(e) }}
                >
                  {children}
                </a>
              )
            }
            // 普通外链：新标签打开
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            )
          },
        }}
      >
        {processed}
      </ReactMarkdown>
      {streaming && <span style={cursorStyle}>▎</span>}
    </div>
  )
}

/** 容器样式：继承项目排版变量 */
const markdownContainerStyle: React.CSSProperties = {
  fontSize: 'var(--text-base)',
  lineHeight: 'var(--leading-relaxed)',
  color: 'var(--text-primary)',
  fontWeight: 400,
  wordBreak: 'break-word',
}

/** wiki-link 概念胶囊样式 */
const wikiLinkStyle: React.CSSProperties = {
  color: 'var(--color-primary)',
  fontWeight: 600,
  cursor: 'pointer',
  borderBottom: '1px dashed var(--color-primary)',
}

/** 流式光标样式 */
const cursorStyle: React.CSSProperties = {
  color: 'var(--color-primary)',
  animation: 'pulse 1s infinite',
  marginLeft: '2px',
}

// memo 避免父组件无关 state 变更触发重渲染（content/streaming 不变时跳过）
export const StreamingMarkdown = memo(StreamingMarkdownImpl)
export default StreamingMarkdown
