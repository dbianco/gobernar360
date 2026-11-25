import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../test/fixtures'
import { choosePerson } from '../test/person'
import { renderApp, t } from '../test/render'
import { PeopleSelect, PersonSelect } from './PersonSelect'

const PEOPLE = [
  { id: 'u-1', full_name: 'Ana Gómez' },
  { id: 'u-2', full_name: 'Leo Paz' },
  { id: 'u-3', full_name: 'María José Núñez' },
  { id: 'u-4', full_name: 'José Paz' },
]
const box = () => screen.findByRole<HTMLInputElement>('combobox', { name: 'Persona' })
const offered = () => screen.getAllByRole('option').map((option) => option.textContent)

function renderOne(props: { initial?: string; required?: boolean; placeholder?: string } = {}) {
  const onChange = vi.fn()
  function One() {
    const [value, setValue] = useState(props.initial ?? '')
    return (
      <PersonSelect
        label="Persona"
        required={props.required}
        placeholder={props.placeholder}
        value={value}
        onChange={(id) => {
          setValue(id)
          onChange(id)
        }}
        people={PEOPLE}
      />
    )
  }
  renderApp(<One />, { me: makeMe() })
  return { onChange, user: userEvent.setup() }
}

it('narrows the list while typing, ignoring case and accents, words in any order', async () => {
  const { user } = renderOne()

  await user.click(await box())
  expect(offered()).toEqual(PEOPLE.map((person) => person.full_name))
  await user.type(await box(), 'paz')
  expect(offered()).toEqual(['Leo Paz', 'José Paz'])
  await user.type(await box(), ' jose')
  expect(offered()).toEqual(['José Paz'])
  await user.clear(await box())
  await user.type(await box(), 'NUNEZ mar')
  expect(offered()).toEqual(['María José Núñez'])
  await user.type(await box(), 'x')
  expect(screen.getByText(t('app.noMatches'))).toBeInTheDocument()
})

it('chooses one, and with the keyboard too', async () => {
  const { user, onChange } = renderOne()

  await choosePerson(user, await box(), 'gomez', 'Ana Gómez')
  expect(await box()).toHaveValue('Ana Gómez')
  await user.clear(await box())
  await user.type(await box(), 'leo{ArrowDown}{Enter}')

  expect(onChange.mock.calls).toEqual([['u-1'], ['u-2']])
  expect(await box()).toHaveValue('Leo Paz')
})

it('keeps who was chosen when what is typed is left without choosing', async () => {
  const { user, onChange } = renderOne({ initial: 'u-2' })

  await user.clear(await box())
  await user.type(await box(), 'ana')
  await user.tab()

  expect(await box()).toHaveValue('Leo Paz')
  expect(onChange).not.toHaveBeenCalled()
})

it('goes back to nobody only when nobody is required', async () => {
  const { user, onChange } = renderOne({ initial: 'u-2', placeholder: 'Todos' })

  // With the keyboard.
  await user.click(await box())
  await user.keyboard('{Escape}')
  await user.tab()
  expect(screen.getByRole('button', { name: t('app.person.clear') })).toHaveFocus()
  await user.keyboard('{Enter}')

  expect(onChange).toHaveBeenCalledWith('')
  expect(await box()).toHaveAttribute('placeholder', 'Todos')
})

it('has no way back to nobody when somebody is required', async () => {
  renderOne({ initial: 'u-2', required: true })

  expect(await box()).toBeRequired()
  expect(await box()).toHaveAttribute('placeholder', t('app.person.choose'))
  expect(screen.queryByRole('button', { name: t('app.person.clear') })).toBeNull()
})

it('chooses several people, each once', async () => {
  const onChange = vi.fn()
  function Several() {
    const [value, setValue] = useState<string[]>([])
    return (
      <PeopleSelect
        label="Persona"
        description="Quiénes"
        value={value}
        onChange={(ids) => {
          setValue(ids)
          onChange(ids)
        }}
        people={PEOPLE}
      />
    )
  }
  renderApp(<Several />, { me: makeMe() })
  const user = userEvent.setup()
  expect(await box()).toHaveAttribute('placeholder', t('app.person.chooseSeveral'))

  await choosePerson(user, await box(), 'nunez', 'María José Núñez')
  // Out of the way of what is below.
  await waitFor(() => expect(screen.queryByRole('option')).toBeNull())
  await choosePerson(user, await box(), 'gomez', 'Ana Gómez')
  await waitFor(() => expect(screen.queryByRole('option')).toBeNull())
  await user.click(await box())
  await user.clear(await box())

  expect(onChange).toHaveBeenLastCalledWith(['u-3', 'u-1'])
  expect(offered()).toEqual(['Leo Paz', 'José Paz'])
})
