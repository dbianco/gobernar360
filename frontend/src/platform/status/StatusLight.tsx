import { IconAlertTriangle, IconCheck, IconX, type Icon } from '@tabler/icons-react'
import type { CSSProperties } from 'react'

import type { StatusColor } from './types'

const FILL: Record<StatusColor, { background: string; color: string; glyph: Icon }> = {
  green: {
    background: 'var(--mantine-color-green-8)',
    color: '#fff',
    glyph: IconCheck,
  },
  // Yellow is too light for white marks.
  yellow: {
    background: 'var(--mantine-color-yellow-5)',
    color: '#212529',
    glyph: IconAlertTriangle,
  },
  red: {
    background: 'var(--mantine-color-red-8)',
    color: '#fff',
    glyph: IconX,
  },
}

/**
 * A round light. Each state has its own mark besides its color, so it can be told
 * apart without seeing color; pass `icon` to show a dashboard's icon instead.
 */
export function StatusLight(props: { color: StatusColor | null; size: number; icon?: Icon }) {
  const fill = props.color ? FILL[props.color] : null
  const Glyph = props.icon ?? fill?.glyph
  const style: CSSProperties = {
    width: props.size,
    height: props.size,
    borderRadius: '50%',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    background: fill?.background ?? 'transparent',
    color: fill?.color ?? 'var(--mantine-color-dimmed)',
    border: fill ? 'none' : '2px dashed var(--mantine-color-default-border)',
  }
  return (
    <span style={style} data-status={props.color ?? 'none'}>
      {Glyph && <Glyph size={Math.round(props.size * 0.58)} stroke={2} aria-hidden />}
    </span>
  )
}
