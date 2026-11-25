/** The list with the element at `index` moved one place up (-1) or down (1). */
export function moved<T>(list: T[], index: number, by: -1 | 1): T[] {
  const next = [...list]
  const [element] = next.splice(index, 1)
  next.splice(index + by, 0, element)
  return next
}
