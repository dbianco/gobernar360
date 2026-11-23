import { Button } from '@mantine/core'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it } from 'vitest'

import { makeMe } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { useConfirm } from './confirmContext'

function Asker() {
  const confirm = useConfirm()
  const [answer, setAnswer] = useState('none')
  return (
    <>
      <Button
        onClick={async () => {
          const accepted = await confirm({
            title: 'Borrar registro',
            message: '¿Borrar el registro 7?',
            confirmLabel: 'Borrar',
            danger: true,
          })
          setAnswer(String(accepted))
        }}
      >
        Preguntar
      </Button>
      <p>Respuesta: {answer}</p>
    </>
  )
}

async function ask() {
  const user = userEvent.setup()
  renderApp(<Asker />, { me: makeMe() })
  await user.click(await screen.findByRole('button', { name: 'Preguntar' }))
  const dialog = await screen.findByRole('dialog', { name: 'Borrar registro' })
  return { user, dialog }
}

it('asks in a modal window and answers yes when accepted', async () => {
  const { user, dialog } = await ask()

  expect(within(dialog).getByText('¿Borrar el registro 7?')).toBeInTheDocument()
  await user.click(within(dialog).getByRole('button', { name: 'Borrar' }))

  expect(await screen.findByText('Respuesta: true')).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('answers no when cancelled', async () => {
  const { user, dialog } = await ask()

  await user.click(within(dialog).getByRole('button', { name: t('app.cancel') }))

  expect(await screen.findByText('Respuesta: false')).toBeInTheDocument()
})

it('answers no when closed with Escape, and starts on the safe button', async () => {
  const { user, dialog } = await ask()

  await waitFor(() =>
    expect(within(dialog).getByRole('button', { name: t('app.cancel') })).toHaveFocus(),
  )
  await user.keyboard('{Escape}')

  expect(await screen.findByText('Respuesta: false')).toBeInTheDocument()
})

function PlainAsker() {
  const confirm = useConfirm()
  const [answer, setAnswer] = useState('none')
  return (
    <>
      <Button
        onClick={async () =>
          setAnswer(String(await confirm({ message: <strong>Se enviará a 3 personas.</strong> })))
        }
      >
        Preguntar
      </Button>
      <p>Respuesta: {answer}</p>
    </>
  )
}

it('asks with the usual title and button unless told otherwise, and shows any content', async () => {
  const user = userEvent.setup()
  renderApp(<PlainAsker />, { me: makeMe() })

  await user.click(await screen.findByRole('button', { name: 'Preguntar' }))
  const dialog = await screen.findByRole('dialog', { name: t('app.confirmTitle') })
  expect(within(dialog).getByText('Se enviará a 3 personas.').tagName).toBe('STRONG')
  const accept = within(dialog).getByRole('button', { name: t('app.confirm') })
  expect(accept).not.toHaveAttribute('data-variant', 'danger')
  await user.click(accept)

  expect(await screen.findByText('Respuesta: true')).toBeInTheDocument()
})
