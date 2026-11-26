# Geographic layer: design

Task: `docs/tasks/07-geographic-layer.md`. How to use it: README, *Geographic layer*.
Rules for changing it: `CLAUDE.md`, *Geographic layer*.

## Data

| Table | What it holds |
|---|---|
| `zones` | A zone's identity and name. `retired_at` when it is no longer used |
| `zone_versions` | Its boundary (`MultiPolygon`, EPSG:4326) from `valid_from` to `valid_to`; one open version per zone |
| `record_zones` | Which records lie in which version. Filled by triggers only |
| `location` column | On `projects_projects` (point or line), `social_households` and `economic_actors` (point) |

All three tables are tenant tables with row-level security; `location` is on tables that
already have it.

## Decisions

**The location is a column of the record, not a table of locations.** Isolation, deletion
and foreign keys are the record's own. A generic table keyed by kind and id would need all
three rebuilt by hand.

**Zones are worked out for every version, not only the current one.** Reading a past year is
then a join with the versions in force when it ended, as cheap as today's figures, and moving
a boundary cannot change it. Moving a *record* does change where it counted in the past: that
is a correction of its place, not a change of the zones.

**Before the first zone existed, today's boundaries answer.** Otherwise every year before the
feature was adopted would say that everything was outside every zone. The answer says which
boundaries it used (`boundaries_as_of`).

**Triggers, with one advisory lock per municipality.** A location and a boundary changed at
the same time in two transactions would not see each other, and the record would be left in
the wrong zone. Records share the lock; a boundary change takes it alone.

**Which tables follow the zones** is read from the catalog (those with the trigger), so a new
dashboard needs no change in the platform.

**A line crosses a zone when the part inside it has length.** So a street along the border of
two neighbourhoods is in both, and one that merely ends at a border is not in the next zone.
A point exactly on a shared border is in both zones too (F11): it counts in each and once in
the total, as anything in several zones.

**A past day counts the records there were then** (F10, `created_at`): the boundaries were
already those of that day. A record loaded later, however old what it describes, is not in it.

**Whoever gets only counts sees the past a month at a time** (F8): `as_of` is moved to the end
of its month, or to today while that month lasts. Two days in a row would tell what was
loaded in between, and so a count hidden for being small.

**Overlaps are reported, not refused.** Districts contain neighbourhoods. A record in several
zones counts in each and once in the total. Shared ground under 10 m² is taken for drawing.

**No spatial indexes.** Checked with `EXPLAIN`: under row-level security PostgreSQL evaluates
the policy before `&&`, which is not leakproof, so the API role never uses a GiST index; it
narrows by municipality. It would only cost writes. With 50,000 located actors in one
municipality, requests for a map stayed under a second on a much slower database than
production's (PostGIS compiled to WebAssembly).

**Grouping is done by the API.** The browser never receives more than the squares that fit on
screen, or 1,000 records at street level (and is told when there are more). The grid is
anchored to the world, so panning does not regroup.

**Hiding small counts.** See below.

**Leaflet, without a React wrapper or a drawing plugin.** What is needed (polygons, marks that
can be dragged and pressed with the keyboard) is small, and marks and labels are built as
elements so that names are never taken for HTML.

## Sensitive locations

Members below `LocatedRecord.individual_level` (editors, for households):

- receive no features, clusters, locations, review list, or zone of one record;
- get counts per zone, with those under the threshold hidden, zero included;
- if what is hidden adds up to less than the threshold, the smallest counts left are hidden
  too: the total is known, and a single hidden count would be the total minus the rest.
  Records outside every zone and without a location take part, as if they were two zones;
- cannot narrow the counts. With a search, two requests that differ in one household would
  tell its zone however large both counts were. The year only changes which help is counted.

The threshold is the municipality's, in Configuración: 5 by default, from 2 to 100. It cannot
be 1, which would show a zone with a single family.

Decided: the list of households, with its address and neighborhood typed as text, was already
open to viewers and stays so. Known limit: a viewer who keeps the figures of before and after a
boundary or a household moved can compare them.

## Backgrounds

Chosen per municipality in Configuración, from OpenStreetMap's list: the raster layers of
openstreetmap.org plus the other worldwide ones its community runs. Left out: layers served
only as vector tiles (Shortbread), which Leaflet does not draw, and those of one country.
Addresses and attributions come from `leaflet-providers` 4.0.0, except Tracestrack's, which it
does not have.

The default needs no key. The four that do ask for the municipality's own; it is not a secret,
because browsers send it with every image, and the screen says to restrict it at the
provider's site. It is kept only while a background uses it.

## API

| Route | Who | |
|---|---|---|
| `GET /api/zones?as_of=` | members | Zones and boundaries |
| `POST /api/admin/zones`, `PATCH`/`DELETE .../{id}` | municipality admins | Answers with the overlaps; `base_version` refuses stale edits |
| `POST /api/admin/zones/import` | municipality admins | GeoJSON, matched by name, all or nothing |
| `GET /api/admin/zones/overlaps`, `.../{id}/versions` | municipality admins | |
| `GET /api/dashboards/{key}/geo/{record}/features?bbox=&zoom=` | individual level | Visible area, plus the list's filters |
| `GET .../zones`, `.../zones.csv` | viewers | Breakdown; `as_of` |
| `GET .../unzoned?reason=` | individual level | Review list |
| `GET`/`PUT .../{id}/location` | individual level / editors | |
| `GET /api/overview/zones/{id}` | members | Zone profile |
| `GET /api/map-background` | members | Background in use, with its key |
| `PUT /api/admin/settings/map` | municipality admins, operator | Background, key and threshold |
