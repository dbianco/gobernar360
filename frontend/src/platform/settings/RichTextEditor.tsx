import { ActionIcon, Button, Group, Popover, Stack, TextInput, Tooltip } from '@mantine/core'
import {
  IconArrowBackUp,
  IconArrowForwardUp,
  IconBold,
  IconH2,
  IconItalic,
  IconLink,
  IconLinkOff,
  IconList,
  IconListNumbers,
  IconStrikethrough,
  IconUnderline,
  type Icon,
} from '@tabler/icons-react'
import { type Editor, EditorContent, useEditor, useEditorState } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { forwardRef, useImperativeHandle, useState } from 'react'
import { useTranslation } from 'react-i18next'

import classes from './RichTextEditor.module.css'

/** Links may point at a placeholder such as {{link}}, filled in when the email is sent. */
const PLACEHOLDER_LINK = /^\{\{\s*\w+\s*\}\}$/

export interface RichTextEditorHandle {
  /** Insert text where the cursor is. */
  insert: (text: string) => void
  focus: () => void
}

function ToolbarButton(props: {
  label: string
  icon: Icon
  active?: boolean
  onClick: () => void
}) {
  const { icon: ButtonIcon } = props
  return (
    <Tooltip label={props.label}>
      <ActionIcon
        variant={props.active ? 'light' : 'subtle'}
        color={props.active ? 'blue' : 'gray'}
        aria-label={props.label}
        aria-pressed={props.active}
        onClick={props.onClick}
      >
        <ButtonIcon size={18} stroke={1.6} aria-hidden />
      </ActionIcon>
    </Tooltip>
  )
}

function LinkButton({
  editor,
  active,
  suggestion,
}: {
  editor: Editor
  active: boolean
  suggestion?: string
}) {
  const { t } = useTranslation()
  const [opened, setOpened] = useState(false)
  const [url, setUrl] = useState('')

  function open() {
    setUrl(editor.getAttributes('link').href ?? suggestion ?? 'https://')
    setOpened(true)
  }

  function apply() {
    const href = url.trim()
    const chain = editor.chain().focus().extendMarkRange('link')
    if (href) chain.setLink({ href }).run()
    else chain.unsetLink().run()
    setOpened(false)
  }

  return (
    <Popover opened={opened} onChange={setOpened} trapFocus position="bottom" withArrow>
      <Popover.Target>
        <span>
          <ToolbarButton
            label={t('settings.editor.link')}
            icon={IconLink}
            active={active}
            onClick={open}
          />
        </span>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap="xs">
          <TextInput
            label={t('settings.editor.linkAddress')}
            description={suggestion ? t('settings.editor.linkHint', { suggestion }) : undefined}
            value={url}
            onChange={(event) => setUrl(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                apply()
              }
            }}
          />
          <Group justify="flex-end" gap="xs">
            {suggestion && (
              <Button size="xs" variant="default" onClick={() => setUrl(suggestion)}>
                {suggestion}
              </Button>
            )}
            <Button size="xs" onClick={apply}>
              {t('settings.editor.apply')}
            </Button>
          </Group>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}

/**
 * A small rich-text editor for email bodies: paragraphs, headings, lists, bold, italic,
 * underline and links. `onChange` receives its HTML.
 */
export const RichTextEditor = forwardRef<
  RichTextEditorHandle,
  { value: string; onChange: (html: string) => void; label: string; linkSuggestion?: string }
>(function RichTextEditor({ value, onChange, label, linkSuggestion }, ref) {
  const { t } = useTranslation()
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
        code: false,
        codeBlock: false,
        link: {
          openOnClick: false,
          autolink: false,
          isAllowedUri: (url, { defaultValidate }) =>
            PLACEHOLDER_LINK.test(url) || (/^(https?:|mailto:)/i.test(url) && defaultValidate(url)),
        },
      }),
    ],
    content: value,
    editorProps: { attributes: { 'aria-label': label, 'aria-multiline': 'true', role: 'textbox' } },
    onUpdate: ({ editor: current }) => onChange(current.getHTML()),
  })
  const state = useEditorState({
    editor,
    // Null until the editor exists, once, before its first render.
    selector: ({ editor: current }) =>
      current && {
        bold: current.isActive('bold'),
        italic: current.isActive('italic'),
        underline: current.isActive('underline'),
        strike: current.isActive('strike'),
        heading: current.isActive('heading', { level: 2 }),
        bulletList: current.isActive('bulletList'),
        orderedList: current.isActive('orderedList'),
        link: current.isActive('link'),
      },
  })

  useImperativeHandle(
    ref,
    () => ({
      insert: (text) => editor?.chain().focus().insertContent(text).run(),
      focus: () => editor?.commands.focus(),
    }),
    [editor],
  )

  if (!editor || !state) return null
  const run =
    (command: (chain: ReturnType<Editor['chain']>) => ReturnType<Editor['chain']>) => () =>
      command(editor.chain().focus()).run()

  return (
    <div className={classes.root}>
      <Group
        gap={2}
        className={classes.toolbar}
        role="toolbar"
        aria-label={t('settings.editor.toolbar')}
      >
        <ToolbarButton
          label={t('settings.editor.bold')}
          icon={IconBold}
          active={state.bold}
          onClick={run((c) => c.toggleBold())}
        />
        <ToolbarButton
          label={t('settings.editor.italic')}
          icon={IconItalic}
          active={state.italic}
          onClick={run((c) => c.toggleItalic())}
        />
        <ToolbarButton
          label={t('settings.editor.underline')}
          icon={IconUnderline}
          active={state.underline}
          onClick={run((c) => c.toggleUnderline())}
        />
        <ToolbarButton
          label={t('settings.editor.strike')}
          icon={IconStrikethrough}
          active={state.strike}
          onClick={run((c) => c.toggleStrike())}
        />
        <ToolbarButton
          label={t('settings.editor.heading')}
          icon={IconH2}
          active={state.heading}
          onClick={run((c) => c.toggleHeading({ level: 2 }))}
        />
        <ToolbarButton
          label={t('settings.editor.bulletList')}
          icon={IconList}
          active={state.bulletList}
          onClick={run((c) => c.toggleBulletList())}
        />
        <ToolbarButton
          label={t('settings.editor.orderedList')}
          icon={IconListNumbers}
          active={state.orderedList}
          onClick={run((c) => c.toggleOrderedList())}
        />
        <LinkButton editor={editor} active={state.link} suggestion={linkSuggestion} />
        <ToolbarButton
          label={t('settings.editor.unlink')}
          icon={IconLinkOff}
          onClick={run((c) => c.unsetLink())}
        />
        <ToolbarButton
          label={t('settings.editor.undo')}
          icon={IconArrowBackUp}
          onClick={run((c) => c.undo())}
        />
        <ToolbarButton
          label={t('settings.editor.redo')}
          icon={IconArrowForwardUp}
          onClick={run((c) => c.redo())}
        />
      </Group>
      <EditorContent editor={editor} className={classes.content} />
    </div>
  )
})
