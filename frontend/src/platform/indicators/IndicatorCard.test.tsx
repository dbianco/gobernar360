import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { makeEvolution } from '../../test/fixtures'
import { renderApp, t } from '../../test/render'
import { IndicatorCard } from './IndicatorCard'

const DELAYED = t('overview.indicators.projects.delayed')

/** Six delayed projects today, five last month and eight a year ago; fewer is better. */
const delayed = (overrides = {}) =>
  makeEvolution('projects.delayed', 6, null, {
    higher_is_better: false,
    previous_value: 5,
    change_previous_month: 1,
    last_year_value: 8,
    change_last_year: -2,
    series: [8, 7, null, 7, 6, 6, 5, 5, 4, 5, 5, 6].map((value, index) => ({
      year: index < 7 ? 2025 : 2026,
      month: ((index + 5) % 12) + 1,
      value,
      target: index < 7 ? 5 : 4,
    })),
    ...overrides,
  })

function renderCard(indicator = delayed()) {
  renderApp(<IndicatorCard indicator={indicator} label={DELAYED} />, { me: null })
  return within(screen.getByText(DELAYED).closest('[data-indicator]') as HTMLElement)
}

it('shows the value and how it changed, judged by the direction of the indicator', () => {
  const card = renderCard()

  expect(card.getByText('6')).toBeInTheDocument()
  // One more delayed project is bad news, two fewer than a year ago good news.
  const lastMonth = card.getByText(t('indicators.vsPreviousMonth', { change: '+1' }))
  expect(lastMonth).toHaveAttribute('data-trend', 'worse')
  const lastYear = card.getByText(t('indicators.vsLastYear', { change: '\u22122' }))
  expect(lastYear).toHaveAttribute('data-trend', 'better')
})

it('draws the last twelve months with the target line', () => {
  const card = renderCard()

  const sparkline = card.getByRole('img', { name: t('indicators.sparkline', { name: DELAYED }) })
  // A month without a value splits the line in two; the target changes with the year.
  expect(sparkline.querySelectorAll('polyline:not([data-target-line])')).toHaveLength(2)
  expect(sparkline.querySelectorAll('[data-target-line]')).toHaveLength(1)
})

it('says when the target is missed and by how much', () => {
  const card = renderCard(delayed({ target: 4, deviation: -2, on_track: false }))

  expect(card.getByText(t('indicators.offTrack'))).toBeInTheDocument()
  expect(
    card.getByText(t('indicators.aboveTarget', { amount: '2', target: '4' })),
  ).toBeInTheDocument()
})

it('says when the target is met', () => {
  const card = renderCard(delayed({ target: 7, deviation: 1, on_track: true }))

  expect(card.getByText(t('indicators.onTrack'))).toBeInTheDocument()
  expect(
    card.getByText(t('indicators.belowTarget', { amount: '1', target: '7' })),
  ).toBeInTheDocument()
})

it('shows ratio changes and gaps in percentage points', () => {
  const label = t('overview.indicators.projects.budget_executed_ratio')
  renderApp(
    <IndicatorCard
      label={label}
      indicator={makeEvolution('projects.budget_executed_ratio', 0.4, 'ratio', {
        change_previous_month: -0.05,
        target: 0.5,
        deviation: -0.1,
        on_track: false,
      })}
    />,
    { me: null },
  )
  const card = within(screen.getByText(label).closest('[data-indicator]') as HTMLElement)

  expect(card.getByText('40 %')).toBeInTheDocument()
  expect(
    card.getByText(t('indicators.vsPreviousMonth', { change: '\u22125 p.p.' })),
  ).toBeInTheDocument()
  expect(
    card.getByText(t('indicators.belowTarget', { amount: '10 p.p.', target: '50 %' })),
  ).toBeInTheDocument()
})

it('says so when there is nothing to compare with and no target', () => {
  const card = renderCard(makeEvolution('projects.delayed', 6))

  expect(card.getByText(t('indicators.noPreviousMonth'))).toBeInTheDocument()
  expect(card.getByText(t('indicators.noLastYear'))).toBeInTheDocument()
  expect(card.getByText(t('indicators.noTarget'))).toBeInTheDocument()
})

it('does not judge a change when neither direction is better', () => {
  const label = t('overview.indicators.combined.deliveries_per_active_project')
  renderApp(
    <IndicatorCard
      label={label}
      indicator={makeEvolution('combined.deliveries_per_active_project', 2.5, null, {
        higher_is_better: null,
        change_previous_month: 0.5,
      })}
    />,
    { me: null },
  )
  const card = within(screen.getByText(label).closest('[data-indicator]') as HTMLElement)

  expect(card.getByText('2,5')).toBeInTheDocument()
  expect(
    card.getByText(t('indicators.vsPreviousMonth', { change: '+0,5' })),
  ).toHaveAttribute('data-trend', 'neutral')
  expect(card.queryByText(t('indicators.noTarget'))).not.toBeInTheDocument()
})

