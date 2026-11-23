/**
 * Everything a person can read on the screen, one piece per line, for snapshot tests:
 * the text, and the names and hints that are not text (accessible names, placeholders,
 * field descriptions). A snapshot of it catches a label, a message or an empty state
 * that changes or disappears, which assertions on a few elements miss.
 *
 * Tests run on a fixed date (src/test/setup.ts), so the years offered by the selects and
 * the one the status strip shows do not change with the calendar.
 */
export function screenText(root: HTMLElement = document.body): string {
  const lines: string[] = []
  const skipped = (element: Element) => element.matches('script, style')
  const visit = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent?.replace(/\s+/g, ' ').trim()
      if (text) lines.push(text)
      return
    }
    if (!(node instanceof Element) || skipped(node)) return
    const label = node.getAttribute('aria-label')
    if (label) lines.push(`[${label}]`)
    const placeholder = node.getAttribute('placeholder')
    if (placeholder) lines.push(`(${placeholder})`)
    node.childNodes.forEach(visit)
  }
  visit(root)
  return lines.join('\n')
}
