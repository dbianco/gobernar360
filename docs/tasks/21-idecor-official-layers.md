# Task 21: Official provincial geography: urban radius, equipment and satellite imagery - DONE

Priority: **high** (chosen by the product owner on 2026-11-25).
Read first: `docs/idecor/README.md` (verified endpoints, quirks and the layers of Noetinger),
`docs/tasks/07-geographic-layer.md` and the "Geographic layer" section of `CLAUDE.md`. Everything this
task needs from outside is in `docs/idecor/`: **no internet is needed to build or test it**; the
real services are only reached when a person runs the import command.

## Task description

The geographic layer (task 07) lets a municipality draw its zones by hand. The Province already
publishes the official boundaries and equipment of every locality (IDECOR), and the national space
agency publishes satellite imagery of the town (CONAE). Today a Noetinger administrator would
have to trace the town's outline from a street map, the demo's zone "Casco urbano" is an
approximation made from parcels, and the map shows no hospital or school. This task brings the
official data in:

1. **Official urban radius as a zone.** `gobernar360 import-idecor <slug> --radius` fetches the
   municipality's *radio urbano* (layer `idecor:radios_urbanos`, selected by the municipality's
   `idecor_key`, for example `360124` for Noetinger) and creates or moves the zone **"Radio urbano"**
   through `platform/geo/zones` (a new version if the boundary differs, none if it is the same, as
   the GeoJSON import does), reporting overlaps with the other zones. The law that approves it
   (`url` property, "Ley 10796/2022") is kept in the zone's description or audit entry.
2. **Equipment as reference layers.** `--layers health,schools` fetches `idecor:Centros_Salud` and
   `idecor:establecimientos_educativos` inside the radius and stores them as **reference features**:
   points shown on every map of the municipality (toggle "Equipamiento"), with name, type and
   address in a popup. They are not records: they have no zone assignment, are not editable by hand
   and are replaced by each import (the import is the unit; it stores `imported_at` and the source
   address). They carry no personal data (facilities, not people); a health *centre* is public data,
   but never import anything that names a patient or a household.