it('opens the twelve months with their target', async () => {
  const card = renderCard(delayed({ target: 4, deviation: -2, on_track: false }))

  await userEvent.click(card.getByRole('button', { name: t('indicators.open', { name: DELAYED }) }))
  const dialog = await screen.findByRole('dialog', { name: DELAYED })
  await userEvent.click(
    within(dialog).getByRole('button', { name: t('indicators.detail.showTable') }),
  )

  const rows = within(within(dialog).getByRole('table')).getAllByRole('row')
  expect(rows).toHaveLength(13)
  expect(within(rows[1]).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['8', '5'])
  expect(within(rows[3]).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['—', '5'])
  expect(rows[12]).toHaveTextContent(
    t('status.monthYear', { month: t('status.months.5'), year: 2026 }),
  )
  expect(within(rows[12]).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['6', '4'])
  expect(
    within(dialog).getByText(t('indicators.detail.lowerIsBetter'), { exact: false }),
  ).toBeInTheDocument()
  expect(
    within(dialog).getByText(t('indicators.detail.gapsNotReconstructible'), { exact: false }),
  ).toBeInTheDocument()
})

const about = (name: string) => t('help.about', { column: name })

it('explains what the indicator measures when its info icon is hovered', async () => {
  const card = renderCard()

  await userEvent.hover(card.getByRole('button', { name: about(DELAYED) }))

  expect(await screen.findByRole('tooltip')).toHaveTextContent(
    t('overview.descriptions.projects.delayed'),
  )
})

it('explains the indicator when its info icon gets keyboard focus', async () => {
  renderCard()

  await userEvent.tab()

  expect(screen.getByRole('button', { name: about(DELAYED) })).toHaveFocus()
  expect(await screen.findByRole('tooltip')).toHaveTextContent(
    t('overview.descriptions.projects.delayed'),
  )
})

it('does not open the detail when the info icon is clicked', async () => {
  const card = renderCard()

  await userEvent.click(card.getByRole('button', { name: about(DELAYED) }))

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('explains the indicator next to the title of its detail', async () => {
  const card = renderCard()
  await userEvent.click(card.getByRole('button', { name: t('indicators.open', { name: DELAYED }) }))
  const dialog = await screen.findByRole('dialog', { name: DELAYED })

  await userEvent.hover(within(dialog).getByRole('button', { name: about(DELAYED) }))

  expect(await screen.findByRole('tooltip')).toHaveTextContent(
    t('overview.descriptions.projects.delayed'),
  )
})

it('keeps its two icons together, alike, at the top of the card', () => {
  const card = renderCard()

  const info = card.getByRole('button', { name: about(DELAYED) })
  const chart = card.getByRole('button', { name: t('indicators.open', { name: DELAYED }) })
  expect(info.parentElement).toBe(chart.parentElement)
  expect(info.className).toBe(chart.className)
  const size = (button: HTMLElement) => button.querySelector('svg')?.getAttribute('width')
  expect(size(info)).toBe(size(chart))
})

it('says that its chart icon shows the last twelve months', async () => {
  const card = renderCard()

  await userEvent.hover(card.getByRole('button', { name: t('indicators.open', { name: DELAYED }) }))

  expect(await screen.findByRole('tooltip')).toHaveTextContent(t('indicators.openHint'))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('says when the value is exactly at the target and did not change', () => {
  const card = renderCard(
    delayed({ target: 6, deviation: 0, on_track: true, change_previous_month: 0 }),
  )

  expect(card.getByText(t('indicators.atTarget', { target: '6' }))).toBeInTheDocument()
  expect(card.getByText(t('indicators.vsPreviousMonth', { change: '0' }))).toHaveAttribute(
    'data-trend',
    'same',
  )
})

it('shows the target alone while there is no value to compare', () => {
  const card = renderCard(delayed({ value: null, target: 4 }))

  expect(card.getByText(t('indicators.targetOf', { target: '4' }))).toBeInTheDocument()
  expect(card.queryByText(t('indicators.onTrack'))).not.toBeInTheDocument()
  expect(card.queryByText(t('indicators.offTrack'))).not.toBeInTheDocument()
})

it('opens from anywhere on the card and closes again', async () => {
  const card = renderCard()

  await userEvent.click(card.getByText('6'))
  const dialog = await screen.findByRole('dialog', { name: DELAYED })
  await userEvent.keyboard('{Escape}')

  await waitFor(() => expect(dialog).not.toBeInTheDocument())
})

it('has no info icon for an indicator nobody described', () => {
  const card = renderCard(delayed({ key: 'projects.not_described' }))

  expect(card.queryByRole('button', { name: about(DELAYED) })).not.toBeInTheDocument()
  expect(card.getByRole('button', { name: t('indicators.open', { name: DELAYED }) })).toBeVisible()
})
