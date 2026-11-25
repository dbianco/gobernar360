import { Button, Checkbox, Group, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { DateField } from '../../platform/DateField'
import { formatDate } from '../../platform/format'
import { HelpTh } from '../../platform/HelpTh'
import { send, useAction } from './api'
import { type Calendar, WEEKDAYS } from './types'

/** The days the service clock counts: working weekdays and holidays. */
export function CalendarPanel({ calendar }: { calendar: Calendar }) {
  const { t } = useTranslation()
  const action = useAction()
  const [weekdays, setWeekdays] = useState<number[]>(calendar.weekdays)
  const [day, setDay] = useState('')
  const [name, setName] = useState('')
  const label = (key: string, options = {}) => t(`complaints.parameters.${key}`, options)
  const help = (key: string) => t(`complaints.help.holidays.${key}`)
  const names = t('complaints.parameters.weekdayNames', { returnObjects: true }) as string[]
  const changed = weekdays.join() !== calendar.weekdays.join()

  function toggle(weekday: number, checked: boolean) {
    setWeekdays((current) =>
      (checked ? [...current, weekday] : current.filter((item) => item !== weekday)).sort(
        (a, b) => a - b,
      ),
    )
  }

  async function addHoliday(event: FormEvent) {
    event.preventDefault()
    const saved = await action.run(() => send('POST', '/calendar/holidays', { date: day, name }))
    if (saved) {
      setDay('')
      setName('')
    }
  }

  return (
    <Stack gap="md">
      <Stack gap="xs">
        <Title order={5}>{label('weekdays')}</Title>
        <Group>
          {WEEKDAYS.map((weekday) => (
            <Checkbox
              key={weekday}
              label={names[weekday - 1]}
              checked={weekdays.includes(weekday)}
              onChange={(event) => toggle(weekday, event.currentTarget.checked)}
            />
          ))}
        </Group>
        <Group>
          <Button
            variant="default"
            disabled={!changed || weekdays.length === 0}
            onClick={() => void action.run(() => send('PUT', '/calendar/weekdays', { weekdays }))}
          >
            {label('saveWeekdays')}
          </Button>
        </Group>
      </Stack>
      <Stack gap="xs">
        <Title order={5}>{label('holidays')}</Title>
        {calendar.holidays.length === 0 && <Text c="dimmed">{label('noHolidays')}</Text>}
        {calendar.holidays.length > 0 && (
          <Table.ScrollContainer minWidth={420} mah={320}>
            <Table stickyHeader aria-label={label('holidays')}>
              <Table.Thead>
                <Table.Tr>
                  <HelpTh help={help('date')}>{label('holidayDate')}</HelpTh>
                  <HelpTh help={help('name')}>{label('holidayName')}</HelpTh>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {calendar.holidays.map((holiday) => (
                  <Table.Tr key={holiday.id}>
                    <Table.Td>{formatDate(holiday.date)}</Table.Td>
                    <Table.Td>{holiday.name}</Table.Td>
                    <Table.Td ta="right">
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        color="red"
                        aria-label={label('deleteHoliday', {
                          name: `${holiday.name} ${formatDate(holiday.date)}`,
                        })}
                        onClick={() =>
                          void action.run(() => send('DELETE', `/calendar/holidays/${holiday.id}`))
                        }
                      >
                        {t('app.delete')}
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        <form onSubmit={(event) => void addHoliday(event)}>
          <Group align="flex-end">
            <DateField label={label('holidayDate')} required value={day} onChange={setDay} />
            <TextInput
              label={label('holidayName')}
              required
              withAsterisk={false}
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
            />
            <Button type="submit" variant="default" loading={action.pending}>
              {label('addHoliday')}
            </Button>
          </Group>
        </form>
      </Stack>
      {action.error && <Text c="red">{action.error}</Text>}
    </Stack>
  )
}