3. **Satellite imagery as a background.** A new map background "Satélite (CONAE)" using the layer
   `Localidades:Cordoba_<Town>_<year>` the municipality configures (`conae_layer`, validated to be
   safe in an address like the provider key is), with its attribution, drawn from the WMTS address
   in `docs/idecor/README.md`. It exists only where the municipality has set the layer; where tiles
   are missing (HTTP 400) nothing is drawn and the map stays usable (task 07's rule).
4. **The import is repeatable and honest.** It retries as GeoMiner's client does, reads in EPSG:22174
   and transforms in the database, validates every geometry before storing it (no partial import:
   one failure leaves nothing changed), prints what it did (created, moved, unchanged, rows read),
   and works offline from a directory with `--from-dir DIR` (files named as the samples in
   `docs/idecor/samples/`).

## Design notes (decisions already taken)

- **Reference features are a platform table**, `geo_reference_features` (tenant table with
  `TenantMixin`, `enable_tenant_rls`, the migration's next free number): `id`, `layer` (`health`,
  `schools`), `source_id` (the layer's own `id`), `name`, `properties` (JSON with only the fields
  listed in `docs/idecor/README.md`: type, address, sector, level), `location` (GeoJSON point, the
  project's `geo/types.Geometry`, deferred), `source_url`, `imported_at`. Unique
  `(layer, source_id)`. **No `LocatedMixin`**: no triggers, no `record_zones` rows.
- **Who may read them:** any member of the municipality (they are public facilities). Endpoint
  `GET /api/geo/reference-layers/{layer}?bbox=` returns only what is inside the visible box, like
  the records map. Writes only through the import command.
- **`idecor_key` and `conae_layer`** are columns of `municipality_settings` edited **only by the
  platform operator** (they identify official sources) at `PUT /api/platform/municipalities/{id}/
  settings/geography`; municipality administrators see them read-only. Validation: `idecor_key` is
  six digits; `conae_layer` allows letters, digits, `:`, `_`, `-` only. Neither is written by
  `PUT .../settings` or `PUT .../settings/map`. Add them to the audit trail.
- **Background:** extend `platform/geo/backgrounds.py` with a `Background` whose URL has `{layer}`
  (replaced from the setting by the same code that replaces `{apiKey}`); `max_zoom` 19 (the product
  is 0.30 m; Noetinger's layer exists at 17 and beyond: verify the highest zoom that answers and
  record it); attribution "Imagen: CONAE – Pleiades Neo 2023" where the year comes from the layer
  name. Its name and description in the frontend locale and in `settings/testData.ts`
  (`settings.map.backgrounds`), as the existing ones.
- **Do not hotlink without telling:** CONAE sends `Cache-Control: no-store`, so every view
  re-downloads. Add to the map-background help text that tiles come from a national agency's
  server and that heavy use should be agreed with them. Task 09's content-security policy must
  allow `geotematico01.conae.gov.ar`; write that into task 09's notes (`docs/tasks/todo.md`).
- **Licence (decided by the product owner): MIT, use them.** Keep the attribution on the map and in
  the import output, and cite the source of each import (address and date). The decision is
  recorded in `docs/idecor/README.md`; if a licence document is found later, add it there.

## How to judge completion

Setup: database up, `uv run alembic upgrade head`, `uv run gobernar360 seed-demo --reset` (the
demo sets Noetinger's `idecor_key` to `360124` and `conae_layer` to
`Localidades:Cordoba_Noetinger_2023`), API and web app running.

Automated, all must pass (no internet):

- `cd backend && uv run pytest` — includes tests, using `docs/idecor/samples/` copied to
  `backend/tests/platform/geo/idecor_samples/`, for: the radius sample becomes a valid zone named
  "Radio urbano" with the right area (about 1263.6 ha within 1 %); importing twice leaves one zone
  and one version; a changed boundary adds a version and closes the previous (history kept, as in
  task 07); a self-intersecting polygon in a fixture is rejected and nothing is stored; a feature
  with a null geometry or an unexpected type is skipped and counted; the schools and health samples
  produce the right number of reference features (11 and 1) and a second import replaces rather than
  duplicates them; a layer with 500 features comes through (generated); a request for a box returns
  only the features inside it; municipality B cannot read A's reference features and the import for
  A never writes B's (two municipalities with overlapping radii); `--from-dir` never opens a socket
  (monkeypatch `httpx`); the HTTP client retries a 5xx and an XML exception body, then raises a
  clear error after 4 attempts (mock transport, as GeoMiner's tests do); the operator can set
  `idecor_key` and `conae_layer`, the municipality admin cannot (403), invalid values are 422, and
  the audit trail records the change; the background list includes the satellite entry only
  where `conae_layer` is set, with the URL filled in; `PUT .../settings` and `.../settings/map` do
  not touch the new columns.
- `cd backend && uv run pytest --cov` ≥ 95 % per file, `uv run ruff check . && uv run ruff format
  --check . && uv run lint-imports`.
- `cd frontend && npm test -- --run && npm run test:coverage && npm run lint && npm run build &&
  npm run e2e` — includes `e2e/reference-layers.spec.ts`: open a map, turn "Equipamiento" on, see a
  marker with the hospital's name, and choose the satellite background (the e2e runs offline: tiles
  fail and the map stays usable).

By hand (this part needs internet), as the operator `operador@gobernar360.test` then
`admin@noetinger.test`:

1. `uv run gobernar360 import-idecor noetinger --radius --layers health,schools`: the output says one
   zone created and the numbers of features read. Open Configuración > Mapas y zonas: "Radio urbano" appears with its law; the
   overlap with "Casco urbano" is reported as a warning, not an error.
2. Run it again: "unchanged".
3. Open the Projects map: "Equipamiento" shows the Hospital Municipal de Noetinger and the schools
   in their places on the satellite image; the popup shows name and address.
4. Settings → Maps: choose "Satélite (CONAE)": the town appears in true colour at street level;
   zoom out beyond the layer: no tiles, no error, the points and zones are still drawn.
5. As `admin@comuna-demo.test` there is no "Satélite" option (no layer set) and none of Noetinger's
   equipment.
6. Turn the internet off and run the command with `--from-dir docs/idecor/samples`: it works.

Pass: every command is green and the six manual checks behave as described.

## Other notes

- Only Noetinger has been checked. Other towns have layers named differently (`<town>_barrios`,
  `<town>_calles`...); the radius, health and schools layers are provincial and uniform. Do not
  build neighbourhood import for Noetinger: it has none in IDECOR (`docs/idecor/README.md`).
- The radius is the *official* outline of the urban area, not a neighbourhood: a municipality
  still draws its own neighbourhoods as zones inside it.
- GeoMiner (`/Users/daniel/src/geominer`) fetches parcels with the same WFS client; this task may
  copy its retry logic, but **must not import from GeoMiner** (separate project).
- Out of scope: parcels, blocks (`idecor:manzana`, which also returns neighbouring towns), streets,
  the viewer's 1,259-layer WFS (fails intermittently), RENABAP informal neighbourhoods
  (`no_cache_renabap_barrios` answered with an error), scheduled refreshes, and any record of people.
