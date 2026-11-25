import type { ZoneRef } from './types'

/** The zones of a record, as a table shows them. */
export const zoneNames = (zones: ZoneRef[], none: string) =>
  zones.map((zone) => zone.name).join(', ') || none
