/** A municipality's configuration, as the API returns it. */
export interface MunicipalitySettings {
  notification_emails: string[]
  sso_enabled: boolean
  /** Whether the platform has an identity provider configured at all. */
  sso_available: boolean
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
