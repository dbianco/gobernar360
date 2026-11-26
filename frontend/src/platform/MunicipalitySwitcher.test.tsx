import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeMe, NOETINGER, SAIRA } from '../test/fixtures'
import { renderApp, t } from '../test/render'
import { useAuth } from './authContext'
import {
  MunicipalityChooser,
  MunicipalitySwitcher,
  SuspendedMunicipality,
} from './MunicipalitySwitcher'

/** Says once it is known who is signed in. */
function Known() {
  const { isLoading } = useAuth()
  return isLoading ? null : <p>known</p>
}

it('offers nothing to somebody who is not signed in', async () => {
  renderApp(
    <>
      <Known />
      <MunicipalitySwitcher />
      <MunicipalityChooser />
      <SuspendedMunicipality />
    </>,
    { me: null },
  )

  await screen.findByText('known')
  expect(screen.queryByLabelText(t('nav.municipality'))).not.toBeInTheDocument()
  expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual([
    t('municipality.checkAgain'),
  ])
})

it('lists the municipalities one can choose and names the suspended ones', async () => {
  const me = makeMe({ municipalities: [NOETINGER], active: null, suspended: [SAIRA] })
  renderApp(<MunicipalityChooser />, { me })

  expect(await screen.findByRole('button', { name: NOETINGER.name })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: SAIRA.name })).not.toBeInTheDocument()
  expect(
    screen.getByText(t('municipality.suspendedOthers', { names: SAIRA.name, count: 1 })),
  ).toBeInTheDocument()
})

it('shows the municipality one works in', async () => {
  const me = makeMe({ municipalities: [NOETINGER, SAIRA], active: SAIRA.id })
  renderApp(<MunicipalitySwitcher />, { me })

  const select = await screen.findByRole('combobox', { name: t('nav.municipality') })
  await waitFor(() => expect(select).toHaveValue(SAIRA.name))
  await userEvent.click(select)
  expect(await screen.findByRole('option', { name: NOETINGER.name })).toBeInTheDocument()
})
