import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { expect, it, vi } from 'vitest'

import { renderApp, t } from '../test/render'
import { CountBarChart } from './CountBarChart'

// jsdom lays nothing out: give the chart a size so that it draws.
vi.mock('recharts', async (importOriginal) => {
  const recharts = await importOriginal<typeof import('recharts')>()
  return {
    ...recharts,
    ResponsiveContainer: ({ children }: { children: ReactElement }) => (
      <recharts.ResponsiveContainer width={600} height={300}>
        {children}
      </recharts.ResponsiveContainer>
    ),
  }
})

const ROWS = [
  { name: 'Alimentos', count: 4 },
  { name: 'Hábitat', count: 1 },
]

it('draws a bar per row and names the value in the tooltip', async () => {
  const { container } = renderApp(
    <CountBarChart title="Por categoría" valueLabel="Entregas" rows={ROWS} />,
    { me: null },
  )

  await waitFor(() => expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(2))
  fireEvent.mouseMove(container.querySelector('.recharts-wrapper')!, { clientX: 300, clientY: 10 })

  const tooltip = container.querySelector('.recharts-tooltip-wrapper')!
  await waitFor(() => expect(tooltip).toHaveTextContent('Alimentos'))
  expect(tooltip).toHaveTextContent('Entregas : 4')
})

it('shows the same numbers as a table', async () => {
  renderApp(<CountBarChart title="Por categoría" valueLabel="Entregas" rows={ROWS} />, {
    me: null,
  })
  const user = userEvent.setup()

  await user.click(screen.getByRole('button', { name: t('app.chart.showTable') }))

  expect(screen.getByRole('row', { name: /Hábitat/ })).toHaveTextContent('1')
  await user.click(screen.getByRole('button', { name: t('app.chart.showChart') }))
  expect(screen.queryByRole('table')).toBeNull()
})

it('says when there is nothing to draw', () => {
  renderApp(<CountBarChart title="Por categoría" valueLabel="Entregas" rows={[]} />, {
    me: null,
  })

  expect(screen.getByText(t('app.chart.noData'))).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: t('app.chart.showTable') })).toBeNull()
})
