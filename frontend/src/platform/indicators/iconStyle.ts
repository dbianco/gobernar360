/** Shared by the icons of an indicator (info, open the chart) so they look and behave alike. */
export const ICON_BUTTON = { variant: 'subtle', color: 'gray', size: 'md' } as const
export const ICON_SIZE = 18
export const ICON_STROKE = 1.5
export const TOOLTIP = {
  multiline: true,
  w: 260,
  withArrow: true,
  fw: 400,
  ta: 'left',
  events: { hover: true, focus: true, touch: true },
} as const
