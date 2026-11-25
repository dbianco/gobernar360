import { Button, Modal } from '@mantine/core'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { type ComponentProps, useState } from 'react'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { DateField } from './DateField'

type Props = Partial<ComponentProps<typeof DateField>>
const date = (key: string, options = {}) => t(`app.date.${key}`, options)
const field = () => screen.findByLabelText<HTMLInputElement>('Fecha')

/** A form with the field, that shows its value and can be cleared or sent. */
function Form({ initial = '', onChange, onSubmit, ...props }: Props & {
  initial?: string
  onSubmit?: () => void
}) {
  const [value, setValue] = useState(initial)
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit?.()
      }}
    >
      <DateField
        label="Fecha"
        {...props}
        value={value}
        onChange={(next) => {
          setValue(next)
          onChange?.(next)
        }}
      />
      <button type="button" onClick={() => setValue('')}>
        clear
      </button>
      <button type="button" onClick={() => setValue('2026-12-31')}>
        set
      </button>
      <button type="submit">send</button>
    </form>
  )
}

function renderField(props: ComponentProps<typeof Form> = {}) {
  const onChange = vi.fn()
  renderApp(<Form {...props} onChange={onChange} />, { me: makeMe() })
  return { onChange, user: userEvent.setup() }
}

it('shows the date as day, month and year', async () => {
  renderField({ initial: '2026-11-24' })

  expect(await field()).toHaveValue('24/11/2026')
  expect(await field()).toHaveAttribute('placeholder', date('placeholder'))
})

it('takes what is typed once it is a whole date, and writes it in full on leaving', async () => {
  const { user, onChange } = renderField()

  await user.type(await field(), '5/1/2026')
  expect(onChange.mock.calls).toEqual([['2026-01-05']])
  expect(await field()).toHaveValue('5/1/2026')
  await user.tab()

  expect(await field()).toHaveValue('05/01/2026')
})

it('has no date while what is written is not one, and says so on leaving', async () => {
  const { user, onChange } = renderField({ initial: '2026-11-24' })

  await user.type(await field(), '{Backspace}')
  expect(onChange).toHaveBeenLastCalledWith('')
  expect(screen.queryByText(date('invalid'))).toBeNull()
  await user.tab()

  expect(await screen.findByText(date('invalid'))).toBeInTheDocument()
  // What was written stays, to be corrected.
  expect(await field()).toHaveValue('24/11/202')
  await user.type(await field(), '7')
  expect(onChange).toHaveBeenLastCalledWith('2027-11-24')
  expect(screen.queryByText(date('invalid'))).toBeNull()
})

it('is not sent with half a date, or without one when it is required', async () => {
  const onSubmit = vi.fn()
  const { user } = renderField({ onSubmit, required: true })
  const send = () => user.click(screen.getByRole('button', { name: 'send' }))

  await field()
  await send()
  await user.type(await field(), '31/02/2026')
  await send()
  expect((await field()).validationMessage).toBe(date('invalid'))
  expect(onSubmit).not.toHaveBeenCalled()
  await user.clear(await field())
  await user.type(await field(), '28/02/2026')
  await send()

  expect(onSubmit).toHaveBeenCalledTimes(1)
})

it('may be left empty when it is not required', async () => {
  const onSubmit = vi.fn()
  const { user, onChange } = renderField({ onSubmit, initial: '2026-11-24' })

  await user.clear(await field())
  await user.click(screen.getByRole('button', { name: 'send' }))

  expect(onChange).toHaveBeenLastCalledWith('')
  expect(onSubmit).toHaveBeenCalledTimes(1)
})

it.each([
  ['31/10/2026', date('min', { date: '01/11/2026' })],
  ['01/11/2026', null],
  ['30/11/2026', null],
  ['01/12/2026', date('max', { date: '30/11/2026' })],
])('accepts %s or says what is wrong with it', async (text, problem) => {
  const onSubmit = vi.fn()
  const { user } = renderField({ onSubmit, min: '2026-11-01', max: '2026-11-30' })

  await user.type(await field(), text)
  await user.click(screen.getByRole('button', { name: 'send' }))

  expect(onSubmit).toHaveBeenCalledTimes(problem ? 0 : 1)
  if (problem) expect(await screen.findByText(problem)).toBeInTheDocument()
})

