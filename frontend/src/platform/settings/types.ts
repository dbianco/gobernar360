import type { MapBackground } from '../geo/types'

/** A municipality's configuration, as the API returns it. */
export interface MunicipalitySettings {
  notification_emails: string[]
  sso_enabled: boolean
  /** Whether the platform has an identity provider configured at all. */
  sso_available: boolean
  /** Counts per zone of sensitive records are shown to viewers from this many up. */
  small_zone_threshold: number
  map_background: string
  map_api_key: string | null
  /** What can be chosen. */
  map_backgrounds: MapBackground[]
}

/** What a municipality chooses for its maps. */
export type MapSettings = Pick<
  MunicipalitySettings,
  'small_zone_threshold' | 'map_background' | 'map_api_key'
>

/** One kind of email and the municipality's text for it. */
export interface EmailTemplate {
  key: string
  subject: string
  html: string
  /** False while the municipality uses the default text. */
  customized: boolean
  variables: string[]
  required: string[]
}
