import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { expect, it, vi } from 'vitest'

import { makeEvolution } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { IndicatorDetail } from './IndicatorDetail'
import type { IndicatorEvolution } from './types'

// jsdom has no layout: give the chart the size its container would.
vi.mock('recharts', async (importOriginal) => {
  const recharts = await importOriginal<typeof import('recharts')>()
  return {
    ...recharts,
    ResponsiveContainer: (props: { children: ReactElement }) => (
      <recharts.ResponsiveContainer width={600} height={280}>
        {props.children}
      </recharts.ResponsiveContainer>
    ),
  }
})

const LABEL = t('overview.indicators.projects.budget_executed_ratio')
const detail = (key: string, options = {}) => t(`indicators.detail.${key}`, options)

function executed(overrides: Partial<IndicatorEvolution> = {}) {
  const base = makeEvolution('projects.budget_executed_ratio', 0.4, 'ratio')
  return {
    ...base,
    previous_value: 0.38,
    change_previous_month: 0.02,
    last_year_value: 0.45,
    change_last_year: -0.05,
    target: 0.5,
    on_track: false,
    series: base.series.map((point, index) => ({
      ...point,
      value: 0.29 + index / 100,
      target: 0.5,
    })),
    ...overrides,
  }
}

async function openDetail(indicator = executed()) {
  const onClose = vi.fn()
  renderApp(<IndicatorDetail indicator={indicator} label={LABEL} opened onClose={onClose} />, {
    me: null,
  })
  return { dialog: within(await screen.findByRole('dialog', { name: LABEL })), onClose }
}

it('compares today with the month before, a year ago and the target', async () => {
  const { dialog } = await openDetail()

  expect(dialog.getByText(detail('change', { change: '+2 p.p.' }))).toBeInTheDocument()
  expect(dialog.getByText(detail('change', { change: '\u22125 p.p.' }))).toBeInTheDocument()
  expect(dialog.getByText(detail('target', { year: 2026 }))).toBeInTheDocument()
  expect(dialog.getByText(t('indicators.offTrack'))).toBeInTheDocument()
  // Every month has a value: nothing to explain after the direction.
  expect(dialog.getByText(detail('higherIsBetter'))).toBeInTheDocument()
})

it('leaves out the comparisons there is nothing for', async () => {
  const { dialog } = await openDetail(
    makeEvolution('combined.deliveries_per_active_project', 2.5, null, {
      higher_is_better: null,
      reconstructible: true,
    }),
  )

  expect(dialog.queryByText(t('indicators.offTrack'))).not.toBeInTheDocument()
  expect(dialog.queryByText(t('indicators.onTrack'))).not.toBeInTheDocument()
  // Its past months can be rebuilt, so the gaps mean something else.
  expect(dialog.getByText(`${detail('neutral')} ${detail('gaps')}`)).toBeInTheDocument()
})

it('says when the target is met, and closes', async () => {
  const { dialog, onClose } = await openDetail(executed({ on_track: true, target: 0.3 }))

  expect(dialog.getByText(t('indicators.onTrack'))).toBeInTheDocument()
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
  await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
})

it('draws the months with their values in the unit of the indicator', async () => {
  await openDetail()
  const chart = () => document.querySelector('.recharts-wrapper') as HTMLElement

  await waitFor(() => expect(chart().querySelectorAll('.recharts-line')).toHaveLength(2))
  const axis = [...chart().querySelectorAll('.recharts-yAxis-tick-labels text')]
  expect(axis.length).toBeGreaterThan(0)
  for (const tick of axis) expect(tick.textContent).toMatch(/ %$/)

  fireEvent.mouseMove(chart(), { clientX: 580, clientY: 100 })
  const tooltip = () => document.querySelector('.recharts-tooltip-wrapper') as HTMLElement
  const june = t('status.monthYear', { month: t('status.months.6'), year: 2026 })
  await waitFor(() => expect(tooltip()).toHaveTextContent(june))
  expect(tooltip()).toHaveTextContent('40 %')
  expect(tooltip()).toHaveTextContent('50 %')
})

it('draws no target line for an indicator without one', async () => {
  const series = executed().series.map((point) => ({ ...point, target: null }))
  await openDetail(executed({ series, target: null, on_track: null }))

  await waitFor(() => expect(document.querySelectorAll('.recharts-line')).toHaveLength(1))
})
