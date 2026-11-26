"""Bringing official geography in: what is created, moved, left alone and refused."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import undefer
from typer.testing import CliRunner

from gobernar360 import cli
from gobernar360.core.db import tenant_session
from gobernar360.platform.access import system_context
from gobernar360.platform.clock import get_today
from gobernar360.platform.geo.idecor import Directory
from gobernar360.platform.geo.models import RecordZone, ReferenceFeature, Zone, ZoneVersion
from gobernar360.platform.geo.reference_import import import_official
from gobernar360.platform.models import AuditLog, MunicipalitySettings
from tests.factories import admin_session, make_municipality
from tests.platform.geo.factories import make_zone

SAMPLES = Path(__file__).parent / "idecor_samples"
KEY = "360124"
LAW = "Expte 0423-031865-2008 - Ley 10796/2022"
HOSPITAL = "HOSPITAL MUNICIPAL DE NOETINGER"
METRIC = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::22174"}}
SOURCE_LINE = "Source: IDECOR, Infraestructura de Datos Espaciales de la Provincia de Córdoba."


@pytest.fixture(autouse=True)
def no_connections(monkeypatch):
    """Reading a directory opens none."""

    def refuse(*args, **kwargs):
        raise AssertionError("A connection was opened.")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", refuse)


def _municipality(name="Noetinger", key=KEY):
    municipality = make_municipality(name)
    with admin_session() as session, session.begin():
        session.add(MunicipalitySettings(municipality_id=municipality.id, idecor_key=key))
    return municipality


def _import(*args, slug="noetinger", directory=SAMPLES):
    result = CliRunner().invoke(
        cli.app, ["import-idecor", slug, *args, "--from-dir", str(directory)]
    )
    assert result.exception is None or isinstance(result.exception, SystemExit), result.exception
    return result


def _done(*args, **options) -> list[str]:
    result = _import(*args, **options)
    assert result.exit_code == 0, result.output
    return result.output.splitlines()


def _refused(*args, **options) -> str:
    result = _import(*args, **options)
    assert result.exit_code == 1
    return result.output.strip()


def _zones():
    with admin_session() as session:
        return session.execute(
            select(Zone.name, ZoneVersion.version, ZoneVersion.source, ZoneVersion.valid_to)
            .join(ZoneVersion, ZoneVersion.zone_id == Zone.id)
            .order_by(Zone.name, ZoneVersion.version)
        ).all()


def _features(*conditions) -> list[ReferenceFeature]:
    with admin_session() as session:
        return list(
            session.scalars(
                select(ReferenceFeature)
                .where(*conditions)
                .options(undefer(ReferenceFeature.location))
                .order_by(ReferenceFeature.source_id)
            )
        )


def _nothing_stored() -> bool:
    return not _zones() and not _features()


# Files of made-up answers. The samples' radius is about four kilometres wide around here.
CENTER = (4_565_000.0, 6_420_000.0)


def _box(half=1000.0, east=0.0) -> list[list[list[float]]]:
    x, y = CENTER[0] + east, CENTER[1]
    return [
        [
            [x - half, y - half],
            [x + half, y - half],
            [x + half, y + half],
            [x - half, y + half],
            [x - half, y - half],
        ]
    ]


def _write(directory, layer, *features, crs=METRIC, slug="noetinger") -> None:
    body = {"type": "FeatureCollection", "features": list(features), "crs": crs}
    (directory / f"{slug}_{layer}_epsg22174.json").write_text(json.dumps(body))


def _radius(coordinates=None, kind="Polygon", key=KEY, **properties) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": kind, "coordinates": coordinates or _box()},
        "properties": {"key": key, "url": LAW} | properties,
    }


def _school(number, x=0.0, y=0.0, **properties) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [CENTER[0] + x, CENTER[1] + y]},
        "properties": {"id": number, "nombre": f"Escuela {number}"} | properties,
    }


SCHOOLS = "establecimientos_educativos"


# The radius


def test_the_radius_becomes_a_zone_with_its_law():
    municipality = _municipality()

    output = _done("--radius")

    assert output[0] == f"Radio urbano: 1 zone created, 1263.5 ha ({LAW})."
    assert output[1:] == [
        SOURCE_LINE,
        f"  {SAMPLES / 'noetinger_radios_urbanos_epsg22174.json'}",
        f"Read on {get_today():%Y-%m-%d}.",
    ]
    assert _zones() == [("Radio urbano", 1, LAW, None)]
    with admin_session() as session:
        area, valid, outline = session.execute(
            select(
                func.ST_Area(func.geography(ZoneVersion.boundary)),
                func.ST_IsValid(ZoneVersion.boundary),
                ZoneVersion.boundary,
            )
        ).one()
        owner = session.scalar(select(Zone.municipality_id))
    assert valid and area / 10_000 == pytest.approx(1263.6, rel=0.01)
    # In degrees and not rounded to ten metres, as IDECOR's own degrees are.
    longitude, latitude = outline["coordinates"][0][0][0]
    assert (longitude, latitude) == (
        pytest.approx(-62.323197, abs=2e-6),
        pytest.approx(-32.339208, abs=2e-6),
    )
    assert owner == municipality.id


def test_importing_twice_leaves_one_zone_and_one_version():
    _municipality()
    _done("--radius")

    output = _done("--radius")

    assert output[0].startswith("Radio urbano: 1 zone unchanged, ")
    assert _zones() == [("Radio urbano", 1, LAW, None)]


def test_a_changed_boundary_adds_a_version_and_closes_the_one_before(tmp_path):
    _municipality()
    _done("--radius")
    _write(tmp_path, "radios_urbanos", _radius(url="Ley 11000/2027"))

    output = _done("--radius", directory=tmp_path)

    assert output[0] == "Radio urbano: 1 zone moved, 400.0 ha (Ley 11000/2027)."
    [old, new] = _zones()
    assert (old.version, old.source, old.valid_to is None) == (1, LAW, False)
    assert (new.version, new.source, new.valid_to) == (2, "Ley 11000/2027", None)


def test_another_law_over_the_same_outline_moves_nothing(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius(url=None))
    assert _done("--radius", directory=tmp_path)[0] == "Radio urbano: 1 zone created, 400.0 ha."
    _write(tmp_path, "radios_urbanos", _radius(url=" Ley 1 "))

    assert "unchanged" in _done("--radius", directory=tmp_path)[0]

    assert _zones() == [("Radio urbano", 1, "Ley 1", None)]


def test_a_zone_somebody_drew_with_that_name_is_moved_and_others_are_reported():
    municipality = _municipality()
    inside = {
        "type": "Polygon",
        "coordinates": [
            [
                [-62.32, -32.36],
                [-62.31, -32.36],
                [-62.31, -32.37],
                [-62.32, -32.37],
                [-62.32, -32.36],
            ]
        ],
    }
    make_zone(municipality, "RADIO URBANO", inside)
    make_zone(municipality, "Casco urbano", inside)

    output = _done("--radius")

    assert output[0].startswith("Radio urbano: 1 zone moved, ")
    assert re.fullmatch(
        r"  Warning: Casco urbano and RADIO URBANO share 10[0-9]\.\d\d ha\.", output[1]
    )
    assert [(z.name, z.version, z.source) for z in _zones()] == [
        ("Casco urbano", 1, ""),
        ("RADIO URBANO", 1, ""),
        ("RADIO URBANO", 2, LAW),
    ]


def test_a_retired_zone_of_that_name_is_left_in_the_past():
    municipality = _municipality()
    zone = make_zone(municipality, "Radio urbano")
    with admin_session() as session, session.begin():
        session.get(Zone, zone.id).retired_at = datetime(2026, 1, 1, tzinfo=UTC)

    assert "zone created" in _done("--radius")[0]


def test_what_was_imported_from_where_is_in_the_audit_trail_as_the_systems():
    _municipality()

    _done("--radius", "--layers", "health")

    with admin_session() as session:
        entries = session.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
        settings_id = str(session.scalar(select(MunicipalitySettings.id)))
        zone_id = str(session.scalar(select(Zone.id)))
        author = session.scalar(select(Zone.created_by))
    assert {entry.user_id for entry in entries} == {None} and author is None
    radius_file = str(SAMPLES / "noetinger_radios_urbanos_epsg22174.json")
    changes = {(e.entity_type, e.action): e for e in entries}
    assert changes[("zone_versions", "create")].changes == {
        "zone_id": zone_id,
        "version": 1,
        "source": LAW,
    }
    assert changes[("zones", "update")].changes == {"imported_from": radius_file, "law": LAW}
    layers = changes[("municipality_settings", "update")]
    assert layers.entity_id == settings_id
    assert layers.changes == {
        "reference_layers": {
            "health": {
                "imported_from": str(SAMPLES / "noetinger_Centros_Salud.geojson"),
                "features": 1,
            }
        }
    }


BOWTIE = [[[0, 0], [1000, 1000], [1000, 0], [0, 1000], [0, 0]]]


@pytest.mark.parametrize(
    ("feature", "reason"),
    [
        (
            _radius([[[x + CENTER[0], y + CENTER[1]] for x, y in BOWTIE[0]]]),
            "The boundary crosses itself: ",
        ),
        (_radius([_box()[0][:-1]]), "The boundary is not closed"),
        (_radius(_box(0.5)), "The zone encloses almost no area."),
        (_radius() | {"geometry": None}, f"the urban radius {KEY} has no usable boundary."),
        (
            _radius([1.0, 2.0], "Point"),
            f"the urban radius {KEY} has no usable boundary.",
        ),
        (_radius([[["a", "b"]]]), f"the urban radius {KEY} has no usable boundary."),
        (_radius([[[float("nan"), 1.0]]]), f"the urban radius {KEY} has no usable boundary."),
        (_radius([[[True, 1.0]]]), f"the urban radius {KEY} has no usable boundary."),
        (_radius(key="999999"), f"expected one urban radius with key {KEY}, found 0."),
        ("text", f"expected one urban radius with key {KEY}, found 0."),
        (
            {"type": "Feature", "properties": None},
            f"expected one urban radius with key {KEY}, found 0.",
        ),
    ],
)
def test_a_radius_that_cannot_be_used_changes_nothing(tmp_path, feature, reason):
    _municipality()
    _write(tmp_path, "radios_urbanos", feature)
    _write(tmp_path, SCHOOLS, _school(1))

    output = _refused("--radius", "--layers", "schools", directory=tmp_path)

    assert output.startswith("Nothing was changed. radios_urbanos: ")
    assert reason in output
    assert _nothing_stored()


def test_two_radii_with_the_same_key_are_not_chosen_between(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius(), _radius())

    assert "found 2." in _refused("--radius", directory=tmp_path)


def test_the_radius_of_another_town_in_the_answer_is_ignored(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius(key="360125"), _radius())

    assert "zone created" in _done("--radius", directory=tmp_path)[0]


def test_a_key_that_is_a_number_in_the_answer_is_the_same_key(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius(key=360124))

    assert "zone created" in _done("--radius", directory=tmp_path)[0]


# Facilities


def test_the_samples_give_eleven_schools_and_a_health_centre():
    _municipality()

    output = _done("--layers", "health,schools")

    assert output[:2] == [
        "health: 1 features read; 1 created, 0 moved or changed, 0 unchanged, 0 removed; "
        "0 skipped, 0 outside the radius.",
        "schools: 11 features read; 11 created, 0 moved or changed, 0 unchanged, 0 removed; "
        "0 skipped, 0 outside the radius.",
    ]
    assert output.count("  Warning: in degrees, which IDECOR rounds to about 10 m.") == 2
    # The radius only said where to look.
    assert _zones() == []
    [hospital] = _features(ReferenceFeature.layer == "health")
    assert (hospital.source_id, hospital.name) == ("479", HOSPITAL)
    assert hospital.properties == {
        "type": "Con atención médica diaria y con especialidades y/o otras profesiones",
        "address": "INTENDENTE MARANGON Y CUPERTINO SALINAS",
        "sector": "MUNICIPAL",
    }
    assert hospital.location == {"type": "Point", "coordinates": [-62.3079, -32.3654]}
    assert hospital.source_url == str(SAMPLES / "noetinger_Centros_Salud.geojson")
    alem = next(f for f in _features() if f.name == "ESCUELA LEANDRO N. ALEM")
    assert alem.properties == {
        "level": "1. Común - Primario",
        "address": "ANDRES COSTA 486",
        "sector": "Estatal",
    }
    assert len(_features(ReferenceFeature.layer == "schools")) == 11
    # They are not records of any zone.
    with admin_session() as session:
        assert session.scalar(select(func.count()).select_from(RecordZone)) == 0


def test_a_second_import_replaces_rather_than_duplicates(tmp_path):
    _municipality()
    _done("--layers", "health,schools")
    before = {f.source_id: f.id for f in _features()}

    output = _done("--layers", "schools,health,schools")

    assert output[0].startswith("schools: 11 features read; 0 created, 0 moved or changed, 11 unch")
    assert {f.source_id: f.id for f in _features()} == before
    _write(tmp_path, "radios_urbanos", _radius())
    _write(
        tmp_path,
        SCHOOLS,
        _school(1, nombre="Una"),
        _school(2),
        _school(3),
        _school(4, est_sector="x"),
    )
    _done("--layers", "schools", directory=tmp_path)
    _write(
        tmp_path,
        SCHOOLS,
        _school(1, nombre="Otra"),
        _school(2, x=10),
        _school(3),
        _school(4, est_sector="y"),
        _school(5),
    )

    output = _done("--layers", "schools", directory=tmp_path)

    assert output[0] == (
        "schools: 5 features read; 1 created, 3 moved or changed, 1 unchanged, 0 removed; "
        "0 skipped, 0 outside the radius."
    )
    schools = _features(ReferenceFeature.layer == "schools")
    assert [(f.source_id, f.name) for f in schools] == [
        ("1", "Otra"),
        ("2", "Escuela 2"),
        ("3", "Escuela 3"),
        ("4", "Escuela 4"),
        ("5", "Escuela 5"),
    ]
    # The other layer is another import's.
    assert len(_features(ReferenceFeature.layer == "health")) == 1


def test_what_is_no_longer_published_is_removed(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    _write(tmp_path, SCHOOLS, _school(1), _school(2))
    _done("--layers", "schools", directory=tmp_path)
    _write(tmp_path, SCHOOLS, _school(2))

    output = _done("--layers", "schools", directory=tmp_path)

    assert "0 created, 0 moved or changed, 1 unchanged, 1 removed;" in output[0]
    assert [f.source_id for f in _features()] == ["2"]


def test_what_cannot_be_shown_is_skipped_and_counted(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    good = _school(1)
    bad = [
        good | {"geometry": None},
        good | {"geometry": {"type": "MultiPoint", "coordinates": [[1, 2]]}},
        good | {"geometry": {"type": "Point", "coordinates": [CENTER[0]]}},
        good | {"geometry": {"type": "Point", "coordinates": ["x", "y"]}},
        good | {"geometry": {"type": "Point", "coordinates": None}},
        good | {"properties": None},
        _school(None),
        _school(2, nombre=None),
        _school(3, nombre="  "),
        "not a feature",
        # Said twice.
        _school(1, nombre="Repetida"),
    ]
    _write(tmp_path, SCHOOLS, good, *bad)

    output = _done("--layers", "schools", directory=tmp_path)

    assert output[0] == (
        "schools: 12 features read; 1 created, 0 moved or changed, 0 unchanged, 0 removed; "
        "11 skipped, 0 outside the radius."
    )
    assert [f.name for f in _features()] == ["Escuela 1"]


def test_a_place_outside_the_world_is_skipped(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    nowhere = _school(1) | {"geometry": {"type": "Point", "coordinates": [-62.3, 95]}}
    _write(tmp_path, SCHOOLS, nowhere, crs=None)

    assert "1 skipped" in _done("--layers", "schools", directory=tmp_path)[0]


def test_those_of_the_next_town_are_left_out(tmp_path):
    _municipality()
    # A triangle: its box has corners that are not inside it.
    [ring] = _box()
    _write(tmp_path, "radios_urbanos", _radius([[ring[0], ring[1], ring[2], ring[0]]]))
    _write(tmp_path, SCHOOLS, _school(1, x=500, y=-500), _school(2, x=-900, y=900))

    output = _done("--layers", "schools", directory=tmp_path)

    assert output[0].endswith("0 skipped, 1 outside the radius.")
    assert [f.source_id for f in _features()] == ["1"]


@pytest.mark.parametrize(
    ("level", "shown"),
    [
        ('["1. Común - Primario", " 2. Común "]', "1. Común - Primario; 2. Común"),
        ('[""]', None),
        ("[roto", "[roto"),
        ("  Primario \n urbano ", "Primario urbano"),
        (None, None),
        (7, "7"),
        ("x" * 400, "x" * 300),
    ],
)
def test_values_are_kept_as_people_read_them(tmp_path, level, shown):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    _write(tmp_path, SCHOOLS, _school(1, nivel=level, nombre="N" * 400, cueanexo="secret"))

    _done("--layers", "schools", directory=tmp_path)

    [school] = _features()
    assert school.properties == ({"level": shown} if shown else {})
    assert school.name == "N" * 300


def test_a_health_centre_without_category_has_its_type(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    centre = _school(9) | {
        "properties": {
            "id": 9,
            "establecimiento_salud": "Dispensario",
            "categoria": " ",
            "tipo": "ESSIDT",
        }
    }
    _write(tmp_path, "Centros_Salud", centre)

    _done("--layers", "health", directory=tmp_path)

    [found] = _features()
    assert (found.name, found.properties) == ("Dispensario", {"type": "ESSIDT"})


def test_a_layer_with_five_hundred_features_comes_through(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    _write(tmp_path, SCHOOLS, *(_school(n, x=n, y=n % 30) for n in range(500)))

    output = _done("--layers", "schools", directory=tmp_path)

    assert output[0].startswith("schools: 500 features read; 500 created, ")
    assert len(_features()) == 500


def test_a_problem_with_the_facilities_leaves_the_radius_as_it_was(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    (tmp_path / f"noetinger_{SCHOOLS}.geojson").write_text("<xml/>")

    output = _refused("--radius", "--layers", "schools", directory=tmp_path)

    assert output == (f"Nothing was changed. noetinger_{SCHOOLS}.geojson: the answer is not JSON.")
    assert _nothing_stored()


def test_the_import_of_one_never_writes_the_others(tmp_path):
    noetinger, saira = _municipality(), _municipality("Saira", "360125")
    _done("--radius", "--layers", "schools")
    _write(tmp_path, "radios_urbanos", _radius(key="360125"), slug="saira")
    # The same school, with the same identifier: both towns' radii overlap.
    _write(tmp_path, SCHOOLS, _school(1035), slug="saira")

    _done("--radius", "--layers", "schools", slug="saira", directory=tmp_path)

    def owned(municipality):
        with admin_session() as session:
            return (
                session.scalar(select(func.count()).where(Zone.municipality_id == municipality.id)),
                sorted(
                    session.scalars(
                        select(ReferenceFeature.name).where(
                            ReferenceFeature.municipality_id == municipality.id,
                            ReferenceFeature.source_id == "1035",
                        )
                    )
                ),
            )

    assert owned(noetinger) == (1, ["ESCUELA LEANDRO N. ALEM"])
    assert owned(saira) == (1, ["Escuela 1035"])


# The command


def test_without_a_key_it_says_who_sets_it():
    make_municipality()

    assert _refused("--radius") == (
        "Nothing was changed. The municipality has no IDECOR key. The platform operator sets it "
        "in Configuración, tab Mapas y zonas."
    )
    with admin_session() as session, session.begin():
        municipality = session.execute(select(MunicipalitySettings)).first()
    assert municipality is None


def test_a_configuration_without_the_key_is_the_same_as_none():
    _municipality(key=None)

    assert "has no IDECOR key" in _refused("--radius")


@pytest.mark.parametrize(
    ("args", "problem"),
    [
        ([], "Nothing to import: use --radius, --layers or both."),
        (["--layers", " , "], "Nothing to import: use --radius, --layers or both."),
        (["--layers", "health,parcels,streets"], "Unknown: parcels, streets. There are: health,"),
    ],
)
def test_a_command_that_asks_for_nothing_or_the_unknown_is_refused(args, problem):
    _municipality()

    result = _import(*args)

    assert result.exit_code == 2
    assert problem in re.sub(r"[│╭╮╰╯─\s]+", " ", result.output)


def test_an_unknown_municipality_is_refused():
    result = _import("--radius", slug="saira")

    assert result.exit_code == 2
    assert "There is no municipality saira." in re.sub(r"[│╭╮╰╯─\s]+", " ", result.output)


def test_without_a_directory_the_service_is_asked(monkeypatch):
    _municipality()
    asked = []

    def answer(self, request):
        asked.append(request.url.params["typeNames"])
        file = SAMPLES / "noetinger_radios_urbanos_epsg22174.json"
        return httpx2.Response(200, content=file.read_bytes(), request=request)

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", answer)

    result = CliRunner().invoke(cli.app, ["import-idecor", "noetinger", "--radius"])

    assert result.exit_code == 0, result.output
    assert asked == ["idecor:radios_urbanos"]
    assert "  https://idecor-ws.mapascordoba.gob.ar/geoserver/wfs?service=WFS" in result.output


# What each part is asked for


class Recorded(Directory):
    """Saved answers, and what they were asked with."""

    def __init__(self) -> None:
        super().__init__(SAMPLES, "noetinger")
        self.asked: list[tuple] = []

    def radius(self, key):
        self.asked.append(("radius", key))
        return super().radius(key)

    def facilities(self, layer, box):
        self.asked.append((layer, box))
        return super().facilities(layer, box)


def test_the_radius_is_asked_for_by_key_and_the_facilities_by_its_box():
    municipality = _municipality()
    source = Recorded()

    with tenant_session(municipality.id) as db:
        import_official(
            system_context(db, municipality.id),
            source,
            radius=False,
            layers=["schools"],
            now=datetime(2026, 11, 26, tzinfo=UTC),
        )

    asked_radius, (layer, (west, south, east, north)) = source.asked
    assert asked_radius == ("radius", KEY)
    assert layer == SCHOOLS
    # docs/idecor/README.md, to the fourth decimal it was written with.
    assert (west, south, east, north) == (
        pytest.approx(-62.3407, abs=1e-4),
        pytest.approx(-32.3794, abs=1e-4),
        pytest.approx(-62.2839, abs=1e-4),
        pytest.approx(-32.3392, abs=1e-4),
    )
    assert {f.imported_at for f in _features()} == {datetime(2026, 11, 26, tzinfo=UTC)}


def test_another_zone_is_not_taken_for_the_radius():
    municipality = _municipality()
    make_zone(municipality, "Casco urbano")

    assert "1 zone created" in _done("--radius")[0]

    assert [(z.name, z.version) for z in _zones()] == [("Casco urbano", 1), ("Radio urbano", 1)]


def test_overlaps_between_other_zones_are_not_reported():
    municipality = _municipality()
    for name in ("Lejos", "También lejos"):
        make_zone(municipality, name)

    assert not any("Warning" in line for line in _done("--radius"))


def test_a_radius_in_degrees_is_taken_with_a_warning(tmp_path):
    _municipality()
    file = "noetinger_radios_urbanos.geojson"
    (tmp_path / file).write_bytes((SAMPLES / file).read_bytes())

    output = _done("--radius", directory=tmp_path)

    assert "1 zone created" in output[0]
    assert "  Warning: in degrees, which IDECOR rounds to about 10 m." in output


def test_several_left_out_are_counted_one_by_one(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    _write(tmp_path, SCHOOLS, *(_school(n, x=5000) for n in range(3)))

    assert _done("--layers", "schools", directory=tmp_path)[0].endswith("3 outside the radius.")


def test_the_audit_trail_counts_what_is_there_whatever_changed(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    _write(tmp_path, SCHOOLS, _school(1), _school(2))
    _done("--layers", "schools", directory=tmp_path)
    _write(tmp_path, SCHOOLS, _school(1), _school(2, x=5), _school(3))
    _done("--layers", "schools", directory=tmp_path)

    with admin_session() as session:
        entries = session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "municipality_settings")
            .order_by(AuditLog.created_at)
        ).all()
    counts = [e.changes["reference_layers"]["schools"]["features"] for e in entries]
    assert counts == [2, 3]


def test_a_radius_alone_leaves_no_trace_of_layers():
    _municipality()
    _done("--radius")

    with admin_session() as session:
        types = set(session.scalars(select(AuditLog.entity_type)))
    assert types == {"zones", "zone_versions"}


def test_an_altitude_is_dropped_and_empty_parts_too(tmp_path):
    _municipality()
    _write(tmp_path, "radios_urbanos", _radius())
    school = _school("x" * 150, nivel='["Primario", " ", "Medio"]')
    school["geometry"]["coordinates"].append(120.0)
    _write(tmp_path, SCHOOLS, school)

    _done("--layers", "schools", directory=tmp_path)

    [found] = _features()
    assert len(found.location["coordinates"]) == 2
    assert found.properties == {"level": "Primario; Medio"}
    assert found.source_id == "x" * 100
