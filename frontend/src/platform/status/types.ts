export const STATUS_COLORS = ["green", "yellow", "red"] as const;
export type StatusColor = (typeof STATUS_COLORS)[number];

/** The light of one month of the year being looked at. */
export interface MonthStatus {
  month: number;
  color: StatusColor;
}

/** A light with its year, as the general overview lists them. */
export interface DatedStatus extends MonthStatus {
  year: number;
}
