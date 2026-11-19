/** 30711111118 -> 30-71111111-8 */
export function formatCuit(cuit: string): string {
  return cuit.length === 11 ? `${cuit.slice(0, 2)}-${cuit.slice(2, 10)}-${cuit.slice(10)}` : cuit
}

/** 12345678 -> 12.345.678 */
export function formatDni(dni: string | null): string {
  return dni ? dni.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '—'
}

/** Today's date as YYYY-MM-DD in the browser's time zone. */
export function todayIso(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}
