import { fireEvent, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { expect, it, vi } from 'vitest'

import { renderApp, t } from '../../test/render'
import { SeriesChart } from './SeriesChart'

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

const POINTS = [
  { label: 'Ene', name: 'Enero', value: 1500 },
  { label: 'Feb', name: 'Febrero', value: 12500.5 },
  { label: 'Mar', name: 'Marzo', value: null },
]

function renderChart(target: number | null) {
  return renderApp(
    <SeriesChart title="Consumo" unit="kWh" points={POINTS} target={target} periodHeader="Mes" />,
    { me: null },
  )
}

it('draws a dot per value and the target as a dashed line', async () => {
  const { container } = renderChart(12000)

  await waitFor(() => expect(container.querySelectorAll('.recharts-line-dot')).toHaveLength(2))
  expect(container.querySelector('.recharts-reference-line-line')).toHaveAttribute(
    'stroke-dasharray',
    '6 4',
  )
})

it('names the month and the value with its unit in the tooltip', async () => {
  const { container } = renderChart(null)

  await waitFor(() => expect(container.querySelector('.recharts-line')).not.toBeNull())
  expect(container.querySelector('.recharts-reference-line')).toBeNull()
  fireEvent.mouseMove(container.querySelector('.recharts-wrapper')!, { clientX: 300, clientY: 50 })

  const tooltip = container.querySelector('.recharts-tooltip-wrapper')!
  await waitFor(() => expect(tooltip).toHaveTextContent('Febrero'))
  expect(tooltip).toHaveTextContent(`${t('environment.tracking.value')} : 12.500,5 kWh`)
})