it('follows its value when it is changed from outside', async () => {
  const { user } = renderField({ initial: '2026-11-24' })

  await user.click(await screen.findByRole('button', { name: 'set' }))
  expect(await field()).toHaveValue('31/12/2026')
  await user.click(screen.getByRole('button', { name: 'clear' }))
  expect(await field()).toHaveValue('')
})

it('picks a day in a calendar in Spanish and gives the focus back', async () => {
  const { user, onChange } = renderField({ initial: '2026-11-24' })

  await user.click(await screen.findByRole('button', { name: date('open') }))
  expect(await screen.findByRole('button', { name: date('chooseMonth') })).toHaveTextContent(
    /noviembre 2026/i,
  )
  await user.click(screen.getByRole('button', { name: date('nextMonth') }))
  await user.click(await screen.findByRole('button', { name: '5 diciembre 2026' }))

  expect(onChange.mock.calls).toEqual([['2026-12-05']])
  expect(await field()).toHaveValue('05/12/2026')
  await waitFor(async () => expect(await field()).toHaveFocus())
  expect(screen.queryByRole('button', { name: date('nextMonth') })).toBeNull()
})

it('keeps the date when its day is picked again', async () => {
  const { user } = renderField({ initial: '2026-11-24' })

  await user.click(await screen.findByRole('button', { name: date('open') }))
  await user.click(await screen.findByRole('button', { name: '24 noviembre 2026' }))

  expect(await field()).toHaveValue('24/11/2026')
})

it('does not offer days out of its limits, and starts where there are some', async () => {
  const { user } = renderField({ min: '2027-03-10', max: '2027-03-20' })

  await user.click(await screen.findByRole('button', { name: date('open') }))

  expect(await screen.findByRole('button', { name: '9 marzo 2027' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '10 marzo 2027' })).toBeEnabled()
  expect(screen.getByRole('button', { name: '21 marzo 2027' })).toBeDisabled()
})

it('opens on today when there is no date, and closes with its button', async () => {
  const { user } = renderField()
  const button = await screen.findByRole('button', { name: date('open') })

  await user.click(button)
  expect(await screen.findByRole('button', { name: '23 noviembre 2026' })).toBeInTheDocument()
  expect(button).toHaveAttribute('aria-expanded', 'true')
  await user.click(button)

  await waitFor(() => expect(screen.queryByRole('button', { name: date('nextMonth') })).toBeNull())
})

it('closes with Escape without closing the window it is in', async () => {
  function InModal() {
    const [open, setOpen] = useState(false)
    return (
      <>
        <Button onClick={() => setOpen(true)}>open</Button>
        <Modal opened={open} onClose={() => setOpen(false)} title="Ventana">
          <Form initial="2026-11-24" />
        </Modal>
      </>
    )
  }
  renderApp(<InModal />, { me: makeMe() })
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'open' }))
  const modal = await screen.findByRole('dialog', { name: 'Ventana' })

  await user.click(within(modal).getByRole('button', { name: date('open') }))
  await screen.findByRole('button', { name: date('nextMonth') })
  await user.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('button', { name: date('nextMonth') })).toBeNull())
  expect(screen.getByRole('dialog', { name: 'Ventana' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Ventana' })).toBeNull())
})

it('stays open while other keys move through the calendar', async () => {
  const { user } = renderField({ initial: '2026-11-24' })

  await user.click(await screen.findByRole('button', { name: date('open') }))
  await user.click(await screen.findByRole('button', { name: date('nextMonth') }))
  await user.keyboard('{Shift}')

  expect(screen.getByRole('button', { name: date('nextMonth') })).toBeInTheDocument()
})
