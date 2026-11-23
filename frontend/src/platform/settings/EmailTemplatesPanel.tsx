import {
  Alert,
  Badge,
  Button,
  Group,
  NativeSelect,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, ApiError } from '../../api/client'
import { useAuth } from '../authContext'
import { useConfirm } from '../confirmContext'
import { errorMessage } from '../errorMessage'
import { RichTextEditor, type RichTextEditorHandle } from './RichTextEditor'
import { useSettingsScope } from './scope'
import type { EmailTemplate } from './types'

const TEMPLATE_ERRORS: Record<string, string> = {
  template_unknown_variable: 'settings.templates.unknownVariables',
  template_missing_variable: 'settings.templates.missingVariables',
}

function useTemplateError() {
  const { t } = useTranslation()
  return (error: unknown) => {
    if (error instanceof ApiError && TEMPLATE_ERRORS[error.code]) {
      // Each detail names the variables, separated by commas.
      const variables = (error.details ?? [])
        .flatMap((detail) => detail.message.split(', '))
        .map((name) => `{{${name}}}`)
        .join(', ')
      return t(TEMPLATE_ERRORS[error.code], { variables })
    }
    return errorMessage(error)
  }
}

/** Subject and body of one kind of email, with its variables at hand. */
function TemplateForm(props: { template: EmailTemplate; onDirtyChange: (dirty: boolean) => void }) {
  const { template, onDirtyChange } = props
  const { t } = useTranslation()
  const { me } = useAuth()
  const queryClient = useQueryClient()
  const confirm = useConfirm()
  const templateError = useTemplateError()
  const [subject, setSubject] = useState(template.subject)
  const [html, setHtml] = useState(template.html)
  const [pending, setPending] = useState<'save' | 'test' | 'restore' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const editor = useRef<RichTextEditorHandle>(null)
  const subjectInput = useRef<HTMLInputElement>(null)
  // Where a variable button inserts: the field used last.
  const lastField = useRef<'subject' | 'body'>('body')
  const dirty = subject !== template.subject || html !== template.html
  const { base, templatesKey } = useSettingsScope()
  const url = `${base}/email-templates/${template.key}`

  function update(next: { subject?: string; html?: string }) {
    const nextSubject = next.subject ?? subject
    const nextHtml = next.html ?? html
    if (next.subject !== undefined) setSubject(nextSubject)
    if (next.html !== undefined) setHtml(nextHtml)
    onDirtyChange(nextSubject !== template.subject || nextHtml !== template.html)
  }

  function insert(variable: string) {
    const placeholder = `{{${variable}}}`
    const input = subjectInput.current
    if (lastField.current === 'subject' && input && variable !== 'items') {
      const start = input.selectionStart ?? subject.length
      const end = input.selectionEnd ?? start
      update({ subject: subject.slice(0, start) + placeholder + subject.slice(end) })
      requestAnimationFrame(() => {
        input.focus()
        input.setSelectionRange(start + placeholder.length, start + placeholder.length)
      })
    } else {
      editor.current?.insert(placeholder)
    }
  }

  async function act(kind: 'save' | 'test' | 'restore') {
    setPending(kind)
    setError(null)
    setNotice(null)
    try {
      if (kind === 'test') {
        await api(`${url}/test`, { method: 'POST', body: { subject, html } })
        setNotice(t('settings.templates.testSent', { email: me?.user.email }))
      } else {
        const request =
          kind === 'save'
            ? ({ method: 'PUT', body: { subject, html } } as const)
            : ({ method: 'DELETE' } as const)
        // What the server stored may differ from what was typed (tidied, sanitised), or
        // be what it already had: the form shows it either way.
        const stored = await api<EmailTemplate>(url, request)
        setSubject(stored.subject)
        setHtml(stored.html)
        onDirtyChange(false)
        await queryClient.invalidateQueries({ queryKey: templatesKey })
      }
    } catch (caught) {
      setError(templateError(caught))
    } finally {
      setPending(null)
    }
  }

  return (
    <Stack>
      <Group gap="xs">
        <Badge variant="light" color={template.customized ? 'blue' : 'gray'}>
          {t(template.customized ? 'settings.templates.customized' : 'settings.templates.default')}
        </Badge>
        {dirty && (
          <Text size="sm" c="orange.8">
            {t('settings.templates.unsaved')}
          </Text>
        )}
      </Group>
      {error && (
        <Alert color="red" withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {notice && (
        <Alert color="green" withCloseButton onClose={() => setNotice(null)}>
          {notice}
        </Alert>
      )}
      <TextInput
        ref={subjectInput}
        label={t('settings.templates.subject')}
        required
        maxLength={300}
        value={subject}
        onFocus={() => (lastField.current = 'subject')}
        onChange={(event) => update({ subject: event.currentTarget.value })}
      />
      <Stack gap={4}>
        <Text size="sm" fw={500}>
          {t('settings.templates.variablesTitle')}
        </Text>
        <Text size="xs" c="dimmed">
          {t('settings.templates.variablesHint')}
        </Text>
        <Group gap={6}>
          {template.variables.map((variable) => (
            <Button
              key={variable}
              size="compact-xs"
              variant="light"
              color={template.required.includes(variable) ? 'orange' : 'blue'}
              aria-label={t('settings.templates.insertNamed', {
                name: t(`settings.variables.${variable}`),
              })}
              onClick={() => insert(variable)}
            >
              {t(`settings.variables.${variable}`)}
              {template.required.includes(variable) ? ' *' : ''}
            </Button>
          ))}
        </Group>
        {template.required.length > 0 && (
          <Text size="xs" c="dimmed">
            {t('settings.templates.requiredHint')}
          </Text>
        )}
      </Stack>
      <div onFocusCapture={() => (lastField.current = 'body')}>
        <Text size="sm" fw={500} mb={4}>
          {t('settings.templates.body')}
        </Text>
        <RichTextEditor
          ref={editor}
          label={t('settings.templates.body')}
          value={template.html}
          linkSuggestion={template.variables.includes('link') ? '{{link}}' : undefined}
          onChange={(value) => update({ html: value })}
        />
      </div>
      <Group justify="space-between">
        <Group gap="xs">
          <Button variant="default" loading={pending === 'test'} onClick={() => void act('test')}>
            {t('settings.templates.test')}
          </Button>
          {template.customized && (
            <Button
              variant="subtle"
              color="red"
              loading={pending === 'restore'}
              onClick={async () => {
                const confirmed = await confirm({
                  title: t('settings.templates.restore'),
                  message: t('settings.templates.restoreConfirm'),
                  confirmLabel: t('settings.templates.restore'),
                  danger: true,
                })
                if (confirmed) void act('restore')
              }}
            >
              {t('settings.templates.restore')}
            </Button>
          )}
        </Group>
        <Button disabled={!dirty} loading={pending === 'save'} onClick={() => void act('save')}>
          {t('settings.templates.save')}
        </Button>
      </Group>
    </Stack>
  )
}

/** The municipality's version of each email it sends. */
export function EmailTemplatesPanel() {
  const { t } = useTranslation()
  const { base, templatesKey } = useSettingsScope()
  const templates = useQuery({
    queryKey: templatesKey,
    queryFn: () => api<EmailTemplate[]>(`${base}/email-templates`),
  })
  const confirm = useConfirm()
  const [selected, setSelected] = useState('invitation')
  const [dirty, setDirty] = useState(false)
  const template = templates.data?.find((item) => item.key === selected) ?? templates.data?.[0]
  const label = (key: string) => t([`settings.templates.keys.${key}.label`, key])

  return (
    <Stack>
      <Title order={3}>{t('settings.templates.title')}</Title>
      <Text size="sm" c="dimmed">
        {t('settings.templates.hint', { example: '{{name}}' })}
      </Text>
      {templates.isError && <Alert color="red">{errorMessage(templates.error)}</Alert>}
      {templates.data && template && (
        <>
          <NativeSelect
            label={t('settings.templates.choose')}
            value={template.key}
            data={templates.data.map((item) => ({ value: item.key, label: label(item.key) }))}
            onChange={async (event) => {
              const value = event.currentTarget.value
              if (value === template.key) return
              if (dirty) {
                const discard = await confirm({
                  title: t('settings.templates.discardTitle'),
                  message: t('settings.templates.discard'),
                  confirmLabel: t('settings.templates.discardConfirm'),
                  danger: true,
                })
                if (!discard) return
              }
              setDirty(false)
              setSelected(value)
            }}
          />
          <Text size="sm">
            {t(`settings.templates.keys.${template.key}.description`, { defaultValue: '' })}
          </Text>
          <TemplateForm
            // A fresh form for each kind and for every version the server stores.
            key={`${template.key}:${template.customized}:${template.subject}:${template.html}`}
            template={template}
            onDirtyChange={setDirty}
          />
        </>
      )}
    </Stack>
  )
}
