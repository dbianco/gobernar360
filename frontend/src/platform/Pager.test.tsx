import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { renderApp, t } from '../test/render'
import { Pager } from './Pager'

function renderPager(props: Partial<Parameters<typeof Pager>[0]> = {}) {
  const handlers = { onChange: vi.fn(), onLimitChange: vi.fn() }
  renderApp(<Pager total={45} limit={10} offset={20} {...handlers} {...props} />, { me: null })
  return handlers
}

it('says which rows are shown and moves a page back or forward', async () => {
  const { onChange } = renderPager()
  const user = userEvent.setup()

  expect(
    screen.getByText(t('app.pager.range', { from: 21, to: 30, total: 45 })),
  ).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: t('app.pager.previous') }))
  await user.click(screen.getByRole('button', { name: t('app.pager.next') }))

  expect(onChange.mock.calls).toEqual([[10], [30]])
})

it('cannot go before the first page or after the last one', () => {
  renderPager({ offset: 0 })
  expect(screen.getByRole('button', { name: t('app.pager.previous') })).toBeDisabled()
  expect(screen.getByRole('button', { name: t('app.pager.next') })).toBeEnabled()
})

it('cannot go past the last page, whose range ends at the total', () => {
  renderPager({ offset: 40 })

  expect(
    screen.getByText(t('app.pager.range', { from: 41, to: 45, total: 45 })),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: t('app.pager.next') })).toBeDisabled()
  expect(screen.getByRole('button', { name: t('app.pager.previous') })).toBeEnabled()
})

it('offers the page sizes and says which one is chosen', async () => {
  const { onLimitChange } = renderPager({ pageSizes: [10, 20, 50] })
  const user = userEvent.setup()
  const sizes = screen.getByRole('combobox', { name: t('app.pager.pageSize') })

  expect(sizes).toHaveValue('10')
  await user.selectOptions(sizes, '50')

  expect(onLimitChange).toHaveBeenCalledWith(50)
})

it('is hidden while everything fits in the smallest page', () => {
  renderPager({ total: 10, offset: 0, pageSizes: [10, 20, 50], limit: 20 })
  expect(screen.queryByRole('button', { name: t('app.pager.next') })).toBeNull()
})

it('stays while a page past the first is shown, even when the rest fits', () => {
  renderPager({ total: 10, offset: 10 })
  expect(screen.getByRole('button', { name: t('app.pager.previous') })).toBeEnabled()
})

it('shows the range of an empty list as empty', () => {
  renderPager({ total: 0, offset: 10 })
  expect(screen.getByText(t('app.pager.range', { from: 0, to: 0, total: 0 }))).toBeInTheDocument()
})
