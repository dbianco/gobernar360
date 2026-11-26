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
  /** Where the municipality is in the official services. Only the operator sets them. */
  idecor_key: string | null
  conae_layer: string | null
}

export type Geography = Pick<MunicipalitySettings, 'idecor_key' | 'conae_layer'>

/** What a municipality chooses for its maps. */
export type MapSettings = Pick<
  MunicipalitySettings,
  'small_zone_threshold' | 'map_background' | 'map_api_key'
>

export const NOTICE_CHANNELS = ['email', 'cidi_then_email', 'cidi'] as const
export type NoticeChannel = (typeof NOTICE_CHANNELS)[number]
export const ADHESION_STATES = ['not_requested', 'requested', 'approved'] as const
export type AdhesionState = (typeof ADHESION_STATES)[number]

/** How residents are told things, and the municipality's own connection to CiDi. */
export interface NoticeSettings {
  resident_notice_channel: NoticeChannel
  cidi_ordinance: string
  adhesion_state: AdhesionState
  /** YYYY-MM-DD */
  adhesion_date: string | null
  adhesion_file: string
  system_name: string
  publication_url: string
  contact: string
  /** That each secret is there, and since when. Their values never come back. */
  secrets: { name: string; set_at: string }[]
  /** What is needed before a channel with CiDi can be chosen. */
  missing: string[]
  /** Whether this installation reaches CiDi at all, and whether it can keep secrets. */
  cidi_available: boolean
  secrets_available: boolean
}

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
