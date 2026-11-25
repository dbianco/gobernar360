from tests.contract import administrator, check_reference, check_trace, write
from tests.economic.factories import (
    BASE,
    make_actor,
    make_economic_person,
    make_tool,
    make_tool_category,
    make_tool_subcategory,
)


def test_what_is_created_leaves_a_trace_of_what_it_was(client):
    municipality = administrator(client, "economic")
    category = make_tool_category(municipality)
    tool = make_tool(municipality, category)
    actor, person = make_actor(municipality), make_economic_person(municipality)
    assignment = {"tool_id": str(tool.id), "date": "2026-03-10", "note": "x"}

    for path, body in (
        ("actor-types", {"name": "Comercio"}),
        ("sectors", {"name": "Alimentos"}),
        ("tool-categories", {"name": "Crédito"}),
        ("tool-subcategories", {"category_id": str(category.id), "name": "Micro"}),
        ("tools", {"category_id": str(category.id), "name": "Taller", "audience": "actors"}),
        ("actors", {"name": "Panadería", "employee_count": 3}),
        (f"actors/{actor.id}/people", {"person_id": str(person.id), "role": "owner"}),
        ("assignments", assignment | {"actor_id": str(actor.id)}),
        ("assignments", assignment | {"person_id": str(person.id)}),
    ):
        more = {"actor_id": str(actor.id)} if path.endswith("/people") else {}
        check_trace(client, "POST", f"{BASE}/{path}", body, "create", **more)


def test_a_person_incorporated_leaves_a_trace_of_who_and_how(client):
    administrator(client, "economic")
    person = {"first_name": "Juana", "last_name": "Pérez"}
    body = {"person": person, "occupation": "Herrera", "employment_status": "employed"}

    from tests.contract import trail

    made = write(client, "POST", f"{BASE}/people", body).json()

    [entry] = [e for e in trail() if e.entity_type == "economic_people"]
    assert entry.changes == {
        "person_id": made["person"]["id"],
        "occupation": "Herrera",
        "employment_status": "employed",
    }


def test_only_what_was_sent_of_an_assignment_changes(client):
    municipality = administrator(client, "economic")
    body = {
        "tool_id": str(make_tool(municipality).id),
        "actor_id": str(make_actor(municipality).id),
        "date": "2026-03-10",
        "note": "Primera",
    }
    made = write(client, "POST", f"{BASE}/assignments", body).json()
    url = f"{BASE}/assignments/{made['id']}"

    check_trace(client, "PATCH", url, {"date": "2026-03-11"}, "update")
    check_trace(client, "PATCH", url, {"note": "Segunda"}, "update")

    [assignment] = client.get(f"{BASE}/assignments", params={"year": 2026}).json()["items"]
    assert (assignment["date"], assignment["note"]) == ("2026-03-11", "Segunda")


def test_a_tool_is_offered_only_to_its_audience_and_it_is_said_which(client):
    municipality = administrator(client, "economic")
    actor, person = make_actor(municipality), make_economic_person(municipality)
    recipients = {"actors": {"actor_id": str(actor.id)}, "people": {"person_id": str(person.id)}}

    for audience, other in (("actors", "people"), ("people", "actors")):
        tool = make_tool(municipality, name=audience, audience=audience)
        body = {"tool_id": str(tool.id), "date": "2026-03-10"}
        refused = client.post(f"{BASE}/assignments", json=body | recipients[other])
        assert refused.status_code == 422
        assert refused.json()["error"] == {
            "code": "validation_error",
            "message": f"This tool is not offered to {other}.",
        }
        write(client, "POST", f"{BASE}/assignments", body | recipients[audience])


def test_an_assignment_has_exactly_one_recipient(client):
    municipality = administrator(client, "economic")
    body = {"tool_id": str(make_tool(municipality).id), "date": "2026-03-10"}
    both = {
        "actor_id": str(make_actor(municipality).id),
        "person_id": str(make_economic_person(municipality).id),
    }

    for recipients in ({}, both):
        refused = client.post(f"{BASE}/assignments", json=body | recipients)
        assert refused.status_code == 422
        [detail] = refused.json()["error"]["details"]
        assert detail["message"].endswith("exactly one of actor_id and person_id is required")


def test_a_person_is_linked_to_an_actor_once_and_to_others_too(client):
    municipality = administrator(client, "economic")
    first, second = make_actor(municipality, "Uno"), make_actor(municipality, "Dos")
    person, other = make_economic_person(municipality), make_economic_person(municipality, "Ana")
    link = {"person_id": str(person.id), "role": "owner"}
    write(client, "POST", f"{BASE}/actors/{first.id}/people", link)

    again = client.post(f"{BASE}/actors/{first.id}/people", json=link)

    assert again.status_code == 409
    assert again.json()["error"] == {
        "code": "conflict",
        "message": "This person is already linked to the actor.",
    }
    write(client, "POST", f"{BASE}/actors/{second.id}/people", link)
    write(client, "POST", f"{BASE}/actors/{first.id}/people", link | {"person_id": str(other.id)})


def test_a_document_looked_up_must_be_one(client):
    administrator(client, "economic")

    refused = client.get(f"{BASE}/people/lookup", params={"dni": "12"})

    assert refused.status_code == 422
    assert refused.json()["error"] == {
        "code": "validation_error",
        "message": "dni must have 6 to 9 digits.",
    }


def test_people_without_a_document_are_each_their_own(client):
    administrator(client, "economic")
    made = [
        write(
            client,
            "POST",
            f"{BASE}/people",
            {"person": {"first_name": name, "last_name": "Pérez"}},
        ).json()
        for name in ("Ana", "Juana")
    ]

    assert made[0]["person"]["id"] != made[1]["person"]["id"]


def test_ids_that_are_not_the_municipality_s_are_refused_by_name(client):
    municipality = administrator(client, "economic")
    category = make_tool_category(municipality)
    tool, actor = make_tool(municipality, category), make_actor(municipality)
    make_tool_subcategory(municipality, category)
    assignment = {"tool_id": str(tool.id), "date": "2026-03-10"}

    for method, path, body, field in (
        ("POST", "tool-subcategories", {"name": "Micro"}, "category_id"),
        ("POST", "tools", {"name": "Taller"}, "category_id"),
        ("POST", "actors", {"name": "Uno"}, "actor_type_id"),
        ("POST", "actors", {"name": "Uno"}, "sector_id"),
        ("PATCH", f"actors/{actor.id}", {}, "sector_id"),
        ("POST", f"actors/{actor.id}/people", {"role": "owner"}, "person_id"),
        ("POST", "assignments", assignment | {"actor_id": str(actor.id)}, "tool_id"),
        ("POST", "assignments", assignment, "actor_id"),
        ("POST", "assignments", assignment, "person_id"),
    ):
        check_reference(client, method, f"{BASE}/{path}", body, field)
