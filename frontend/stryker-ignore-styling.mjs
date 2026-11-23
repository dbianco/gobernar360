// A Stryker ignorer: no mutants in props that only change how something looks (spacing,
// sizes, colors, variants, and how the charts draw lines, axes and tooltips). Tests run in
// jsdom, which has no layout or CSS, so such mutants could only survive; how the screens
// look is checked by eye and in the browser.
import { declareValuePlugin, PluginKind } from '@stryker-mutator/api/plugin'

const STYLING_PROPS = new Set([
  'activeDot',
  'align',
  'axisLine',
  'barSize',
  'c',
  'className',
  'color',
  'cols',
  'connectNulls',
  'contentStyle',
  'cursor',
  'dot',
  'fill',
  'fw',
  'fz',
  'gap',
  'h',
  'highlightOnHover',
  'horizontalSpacing',
  'isAnimationActive',
  'itemStyle',
  'justify',
  'labelStyle',
  'lh',
  'm',
  'mah',
  'margin',
  'maw',
  'mb',
  'mih',
  'minWidth',
  'miw',
  'ml',
  'mr',
  'mt',
  'mx',
  'my',
  'p',
  'pb',
  'pl',
  'pr',
  'pt',
  'px',
  'py',
  'radius',
  'shadow',
  'size',
  'spacing',
  'stroke',
  'strokeDasharray',
  'strokeWidth',
  'style',
  'ta',
  'tick',
  'tickLine',
  'variant',
  'vertical',
  'verticalSpacing',
  'w',
  'withBorder',
  'withRowBorders',
  'wrap',
])

export const strykerPlugins = [
  declareValuePlugin(PluginKind.Ignore, 'styling', {
    shouldIgnore(path) {
      const attribute = path.isJSXAttribute()
        ? path
        : path.findParent((parent) => parent.isJSXAttribute())
      const name = attribute?.node.name.name
      return typeof name === 'string' && STYLING_PROPS.has(name)
        ? `Only changes how it looks (the "${name}" prop).`
        : undefined
    },
  }),
]
