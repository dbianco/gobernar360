import { Alert, Button, FileInput, Group, List, Modal, Stack, Text } from '@mantine/core'
import { IconMap } from '@tabler/icons-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/client'
import { errorMessage } from '../errorMessage'
import { importZones, useRefreshEverything } from './api'
import type { ZoneImport } from './types'

interface Problem {
  /** Position of the zone in the file; 0 for the file itself. */
  row: number
  name: string | null
  code: string
}

function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error)
    reader.onload = () => resolve(reader.result as string)
    reader.readAsText(file)
  })
}

/** Creates or moves zones from a GeoJSON file. Nothing changes if any has a problem. */
export function ImportZonesForm(props: {
  opened: boolean
  onDone: (result: ZoneImport) => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const label = (key: string, options = {}) => t(`geo.zones.import.${key}`, options)
  const refresh = useRefreshEverything()
  const [file, setFile] = useState<File | null>(null)
  const [problems, setProblems] = useState<Problem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(chosen: File) {
    setProblems([])
    setError(null)
    let geojson: unknown
    try {
      geojson = JSON.parse(await readText(chosen))
      if (typeof geojson !== 'object' || geojson === null) throw new Error('Not an object.')
    } catch {
      setError(label('unreadable'))
      return
    }
    setPending(true)
    try {
      const result = await importZones(geojson)
      await refresh()
      props.onDone(result)
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'zone_file_invalid') {
        setProblems((caught.details ?? []) as unknown as Problem[])
      } else {
        setError(errorMessage(caught))
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal opened={props.opened} onClose={props.onClose} title={label('title')}>
      <Stack gap="sm">
        <Text size="sm">{label('intro')}</Text>
        {error && <Alert color="red">{error}</Alert>}
        {problems.length > 0 && (
          <Alert color="red" title={label('problems')}>
            <List size="sm">
              {problems.map((problem) => (
                <List.Item key={`${problem.row} ${problem.code}`}>
                  {problem.row === 0
                    ? label(`codes.${problem.code}`)
                    : label('problem', {
                        row: problem.row,
                        name: problem.name ?? label('unnamed'),
                        problem: label(`codes.${problem.code}`),
                      })}
                </List.Item>
              ))}
            </List>
          </Alert>
        )}
        <FileInput
          label={label('file')}
          placeholder={label('choose')}
          accept=".geojson,.json,application/geo+json,application/json"
          leftSection={<IconMap size={16} aria-hidden />}
          value={file}
          onChange={setFile}
          clearable
        />
        <Group gap="xs">
          <Button
            loading={pending}
            disabled={!file}
            onClick={() => file && void submit(file)}
          >
            {label('submit')}
          </Button>
          <Button variant="default" onClick={props.onClose}>
            {t('app.cancel')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
