import { waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { expect, it, vi } from 'vitest'

import { renderApp } from '../../test/render'
import { SeriesChart } from './SeriesChart'

const tooltips: { labelFormatter: (label: unknown, items: unknown[]) => string }[] = []

vi.mock('recharts', async (original) => {
  const recharts = await original<typeof import('recharts')>()
  return {
    ...recharts,
    ResponsiveContainer: ({ children }: { children: ReactElement }) => (
      <recharts.ResponsiveContainer width={600} height={300}>
        {children}
      </recharts.ResponsiveContainer>
    ),
    Tooltip: (props: (typeof tooltips)[number]) => {
      tooltips.push(props)
      return null
    },
  }
})

it('titles the tooltip with the period, or with nothing over no point', async () => {
  renderApp(
    <SeriesChart
      title="Consumo"
      unit="kWh"
      points={[{ label: 'Ene', name: 'Enero', value: 3 }]}
      target={null}
      periodHeader="Mes"
    />,
    { me: null },
  )

  await waitFor(() => expect(tooltips).not.toHaveLength(0))
  const [{ labelFormatter }] = tooltips
  expect(labelFormatter(1, [{ payload: { name: 'Enero' } }])).toBe('Enero')
  expect(labelFormatter(1, [])).toBe('')
  expect(labelFormatter(1, [{}])).toBe('')
})
