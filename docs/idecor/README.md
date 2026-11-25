# IDECOR and CONAE: provincial geographic services, as checked on 2026-11-25

IDECOR is the spatial data infrastructure of the Province of Córdoba (cadastre, boundaries,
equipment). Everything here was **fetched and verified from a machine with internet**, so an agent
without it can work from these notes and `samples/`. The GeoMiner project
(`/Users/daniel/src/geominer`, `src/geominer/ingest/`) already uses the first two services.
Used by `docs/tasks/21-idecor-official-layers.md`.

## Services

| Service | Address | Used for |
|---|---|---|
| IDECOR WFS 2.0 (main) | `https://idecor-ws.mapascordoba.gob.ar/geoserver/wfs` | vector layers (536 of them, `layers-wfs.tsv`) |
| IDECOR WFS 2.0 (map viewer) | `https://gn-idecor.mapascordoba.gob.ar/geoserver/wfs` | the viewer's copy, 1,259 layers, **fails intermittently** |
| CONAE WMTS | `https://geotematico01.conae.gov.ar/geoserver/gwc/service/wmts` | satellite imagery of localities (**CONAE, the national space agency; not IDECOR**) |

Quirks learned by GeoMiner (they are real):
- GetFeature answers some valid requests with an XML exception or a 5xx. **Retry with exponential
  backoff** (4 attempts, 1, 2, 4 s); read the body as JSON and check it has `features`.
- CQL attribute filters time out on large layers. **Filter by `BBOX` and by attribute in memory.**
- Asking for `srsName=EPSG:4326` returns coordinates **rounded to 4 decimals (about 10 m)**. Ask for
  the native projected CRS **EPSG:22174** (POSGAR 94 / Argentina 4, metric) and transform with
  PostGIS (`ST_Transform(..., 4326)`). The files in `samples/` are in 4326 and rounded: they are
  fixtures, not data to import.
- With `urn:ogc:def:crs:EPSG::4326` in the BBOX the axis order is **latitude, longitude**:
  `BBOX=<min_lat>,<min_lon>,<max_lat>,<max_lon>,urn:ogc:def:crs:EPSG::4326`.
- Send a `User-Agent`. Unauthenticated, no key needed.

