import { act, renderHook } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { fitPage, normalize, PAGE_SIZES, useLocalTable, usePaging } from './paging'

it('starts with the smallest page size, or the one this browser chose for the table', () => {
  expect(renderHook(() => usePaging('people')).result.current.limit).toBe(10)

  window.localStorage.setItem('g360.pageSize.people', '50')
  expect(renderHook(() => usePaging('people')).result.current.limit).toBe(50)
  expect(renderHook(() => usePaging('actors')).result.current.limit).toBe(10)

  window.localStorage.setItem('g360.pageSize.people', '7')
  expect(renderHook(() => usePaging('people')).result.current.limit).toBe(10)
})

it('remembers a new page size and starts again from the first page', () => {
  const { result } = renderHook(() => usePaging('people'))
  act(() => result.current.setOffset(30))

  act(() => result.current.pager(100).onLimitChange(20))

  expect([result.current.limit, result.current.offset]).toEqual([20, 0])
  expect(window.localStorage.getItem('g360.pageSize.people')).toBe('20')
  expect(result.current.pager(100)).toMatchObject({
    total: 100,
    limit: 20,
    offset: 0,
    pageSizes: PAGE_SIZES,
  })
})

it('goes back to the first page on restart', () => {
  const { result } = renderHook(() => usePaging('people'))
  act(() => result.current.pager(100).onChange(40))
  expect(result.current.offset).toBe(40)

  act(() => result.current.restart())

  expect(result.current.offset).toBe(0)
})

function fitted(
  offset: number,
  data: { items: unknown[]; total: number } | undefined,
  placeholder = false,
) {
  const { result } = renderHook(() => {
    const paging = usePaging('people')
    fitPage(paging, { data, isPlaceholderData: placeholder })
    return paging
  })
  act(() => result.current.setOffset(offset))
  return result.current.offset
}

it('moves to the last page that has rows when the current one came back empty', () => {
  expect(fitted(40, { items: [], total: 25 })).toBe(20)
  expect(fitted(40, { items: [], total: 30 })).toBe(20)
  expect(fitted(40, { items: [], total: 31 })).toBe(30)
  expect(fitted(40, { items: [], total: 0 })).toBe(0)
})

it('stays where it is while loading, with rows, or on an empty last page', () => {
  expect(fitted(40, undefined)).toBe(40)
  expect(fitted(40, { items: [], total: 25 }, true)).toBe(40)
  expect(fitted(40, { items: [1], total: 45 })).toBe(40)
  expect(fitted(40, { items: [], total: 45 })).toBe(40)
})

it('compares text without case or accents', () => {
  expect(normalize('Pérez MUÑOZ Ñandú')).toBe('perez munoz nandu')
})

const NAMES = Array.from({ length: 25 }, (_, index) => ({ name: `Área ${index + 1}` }))

it('pages a whole list in the browser', () => {
  const { result } = renderHook(() => useLocalTable('areas', NAMES, (item) => item.name))

  expect(result.current.rows.map((item) => item.name)).toEqual(
    NAMES.slice(0, 10).map((item) => item.name),
  )
  expect([result.current.hasItems, result.current.total]).toEqual([true, 25])
  act(() => result.current.pager.onChange(20))
  expect(result.current.rows.map((item) => item.name)).toEqual([
    'Área 21',
    'Área 22',
    'Área 23',
    'Área 24',
    'Área 25',
  ])
})

it('keeps the rows that have every word searched, from the first page', () => {
  const { result } = renderHook(() => useLocalTable('areas', NAMES, (item) => item.name))
  act(() => result.current.pager.onChange(20))

  act(() => result.current.setQuery('  AREA   2 '))

  expect(result.current.query).toBe('  AREA   2 ')
  expect(result.current.rows.map((item) => item.name)).toEqual([
    'Área 2',
    'Área 12',
    'Área 20',
    'Área 21',
    'Área 22',
    'Área 23',
    'Área 24',
    'Área 25',
  ])
  expect(result.current.pager.offset).toBe(0)
})

it('shows the last page when rows went away, and says when there is nothing at all', () => {
  const { result, rerender } = renderHook(
    ({ items }) => useLocalTable('areas', items, (item) => item.name),
    { initialProps: { items: NAMES as { name: string }[] | undefined } },
  )
  act(() => result.current.pager.onChange(20))

  rerender({ items: NAMES.slice(0, 15) })
  expect(result.current.pager.offset).toBe(10)
  expect(result.current.rows).toHaveLength(5)

  rerender({ items: undefined })
  expect([result.current.hasItems, result.current.total, result.current.rows]).toEqual([
    false,
    0,
    [],
  ])
})

it('follows a search typed elsewhere, from the first page', () => {
  const { result, rerender } = renderHook(
    ({ search }) => useLocalTable('areas', NAMES, (item) => item.name, search),
    { initialProps: { search: '' } },
  )
  act(() => result.current.pager.onChange(10))

  rerender({ search: '1' })

  expect(result.current.query).toBe('1')
  expect(result.current.pager.offset).toBe(0)
  expect(result.current.total).toBe(12)
})

it('works without browser storage, forgetting the page size', () => {
  const blocked = () => {
    throw new DOMException('The operation is insecure.', 'SecurityError')
  }
  const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(blocked)
  const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(blocked)
  try {
    const { result } = renderHook(() => usePaging('people'))
    expect(result.current.limit).toBe(10)

    act(() => result.current.pager(100).onLimitChange(20))

    expect(result.current.limit).toBe(20)
  } finally {
    getItem.mockRestore()
    setItem.mockRestore()
  }
})
