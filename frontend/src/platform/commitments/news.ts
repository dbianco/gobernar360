import type { TFunction } from 'i18next'

import type { News } from './types'

/** What happened, in words: who gave it, or who delivered it. */
export function newsText(t: TFunction, news: News): string {
  return t(`notices.kinds.${news.kind}`, { actor: news.actor ?? t('notices.someone') })
}
