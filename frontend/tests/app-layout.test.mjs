import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const sourceUrl = new URL('../src/components/layout/AppLayout.tsx', import.meta.url)

test('mobile navigation leaves the tab order when closed and traps focus when open', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /aria-label="打开导航菜单"/)
  assert.match(source, /aria-label="关闭导航菜单"/)
  assert.match(source, /aria-controls="mobile-navigation-dialog"/)
  assert.match(source, /aria-expanded=\{mobileOpen\}/)
  assert.match(source, /role=\{mobileOpen \? 'dialog' : undefined\}/)
  assert.match(source, /aria-hidden=\{!mobileOpen\} inert=\{!mobileOpen\}/)
  assert.match(source, /<main[^>]*inert=\{mobileOpen\}/)
  assert.match(source, /event\.key === 'Escape'/)
  assert.match(source, /event\.key !== 'Tab'/)
  assert.match(source, /sidebar\.contains\(document\.activeElement\)/)
  assert.match(source, /mobileMenuButtonRef\.current\?\.focus\(\)/)
  assert.match(source, /mobileCloseButtonRef\.current\?\.focus\(\)/)
})

test('client-side route changes move focus to the destination page heading', async () => {
  const source = await readFile(sourceUrl, 'utf8')

  assert.match(source, /previousPathRef/)
  assert.match(source, /mainContentRef\.current\?\.querySelector<HTMLElement>\('h1'\)/)
  assert.match(source, /heading\.tabIndex = -1/)
  assert.match(source, /heading\.focus\(\{ preventScroll: true \}\)/)
  assert.match(source, /ref=\{mainContentRef\}/)
})
