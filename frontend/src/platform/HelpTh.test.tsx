import { Table } from '@mantine/core'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { renderApp, t } from '../test/render'
import { HelpTh } from './HelpTh'

function renderHeader() {
  renderApp(
    <Table>
      <Table.Thead>
        <Table.Tr>
          <HelpTh help="Agrupa las variables dentro de Agua." ta="right">
            Subcategoría
          </HelpTh>
        </Table.Tr>
      </Table.Thead>
    </Table>,
    { me: null },
  )
  return screen.getByRole('button', { name: t('help.about', { column: 'Subcategoría' }) })
}

it('keeps the column name as the header and passes cell props through', () => {
  renderHeader()

  const header = screen.getByRole('columnheader')
  expect(header).toHaveTextContent('Subcategoría')
  expect(header).toHaveStyle({ textAlign: 'right' })
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
})

it('gives the info icon the explanation as its description, for screen readers', () => {
  const info = renderHeader()

  expect(info).toHaveAccessibleDescription('Agrupa las variables dentro de Agua.')
})

it('explains the column when the info icon is hovered', async () => {
  const info = renderHeader()

  await userEvent.hover(info)

  expect(await screen.findByRole('tooltip')).toHaveTextContent(
    'Agrupa las variables dentro de Agua.',
  )
})

it('explains the column when the info icon gets keyboard focus', async () => {
  renderHeader()

  await userEvent.tab()

  expect(await screen.findByRole('tooltip')).toHaveTextContent(
    'Agrupa las variables dentro de Agua.',
  )
})
