# Task 07: Geographic layer

## Task description

A municipality thinks in neighbourhoods: where the works are, where the families that
receive assistance live, where the shops are. gobernar360 runs on a PostGIS database
but stores no location at all, so none of those questions can be asked. This session
makes place a first-class part of the platform, available to every dashboard.

The centre of the work is zones and spatial aggregation, not drawing pins on a map:

- **Zones.** Each municipality defines its zones (neighbourhoods, districts) as
  polygons, by drawing them on a map or uploading a GeoJSON file. Zones are validated
  (closed, not self-intersecting), overlaps are detected and reported, and zones are
  versioned so that editing a boundary does not silently rewrite history.
- **Located records.** A platform mixin and a registry contract let a dashboard declare
  that a record has a location. This session locates projects (a point or a line, for
  a street works), social households and economic actors. A location is set by clicking
  on the map or typing coordinates; the address stays as text.
- **Automatic zone assignment.** The zone of a record is computed in the database from
  its location (point in polygon; a line belongs to every zone it crosses), kept up to
  date when the location or the zone boundaries change, and recomputed in bulk by a
  command. Records outside every zone are listed for review.
- **Map views.** A map in each of the three dashboards with clustering at low zoom,
  filters matching the list's filters, and a click-through to the record. The API
  serves only what is inside the visible area, so a municipality with tens of thousands
  of points stays responsive.
- **Aggregates by zone.** Each dashboard summary gains a breakdown by zone and a
  shaded map (households assisted, active projects and budget, economic actors by
  sector). The general overview gains a zone profile that combines the dashboards the
  member can see.
- **Sensitive locations.** Social households are shown individually only to editors
  and above; viewers get counts per zone, and zones with fewer households than a
  threshold are not shaded. The CSV exports follow the same rule.
- **Tenant isolation in space.** Geometry tables are covered by row-level security,
  and spatial queries are tested not to cross municipalities even when polygons of two
  municipalities overlap.

## How to judge completion

Setup: database up, `uv run alembic upgrade head` (enables PostGIS),
`uv run gobernar360 seed-demo --reset` (Noetinger now has zones and located records
with made-up coordinates), API and web app running.

Automated, all must pass:

- `cd backend && uv run pytest` — includes tests for: an invalid polygon is rejected;
  overlapping zones are reported; a point is assigned to the right zone and reassigned
  when the boundary moves; a line crossing two zones counts in both; the bounding-box
  endpoint returns only points inside it; a viewer of Social receives no household
  coordinates; small zones are suppressed for viewers; two municipalities with
  overlapping polygons never see each other's zones or points; a dashboard registered
  only in the test can declare located records.
- `cd backend && uv run ruff check . && uv run lint-imports`
- `cd frontend && npm test -- --run && npm run lint && npm run build && npm run e2e`
  — includes a spec that opens a map, filters and opens a record from it.

By hand, as `admin@noetinger.test`:

1. In the municipality's zones screen draw a new zone over existing projects: those
   projects now show that zone, and the Projects summary's breakdown by zone adds it.
2. Move one project's location outside every zone: it appears in the "without zone"
   review list.
3. Zoom the Economic map out and in: points cluster and separate; panning loads only
   the visible area (visible in the network panel).
4. As `lectura@noetinger.test` open the Social map: only shaded zones with counts, no
   household points; the API response contains no coordinates.
5. As `admin@comuna-demo.test`: no zones or points of Noetinger are visible.

Pass: every command is green and the five manual checks behave as described.

## Other notes

- The map background must not need a paid service or an API key: use an openly
  licensed tile source with attribution, and keep the map usable (zones and points
  still drawn) when tiles cannot be loaded, since the tests run offline.
- No geocoding of addresses through an external service; locations are set by hand or
  come with the data.
- All coordinates in the demo data are made up.
- If task 03 (complaints) exists, complaints become located records too; not required.
