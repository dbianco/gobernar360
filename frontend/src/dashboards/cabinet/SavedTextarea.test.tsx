import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it, vi } from 'vitest'

import { makeMe } from '../../test/fixtures'
import { renderApp } from '../../test/render'
import { SavedTextarea } from './SavedTextarea'

const box = () => screen.findByRole('textbox', { name: 'Notas' })

function renderNotes(saved = 'Guardado') {
  const onSave = vi.fn()
  function Notes() {
    const [value, setValue] = useState(saved)
    return (
      <>
        <SavedTextarea label="Notas" saved={value} onSave={onSave} />
        <button onClick={() => setValue('De otra persona')}>other</button>
        <button onClick={() => setValue('Mío')}>mine</button>
      </>
    )
  }
  renderApp(<Notes />, { me: makeMe() })
  return { onSave, user: userEvent.setup() }
}

it('saves what was typed on leaving, and nothing when only spaces changed', async () => {
  const { onSave, user } = renderNotes()

  await user.type(await box(), '  ')
  await user.tab()
  expect(onSave).not.toHaveBeenCalled()
  await user.type(await box(), 'y más')
  await user.tab()

  expect(onSave.mock.calls).toEqual([['Guardado  y más']])
})

it('follows what others save while nothing is typed', async () => {
  const { user } = renderNotes()

  await user.click(await screen.findByRole('button', { name: 'other' }))

  expect(await box()).toHaveValue('De otra persona')
})

it('keeps what was typed when others save something else meanwhile', async () => {
  const { onSave, user } = renderNotes()
  await user.clear(await box())
  await user.type(await box(), 'Mío')

  await user.click(await screen.findByRole('button', { name: 'other' }))

  expect(await box()).toHaveValue('Mío')
  expect(onSave).toHaveBeenCalledWith('Mío')
  // Once saved it is what others see too, and it is followed again.
  await user.click(screen.getByRole('button', { name: 'mine' }))
  await user.click(screen.getByRole('button', { name: 'other' }))
  expect(await box()).toHaveValue('De otra persona')
})
