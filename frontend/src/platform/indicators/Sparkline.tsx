import type { SeriesPoint } from './types'

const WIDTH = 132
const HEIGHT = 32
const PAD = 3
const LINE = 'var(--mantine-primary-color-filled)'
const TARGET = 'var(--mantine-color-dimmed)'

type XY = [number, number]

/** Consecutive runs of points with a value; a month without one breaks the line. */
function runs(values: (number | null)[], position: (index: number, value: number) => XY): XY[][] {
  const result: XY[][] = []
  let current: XY[] = []
  values.forEach((value, index) => {
    if (value === null) {
      if (current.length) result.push(current)
      current = []
    } else {
      current.push(position(index, value))
    }
  })
  if (current.length) result.push(current)
  return result
}

const toPoints = (run: XY[]) => run.map(([x, y]) => `${x},${y}`).join(' ')

/**
 * The twelve months of an indicator in a small line, with its target as a dashed line.
 * Decorative detail for sighted users: `label` names it, and the card and its detail
 * give the same numbers as text.
 */
export function Sparkline(props: { points: SeriesPoint[]; label: string }) {
  const values = props.points.map((point) => point.value)
  const targets = props.points.map((point) => point.target)
  const known = [...values, ...targets].filter((value): value is number => value !== null)
  if (!values.some((value) => value !== null)) return null

  const low = Math.min(...known)
  const high = Math.max(...known)
  const span = high - low || 1
  const step = (WIDTH - 2 * PAD) / Math.max(props.points.length - 1, 1)
  const round = (coordinate: number) => Math.round(coordinate * 10) / 10
  const position = (index: number, value: number): XY => [
    round(PAD + index * step),
    // A flat series is drawn across the middle.
    round(high === low ? HEIGHT / 2 : PAD + ((high - value) / span) * (HEIGHT - 2 * PAD)),
  ]
  const lines = runs(values, position)
  const targetLines = runs(targets, position)
  const last = values.length - 1
  const end = values[last] === null ? null : position(last, values[last])

  return (
    <svg
      role="img"
      aria-label={props.label}
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      data-sparkline
    >
      {targetLines.map((run) => (
        <polyline
          key={`target-${run[0][0]}`}
          points={toPoints(run)}
          fill="none"
          stroke={TARGET}
          strokeWidth={1}
          strokeDasharray="3 3"
          data-target-line
        />
      ))}
      {lines.map((run) =>
        run.length === 1 ? (
          <circle key={`dot-${run[0][0]}`} cx={run[0][0]} cy={run[0][1]} r={1.5} fill={LINE} />
        ) : (
          <polyline
            key={`line-${run[0][0]}`}
            points={toPoints(run)}
            fill="none"
            stroke={LINE}
            strokeWidth={1.75}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ),
      )}
      {end && <circle cx={end[0]} cy={end[1]} r={2.5} fill={LINE} />}
    </svg>
  )
}
