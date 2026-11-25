import { Alert, Anchor, Button, FileInput, Group, List, Stack, Table, Text } from '@mantine/core'
import { IconDownload, IconFileTypeCsv } from '@tabler/icons-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api, ApiError, downloadUrl } from '../api/client'
import { useAction } from './useAction'

export interface ImportResult {
  created: number
  updated: number
  unchanged: number
}

interface RowError {
  line: number
  code: string
  column: string
  value: string
}

/** The file's text: UTF-8, or Windows-1252 as older Excel versions save it. */
function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error)
    reader.onload = () => {
      const bytes = reader.result as ArrayBuffer
      try {
        resolve(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
      } catch {
        resolve(new TextDecoder('windows-1252').decode(bytes))
      }
    }
    reader.readAsArrayBuffer(file)
  })
}

/**
 * Adds or updates members from a CSV file. The last row for an email decides that
 * person's access, whether it is in this file or came in an earlier one.
 */
export function ImportUsersForm(props: {
  /** API prefix of the municipality: "/admin" or "/platform/municipalities/{id}". */
  base: string
  scope: string
  onDone: (result: ImportResult) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const action = useAction([props.scope, 'me'])
  const [file, setFile] = useState<File | null>(null)
  const [rowErrors, setRowErrors] = useState<RowError[]>([])
  const [failure, setFailure] = useState<string | null>(null)

  async function submit(file: File) {
    setRowErrors([])
    setFailure(null)
    let content: string
    try {
      content = await readText(file)
    } catch {
      setFailure(t('users.import.unreadable'))
      return
    }
    const result = await action.run(async () => {
      try {
        return await api<ImportResult>(`${props.base}/users/import`, {
          method: 'POST',
          body: { csv: content },
        })
      } catch (error) {
        if (error instanceof ApiError && error.code === 'invalid_csv') {
          setRowErrors((error.details ?? []) as unknown as RowError[])
          return undefined
        }
        throw error
      }
    })
    if (result) props.onDone(result)
  }

  const describe = (error: RowError) =>
    t(`users.import.errors.${error.code}`, {
      column: error.column,
      value: error.value,
      defaultValue: t('users.import.errors.generic'),
    })

  return (
    <Stack>
      <Text size="sm">{t('users.import.intro')}</Text>
      <List size="sm" spacing={4}>
        <List.Item>{t('users.import.ruleColumns')}</List.Item>
        <List.Item>{t('users.import.ruleLevels')}</List.Item>
        <List.Item>{t('users.import.ruleLastRow')}</List.Item>
        <List.Item>{t('users.import.ruleMissingColumn')}</List.Item>
        <List.Item>{t('users.import.ruleEmails')}</List.Item>
      </List>
      <Anchor href={downloadUrl(`${props.base}/users/import-template.csv`)} size="sm">
        <Group gap={6} component="span">
          <IconDownload size={16} aria-hidden />
          {t('users.import.downloadExample')}
        </Group>
      </Anchor>
      <FileInput
        label={t('users.import.file')}
        placeholder={t('users.import.choose')}
        accept=".csv,text/csv"
        leftSection={<IconFileTypeCsv size={18} aria-hidden />}
        clearable
        value={file}
        onChange={(value) => {
          setFile(value)
          setRowErrors([])
          setFailure(null)
        }}
      />
      {failure && <Alert color="red">{failure}</Alert>}
      {action.error && <Alert color="red">{action.error}</Alert>}
      {rowErrors.length > 0 && (
        <Alert color="red" title={t('users.import.hasErrors', { count: rowErrors.length })}>
          <Table.ScrollContainer minWidth={360} mah={240}>
            <Table withRowBorders={false} verticalSpacing={2}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('users.import.line')}</Table.Th>
                  <Table.Th>{t('users.import.problem')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rowErrors.map((error, index) => (
                  <Table.Tr key={index}>
                    <Table.Td>{error.line}</Table.Td>
                    <Table.Td>{describe(error)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Text size="sm" mt="xs">
            {t('users.import.nothingChanged')}
          </Text>
        </Alert>
      )}
      <Group justify="flex-end">
        <Button variant="default" onClick={props.onCancel}>
          {t('app.cancel')}
        </Button>
        <Button
          disabled={!file}
          loading={action.pending}
          onClick={file ? () => void submit(file) : undefined}
        >
          {t('users.import.submit')}
        </Button>
      </Group>
    </Stack>
  )
}
