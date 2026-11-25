"""Geographic layer: zones, records with a location, and aggregates by zone.

A dashboard gives a record a place by adding `LocatedMixin` to its model, calling
`enable_location()` in the migration and declaring a `LocatedRecord` in its
`DashboardModule`. Everything else (assigning zones, maps, breakdowns, the list of records
without a zone) is here and knows no dashboard.
"""
