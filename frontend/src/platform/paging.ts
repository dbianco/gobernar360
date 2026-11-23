import { useState } from 'react'

/** Page sizes every table offers. */
export const PAGE_SIZES = [10, 20, 50]

function storedSize(key: string): number {
  const stored = Number(window.localStorage.getItem(`g360.pageSize.${key}`))
  return PAGE_SIZES.includes(stored) ? stored : PAGE_SIZES[0]
}

/**
 * Page size and position of one table. The size a person picks is remembered per table
 * (`key`) in this browser; changing it, or the search, starts again from the first page.
 */
export function usePaging(key: string) {
  const [limit, setLimitState] = useState(() => storedSize(key))
  const [offset, setOffset] = useState(0)

  function setLimit(size: number) {
    window.localStorage.setItem(`g360.pageSize.${key}`, String(size))
    setLimitState(size)
    setOffset(0)
  }

  return {
    limit,
    offset,
    setOffset,
    restart: () => setOffset(0),
    /** Props for <Pager>. */
    pager: (total: number) => ({
      total,
      limit,
      offset,
      onChange: setOffset,
      pageSizes: PAGE_SIZES,
      onLimitChange: setLimit,
    }),
  }
}

/**
 * Call after loading a page of a list the API paginates: when the page came back empty
 * because the last rows went away (deleted, or no longer matching), go to the last page
 * that has rows. Sets state while rendering, which React allows for derived state.
 */
export function fitPage(
  paging: ReturnType<typeof usePaging>,
  query: { data?: { items: unknown[]; total: number }; isPlaceholderData: boolean },
) {
  const page = query.data
  // While the next page loads, the previous one is still on screen: not a real answer.
  if (!page || query.isPlaceholderData || page.items.length > 0 || paging.offset === 0) return
  const last = Math.max(0, Math.ceil(page.total / paging.limit) - 1) * paging.limit
  if (last !== paging.offset) paging.setOffset(last)
}

/** Lowercase without accents, so "perez" finds "Pérez" as the server's searches do. */
export function normalize(text: string): string {
  return text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
}

/**
 * Search and paging, in the browser, of a list the API returns whole (catalogs, the
 * projects of a term...). Every word typed must appear in `text(item)`.
 *
 * `search` lets one search box drive several tables; without it the table keeps its own.
 */
export function useLocalTable<T>(
  key: string,
  items: T[] | undefined,
  text: (item: T) => string,
  search?: string,
) {
  const paging = usePaging(key)
  const [ownQuery, setQueryState] = useState('')
  const query = search ?? ownQuery
  // A different search starts from the first page, also when it comes from outside.
  const [searched, setSearched] = useState(query)
  if (searched !== query) {
    setSearched(query)
    paging.restart()
  }
  const words = normalize(query).split(/\s+/).filter(Boolean)
  // Cheap enough to redo on every render: these lists are catalogs and plans, not logs.
  const matching = (items ?? []).filter((item) => {
    const haystack = normalize(text(item))
    return words.every((word) => haystack.includes(word))
  })
  // After a deletion the page may be past the end: show the last one instead.
  const lastPage = Math.max(0, Math.ceil(matching.length / paging.limit) - 1) * paging.limit
  const offset = Math.min(paging.offset, lastPage)

  return {
    query,
    setQuery: (value: string) => {
      setQueryState(value)
      paging.restart()
    },
    /** The rows of the current page. */
    rows: matching.slice(offset, offset + paging.limit),
    /** Whether the list has anything at all, before searching. */
    hasItems: (items?.length ?? 0) > 0,
    /** How many rows match the search. */
    total: matching.length,
    pager: { ...paging.pager(matching.length), offset },
  }
}
