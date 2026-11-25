import 'dayjs/locale/es'

import { ActionIcon, FocusTrap, Popover, TextInput } from '@mantine/core'
import { DatePicker } from '@mantine/dates'
import { IconCalendar } from '@tabler/icons-react'
import { type CSSProperties, type KeyboardEvent, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { dateText, parseDate } from './dates'
import { formatDate, todayIso } from './format'

/**
 * A date, always shown as DD/MM/YYYY. The browser's own date field follows the language of
 * the browser instead of the page's, so it must not be used (see dateFields.test.ts).
 *
 * `value` is an ISO date or '' for none, as in the browser's: what is typed counts only
 * once it is a whole date, and a form with half of one is not sent.
 */
export function DateField(props: {
  value: string
  onChange: (value: string) => void
  label?: string
  'aria-label'?: string
  required?: boolean
  /** First and last dates accepted, as ISO dates. */
  min?: string | null
  max?: string | null
  maw?: CSSProperties['maxWidth']
}) {
  const { t } = useTranslation()
  const input = useRef<HTMLInputElement>(null)
  const [text, setText] = useState(() => dateText(props.value))
  const [open, setOpen] = useState(false)
  const [left, setLeft] = useState(false)

  // The value may be changed from outside (a form cleared after saving): show it, unless it
  // is what is already written.
  const [known, setKnown] = useState(props.value)
  if (known !== props.value) {
    setKnown(props.value)
    if ((parseDate(text) ?? '') !== props.value) setText(dateText(props.value))
  }

  const parsed = parseDate(text)
  let problem = ''
  if (text.trim() && !parsed) problem = t('app.date.invalid')
  else if (parsed && props.min && parsed < props.min) {
    problem = t('app.date.min', { date: formatDate(props.min) })
  } else if (parsed && props.max && parsed > props.max) {
    problem = t('app.date.max', { date: formatDate(props.max) })
  }
  // Keeps the browser from sending the form, as its own date field would.
  useEffect(() => input.current?.setCustomValidity(problem), [problem])

  function type(next: string) {
    setText(next)
    const value = parseDate(next) ?? ''
    if (value !== props.value) props.onChange(value)
  }

  function close() {
    setOpen(false)
    input.current?.focus()
  }

  function pick(value: string | null) {
    type(dateText(value ?? ''))
    close()
  }

  function leaveWithEscape(event: KeyboardEvent) {
    if (event.key === 'Escape') close()
  }

  return (
    <Popover
      opened={open}
      onChange={setOpen}
      position="bottom-start"
      shadow="md"
      closeOnEscape={false}
      // The field's label is not the calendar's.
      withRoles={false}
      // Above a modal.
      zIndex={350}
    >
      <Popover.Target>
        {/* The button too: clicking it while open is not clicking outside. */}
        <div>
          <TextInput
            ref={input}
            label={props.label}
            aria-label={props['aria-label']}
            placeholder={t('app.date.placeholder')}
            autoComplete="off"
            required={props.required}
            withAsterisk={false}
            maw={props.maw}
            maxLength={10}
            error={left && problem}
            value={text}
            onChange={(event) => {
              setLeft(false)
              type(event.currentTarget.value)
            }}
            onInvalid={() => setLeft(true)}
          onBlur={() => {
              setLeft(true)
              if (parsed) setText(dateText(parsed))
            }}
            rightSection={
              <ActionIcon
                variant="subtle"
                color="gray"
                aria-label={t('app.date.open')}
                aria-expanded={open}
                onClick={() => setOpen(!open)}
              >
                <IconCalendar size={18} stroke={1.5} aria-hidden />
              </ActionIcon>
            }
          />
        </div>
      </Popover.Target>
      <Popover.Dropdown onKeyDown={leaveWithEscape}>
        {open && (
          <FocusTrap active>
            <DatePicker
              locale="es"
              // Escape closes the calendar, not the modal it was opened from.
              __stopPropagation
              value={parsed}
              defaultDate={parsed ?? props.min ?? props.max ?? todayIso()}
              minDate={props.min ?? undefined}
              maxDate={props.max ?? undefined}
              onChange={pick}
              ariaLabels={{
                previousMonth: t('app.date.previousMonth'),
                nextMonth: t('app.date.nextMonth'),
                previousYear: t('app.date.previousYear'),
                nextYear: t('app.date.nextYear'),
                previousDecade: t('app.date.previousDecade'),
                nextDecade: t('app.date.nextDecade'),
                monthLevelControl: t('app.date.chooseMonth'),
                yearLevelControl: t('app.date.chooseYear'),
              }}
            />
          </FocusTrap>
        )}
      </Popover.Dropdown>
    </Popover>
  )
}
