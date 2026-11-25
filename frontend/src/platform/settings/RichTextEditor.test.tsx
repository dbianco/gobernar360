import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef } from 'react'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { RichTextEditor, type RichTextEditorHandle } from './RichTextEditor'

interface TiptapCommands {
  selectAll: () => void
  setTextSelection: (position: number | { from: number; to: number }) => void
}

const tool = (key: string) => t(`settings.editor.${key}`)

async function renderEditor(value = '<p>hola mundo</p>', linkSuggestion?: string) {
  const onChange = vi.fn()
  const ref = createRef<RichTextEditorHandle>()
  renderApp(
    <RichTextEditor
      ref={ref}
      value={value}
      onChange={onChange}
      label="Texto"
      linkSuggestion={linkSuggestion}
    />,
    { me: makeMe() },
  )
  const box = await screen.findByRole('textbox', { name: 'Texto' })
  // Tiptap keeps its editor on the element: the way to select text in jsdom. Its commands
  // are bound to the state when read, so they are read again each time.
  const editor = (box as unknown as { editor: { commands: TiptapCommands } }).editor
  const commands: TiptapCommands = {
    selectAll: () => editor.commands.selectAll(),
    setTextSelection: (position) => editor.commands.setTextSelection(position),
  }
  const lastHtml = () => onChange.mock.calls.at(-1)?.[0] as string | undefined
  return { onChange, ref, commands, lastHtml, user: userEvent.setup() }
}

it('shows the text it was given, as a multi-line text box', async () => {
  await renderEditor('<p>Hola, <strong>Ana</strong></p>')

  const box = screen.getByRole('textbox', { name: 'Texto' })
  expect(box).toHaveAttribute('aria-multiline', 'true')
  expect(within(box).getByText('Ana').tagName).toBe('STRONG')
})

it.each([
  ['bold', '<p><strong>hola mundo</strong></p>'],
  ['italic', '<p><em>hola mundo</em></p>'],
  ['underline', '<p><u>hola mundo</u></p>'],
  ['strike', '<p><s>hola mundo</s></p>'],
  // Tiptap keeps an empty paragraph after a block so there is always a place to type.
  ['heading', '<h2>hola mundo</h2><p></p>'],
  ['bulletList', '<ul><li><p>hola mundo</p></li></ul><p></p>'],
  ['orderedList', '<ol><li><p>hola mundo</p></li></ol><p></p>'],
])('formats the selection with %s and marks the button as active', async (key, html) => {
  const { commands, lastHtml, user } = await renderEditor()
  const button = screen.getByRole('button', { name: tool(key) })
  expect(button).toHaveAttribute('aria-pressed', 'false')

  commands.selectAll()
  await user.click(button)

  await waitFor(() => expect(lastHtml()).toBe(html))
  // With the cursor inside the formatted text, its button shows as pressed.
  commands.setTextSelection(3)
  await waitFor(() => expect(button).toHaveAttribute('aria-pressed', 'true'))
})

it('links the selection to the suggested placeholder', async () => {
  const { commands, lastHtml, user } = await renderEditor('<p>elegir</p>', '{{link}}')

  commands.selectAll()
  await user.click(screen.getByRole('button', { name: tool('link') }))
  const address = await screen.findByRole('textbox', { name: tool('linkAddress') })
  expect(address).toHaveValue('{{link}}')
  expect(
    screen.getByText(tool('linkHint').replace('{{suggestion}}', '{{link}}')),
  ).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: tool('apply') }))

  await waitFor(() => expect(lastHtml()).toContain('href="{{link}}"'))
  expect(lastHtml()).toContain('>elegir</a>')
})

it('links to an address typed and confirmed with Enter', async () => {
  const { commands, lastHtml, user } = await renderEditor('<p>sitio</p>')

  commands.selectAll()
  await user.click(screen.getByRole('button', { name: tool('link') }))
  const address = await screen.findByRole('textbox', { name: tool('linkAddress') })
  expect(address).toHaveValue('https://')
  expect(screen.queryByRole('button', { name: '{{link}}' })).toBeNull()
  await user.clear(address)
  await user.type(address, 'https://noetinger.gob.ar{Enter}')

  await waitFor(() => expect(lastHtml()).toContain('href="https://noetinger.gob.ar"'))
})

it('fills the address with the suggestion when its button is pressed', async () => {
  const { commands, user } = await renderEditor('<p>sitio</p>', '{{link}}')

  commands.selectAll()
  await user.click(screen.getByRole('button', { name: tool('link') }))
  const address = await screen.findByRole('textbox', { name: tool('linkAddress') })
  await user.clear(address)
  await user.click(screen.getByRole('button', { name: '{{link}}' }))

  expect(address).toHaveValue('{{link}}')
})

