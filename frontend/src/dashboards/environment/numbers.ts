// Numbers are written the Argentine way: comma for decimals, optional dots every three
// digits. A lone dot ("1.5", "1500.5") is rejected rather than guessed at, because
// reading "33.000" as thirty-three would silently store the wrong figure.
const PLAIN = /^-?\d+(,\d{1,4})?$/
const GROUPED = /^-?\d{1,3}(\.\d{3})+(,\d{1,4})?$/

/**
 * What the person typed, as the API wants it: `null` for an empty field, a dotted
 * decimal string for a number, `undefined` when it is not a number.
 */
export function parseNumber(typed: string): string | null | undefined {
  const text = typed.trim()
  if (text === '') return null
  if (!PLAIN.test(text) && !GROUPED.test(text)) return undefined
  return text.replaceAll('.', '').replace(',', '.')
}

/** A stored number as the person would type it back. */
export const numberText = (value: number | null | undefined) =>
  value == null ? '' : String(value).replace('.', ',')
