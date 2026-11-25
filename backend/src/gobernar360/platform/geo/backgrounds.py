"""Map backgrounds a municipality can choose from: OpenStreetMap's list.

The raster layers openstreetmap.org offers, plus the other worldwide ones its community
runs. All draw OpenStreetMap's open data. Layers served only as vector tiles (Shortbread)
are not here, because the maps draw images; nor are the ones that cover a single country.
"""

from dataclasses import dataclass

OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
_THUNDERFOREST = f'&copy; <a href="https://www.thunderforest.com/">Thunderforest</a>, {OSM}'
_FRANCE = '<a href="https://openstreetmap.fr/">OpenStreetMap France</a>'


@dataclass(frozen=True)
class Background:
    key: str
    # Leaflet template. {apiKey} is the municipality's own key for the provider.
    url: str
    # Shown as HTML on every map, as the licence of the data asks.
    attribution: str
    # The closest zoom it has images for; further in, they are enlarged.
    max_zoom: int
    # Whoever gives the key, for those that need one. They have free plans with limits.
    provider: str | None = None
    tile_size: int = 256
    zoom_offset: int = 0


DEFAULT = "standard"

BACKGROUNDS = (
    Background(DEFAULT, "https://tile.openstreetmap.org/{z}/{x}/{y}.png", OSM, 19),
    Background(
        "humanitarian",
        "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        f'{OSM}, style by <a href="https://www.hotosm.org/">Humanitarian OpenStreetMap Team</a>, '
        f"hosted by {_FRANCE}",
        19,
    ),
    Background(
        "cyclosm",
        "https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
        '<a href="https://github.com/cyclosm/cyclosm-cartocss-style/releases">CyclOSM</a> | '
        f"Map data: {OSM}",
        20,
    ),
    Background("germany", "https://tile.openstreetmap.de/{z}/{x}/{y}.png", OSM, 18),
    Background(
        "france",
        "https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
        f"&copy; {_FRANCE} | {OSM}",
        20,
    ),
    Background(
        "topographic",
        "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        f'Map data: {OSM}, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; '
        '<a href="https://opentopomap.org">OpenTopoMap</a> '
        '(<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
        17,
    ),
    Background(
        "public_transport",
        "https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png",
        'Map <a href="https://memomaps.de/">memomaps.de</a> '
        '<a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, '
        f"map data {OSM}",
        18,
    ),
    Background(
        "cycle",
        "https://api.thunderforest.com/cycle/{z}/{x}/{y}.png?apikey={apiKey}",
        _THUNDERFOREST,
        22,
        provider="Thunderforest",
    ),
    Background(
        "transport",
        "https://api.thunderforest.com/transport/{z}/{x}/{y}.png?apikey={apiKey}",
        _THUNDERFOREST,
        22,
        provider="Thunderforest",
    ),
    Background(
        "tracestrack",
        "https://tile.tracestrack.com/topo__/{z}/{x}/{y}.png?key={apiKey}",
        f'&copy; <a href="https://www.tracestrack.com/">Tracestrack</a>, {OSM}',
        19,
        provider="Tracestrack",
    ),
    Background(
        "maptiler",
        "https://api.maptiler.com/maps/openstreetmap/{z}/{x}/{y}.jpg?key={apiKey}",
        f'<a href="https://www.maptiler.com/copyright/">&copy; MapTiler</a> {OSM}',
        21,
        provider="MapTiler",
        tile_size=512,
        zoom_offset=-1,
    ),
)

_by_key = {background.key: background for background in BACKGROUNDS}


def find(key: str) -> Background | None:
    return _by_key.get(key)


def in_use(key: str) -> Background:
    """The background saved, or the default if it was since taken off the list."""
    return _by_key.get(key, _by_key[DEFAULT])