it('does not link to scripts', async () => {
  const { commands, onChange, user } = await renderEditor('<p>sitio</p>')

  commands.selectAll()
  await user.click(screen.getByRole('button', { name: tool('link') }))
  const address = await screen.findByRole('textbox', { name: tool('linkAddress') })
  await user.clear(address)
  await user.type(address, 'javascript:alert(1)')
  await user.click(screen.getByRole('button', { name: tool('apply') }))

  await waitFor(() =>
    expect(screen.queryByRole('textbox', { name: tool('linkAddress') })).toBeNull(),
  )
  for (const [html] of onChange.mock.calls) expect(html).not.toContain('javascript')
})

it('edits an existing link, and removes it when the address is emptied', async () => {
  const { commands, lastHtml, user } = await renderEditor(
    '<p><a href="https://viejo.test">sitio</a></p>',
  )

  commands.setTextSelection({ from: 2, to: 4 })
  const linkButton = screen.getByRole('button', { name: tool('link') })
  await waitFor(() => expect(linkButton).toHaveAttribute('aria-pressed', 'true'))
  await user.click(linkButton)
  const address = await screen.findByRole('textbox', { name: tool('linkAddress') })
  expect(address).toHaveValue('https://viejo.test')
  await user.clear(address)
  await user.click(screen.getByRole('button', { name: tool('apply') }))

  await waitFor(() => expect(lastHtml()).toBe('<p>sitio</p>'))
})

it('removes a link with its own button', async () => {
  const { commands, lastHtml, user } = await renderEditor(
    '<p><a href="mailto:a@b.test">correo</a></p>',
  )

  commands.selectAll()
  await user.click(screen.getByRole('button', { name: tool('unlink') }))

  await waitFor(() => expect(lastHtml()).toBe('<p>correo</p>'))
})

it('undoes and redoes a change', async () => {
  const { commands, lastHtml, user } = await renderEditor()

  commands.selectAll()
  await user.click(screen.getByRole('button', { name: tool('bold') }))
  await waitFor(() => expect(lastHtml()).toBe('<p><strong>hola mundo</strong></p>'))
  await user.click(screen.getByRole('button', { name: tool('undo') }))
  await waitFor(() => expect(lastHtml()).toBe('<p>hola mundo</p>'))
  await user.click(screen.getByRole('button', { name: tool('redo') }))

  await waitFor(() => expect(lastHtml()).toBe('<p><strong>hola mundo</strong></p>'))
})

it('inserts text where the cursor is, for the variable buttons', async () => {
  const { commands, ref, lastHtml } = await renderEditor('<p>Hola mundo</p>')

  // Position 6 is after "Hola " (the paragraph opens at 1).
  commands.setTextSelection(6)
  ref.current?.insert('{{name}} ')

  await waitFor(() => expect(lastHtml()).toBe('<p>Hola {{name}} mundo</p>'))
  ref.current?.focus()
})

it('names its toolbar for assistive technology', async () => {
  await renderEditor()

  const toolbar = screen.getByRole('toolbar', { name: tool('toolbar') })
  expect(within(toolbar).getAllByRole('button')).toHaveLength(11)
})

it.each([
  'https://noetinger.gob.ar',
  'http://noetinger.gob.ar',
  'HTTPS://NOETINGER.GOB.AR',
  'mailto:mesa@noetinger.gob.ar',
  '{{link}}',
  '{{ account_link }}',
])('keeps a link to %s', async (href) => {
  await renderEditor(`<p><a href="${href}">sitio</a></p>`)

  expect(screen.getByText('sitio')).toHaveAttribute('href', href)
})

it.each([
  'javascript:alert(1)',
  'javascript:void("https://x.test")',
  'ftp://noetinger.gob.ar',
  'tel:3472555',
  'noetinger.gob.ar',
  '{{}}',
  '{{a b}}',
  'x{{link}}',
  '{{link}}x',
])('drops a link to %s', async (href) => {
  await renderEditor(`<p><a href='${href}'>sitio</a> web</p>`)

  const box = screen.getByRole('textbox', { name: 'Texto' })
  expect(box.textContent).toBe('sitio web')
  expect(box.querySelector(`a[href='${href}']`)).toBeNull()
})

it('has two sizes of headings and no code', async () => {
  await renderEditor('<h1>uno</h1><h2>dos</h2><h3>tres</h3><p><code>x</code></p><pre>y</pre>')

  const box = screen.getByRole('textbox', { name: 'Texto' })
  expect(within(box).getByText('dos').tagName).toBe('H2')
  expect(within(box).getByText('tres').tagName).toBe('H3')
  expect(box.querySelector('h1, code, pre')).toBeNull()
})

it('links to an address without the spaces around it', async () => {
  const { commands, lastHtml, user } = await renderEditor('<p>sitio</p>')

  commands.selectAll()
  await user.click(screen.getByRole('button', { name: tool('link') }))
  const address = await screen.findByRole('textbox', { name: tool('linkAddress') })
  await user.clear(address)
  await user.type(address, '  https://noetinger.gob.ar  {Enter}')

  await waitFor(() => expect(lastHtml()).toContain('href="https://noetinger.gob.ar"'))
})