Request that worked (Noetinger's box is `-32.3794,-62.3407,-32.3392,-62.2839`):

```
GET https://idecor-ws.mapascordoba.gob.ar/geoserver/wfs
    ?service=WFS&version=2.0.0&request=GetFeature&typeNames=idecor:radios_urbanos
    &outputFormat=application/json&srsName=EPSG:22174
    &BBOX=-32.3794,-62.3407,-32.3392,-62.2839,urn:ogc:def:crs:EPSG::4326
```

Verified: `radios_urbanos` accepts `cql_filter=key='360124'` (answers in 0.1 s, 1 feature, EPSG:22174
at full precision, `samples/noetinger_radios_urbanos_epsg22174.json`). The whole layer has 427
features (1.7 MB, 0.35 s). CQL on the big layers (parcels, blocks) still times out.

## Layers that matter for a municipality (names exact; the full list is `layers-wfs.tsv`)

| Layer | Content | Geometry | Notes |
|---|---|---|---|
| `idecor:radios_urbanos` | official urban radius of each municipality and commune | MultiPolygon | properties `id`, `key`, `nombre`, `url` (the law that approves it), `area_ha`, `tipo_gobierno`. **Noetinger: id 101, key `360124`, `nombre` "NOETINGER", url "Expte 0423-031865-2008 - Ley 10796/2022", 1263.6 ha, "Municipio".** `samples/noetinger_radios_urbanos.geojson` |
| `idecor:localidad_punto` | locality point | MultiPoint | `localidad`, `departamento`, `tipo`. Noetinger: departamento UNIÓN, tipo Municipio |
| `idecor:Centros_Salud` | health centres | Point | `establecimiento_salud`, `domicilio`, `tipo`, `categoria`, `dependencia`, `localidad`, `codigo_sisa`. Noetinger: Hospital Municipal de Noetinger |
| `idecor:establecimientos_educativos` | schools | Point | `nombre`, `cueanexo`, `est_sector`, `est_ambito`, `est_domicilio`, `est_localidad`, `nivel`. Noetinger: 11 features in the box |
| `idecor:parcelas` | cadastral parcels | MultiPolygon | already ingested by GeoMiner (`Nomenclatura`, `localidad`, `Tipo_Parcela`, `Superficie_Tierra_Urbana`, `Superficie_Mejoras`, `Nro_Cuenta`, `Estado`) |
| `idecor:manzana` | city blocks | MultiPolygon | `nomenclatura`, `departamento`, `pedania`. **The box also returns blocks of neighbouring towns (Marcos Juárez): filter by `nomenclatura` or by the radius.** 173 returned for Noetinger's box |
| `idecor:departamentos`, `idecor:provincia` | boundaries | | |
| `<town>_barrios` (for example `cosquin_barrios`, `vm_barrios`, `mteros_barrios`, `va_barrios`) | neighbourhoods **for the towns that supplied them** | | **Noetinger has none.** `no_cache_renabap_barrios` (RENABAP informal neighbourhoods) answered with an XML exception: not usable today. |

Municipality-specific layers exist for many towns (streets, blocks, parcels, equipment). Their
names are not uniform; search `layers-wfs.tsv` by town.

## Imagery: CONAE WMTS

- Layer for Noetinger: **`Localidades:Cordoba_Noetinger_2023`**, "Noetinger, Córdoba 2023", an RGB
  true-colour product from Pleiades Neo (about 0.30 m), covering lon -62.3707..-62.2603, lat
  -32.4056..-32.3238. The GetCapabilities fields `Fees` and `AccessConstraints` say `NONE`; **that is
  not a licence**: show the attribution and ask CONAE about reuse.
- Tile address that returned a PNG (verified at zoom 17):
  `https://geotematico01.conae.gov.ar/geoserver/gwc/service/wmts/rest/{layer}/raster/EPSG:900913/EPSG:900913:{z}/{y}/{x}?format=image/png`
  Note the order **row (`y`) before column (`x`)** and that rows count from the top, which is the
  same as the usual Leaflet `{z}/{x}/{y}` scheme, so Leaflet's `{y}` goes in the row place.
  Outside the layer's coverage the server answers **400 with an XML exception**: draw nothing.
- Response headers: `Access-Control-Allow-Origin: *`, but `Cache-Control: no-cache, no-store,
  must-revalidate`: every view downloads the tiles again. Do not point heavy traffic at it without
  asking; a municipality may prefer us to cache.
- Capabilities of all layers: `https://geotematico01.conae.gov.ar/geoserver/gwc/service/wmts?REQUEST=GetCapabilities`
  (16 MB). Other localities have layers named `Localidades:Cordoba_<Town>_<year>`.

## Files here

- `layers-wfs.tsv`: name and title of the 536 layers of the main WFS.
- `samples/`: real answers for Noetinger (`noetinger_radios_urbanos_epsg22174.json` is the radius in
  EPSG:22174 at full precision; the others are EPSG:4326, rounded to 4 decimals: `noetinger_radios_urbanos`,
  `noetinger_localidad_punto`, `noetinger_Centros_Salud`, `noetinger_establecimientos_educativos`,
  GeoJSON). Use them as test fixtures; the data is public and contains no personal data.

## Licence (decided by the product owner on 2026-11-25)

The product owner states that these sources are published under the **MIT licence** and that they
are to be used as such for now. Keep the attribution shown on the maps and cite the source in the
imports. No licence text was found in the services' capabilities documents (`Fees` and
`AccessConstraints` say `NONE`), so the source of the claim is the owner's statement, not a
document in this repository; record the document here when it is found.

## Pending (a person must answer)

- Whether CONAE agrees to a municipality's maps loading its tiles on every view (no cache headers).
- Whether IDECOR has a stable, documented address for the neighbourhood layers of other towns, and
  why `no_cache_renabap_barrios` answers with an error.
