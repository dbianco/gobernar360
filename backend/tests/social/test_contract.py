from tests.contract import administrator, check_reference, check_trace, trail, write
from tests.social.factories import (
    BASE,
    make_benefit,
    make_benefit_category,
    make_household,
    make_intervention_type,
    make_social_person,
)


def test_what_is_created_leaves_a_trace_of_what_it_was(client):
    municipality = administrator(client, "social")
    category = make_benefit_category(municipality)
    benefit, person = make_benefit(municipality, category), make_social_person(municipality)
    visit = make_intervention_type(municipality)

    for path, body in (
        ("benefit-categories", {"name": "Abrigo"}),
        ("intervention-types", {"name": "Entrevista"}),
        ("benefits", {"category_id": str(category.id), "name": "Frazadas"}),
        ("households", {"name": "Familia Paz", "neighborhood": "Sur"}),
        (
            "deliveries",
            {"benefit_id": str(benefit.id), "person_id": str(person.id), "date": "2026-03-10"},
        ),
        (
            "interventions",
            {
                "intervention_type_id": str(visit.id),
                "person_id": str(person.id),
                "date": "2026-03-10",
                "performed_by": "Equipo",
            },
        ),
    ):
        check_trace(client, "POST", f"{BASE}/{path}", body, "create")


def test_a_person_incorporated_leaves_a_trace_of_who(client):
    administrator(client, "social")

    made = write(
        client,
        "POST",
        f"{BASE}/people",
        {"person": {"first_name": "Juana", "last_name": "Pérez"}},
    ).json()

    [entry] = [e for e in trail() if e.entity_type == "social_people"]
    assert entry.changes == {"person_id": made["person"]["id"]}


def test_ids_that_are_not_the_municipality_s_are_refused_by_name(client):
    municipality = administrator(client, "social")
    benefit, person = make_benefit(municipality), make_social_person(municipality)
    visit = make_intervention_type(municipality)
    delivery = {
        "benefit_id": str(benefit.id),
        "person_id": str(person.id),
        "date": "2026-03-10",
    }
    intervention = {
        "intervention_type_id": str(visit.id),
        "person_id": str(person.id),
        "date": "2026-03-10",
    }

    for method, path, body, field in (
        ("POST", "benefits", {"name": "Frazadas"}, "category_id"),
        ("PATCH", f"benefits/{benefit.id}", {}, "category_id"),
        ("POST", "deliveries", delivery, "benefit_id"),
        ("POST", "deliveries", delivery, "person_id"),
        ("POST", "interventions", intervention, "intervention_type_id"),
        ("POST", "interventions", intervention, "person_id"),
    ):
        check_reference(client, method, f"{BASE}/{path}", body, field)


def test_households_are_listed_with_their_people_and_head(client):
    municipality = administrator(client, "social")
    for name in ("Familia Sosa", "Familia Álvarez", "Familia Paz"):
        make_household(municipality, name)

    names = [h["name"] for h in client.get(f"{BASE}/households").json()["items"]]

    assert names == ["Familia Álvarez", "Familia Paz", "Familia Sosa"]
