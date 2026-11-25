from tests.factories import admin_session, login, make_membership, make_municipality, make_user


def test_the_active_members_are_offered_by_name_to_every_member(client):
    municipality = make_municipality()
    for name in ("zoe", "álvaro", "ana"):
        make_membership(make_user(f"{name}@noetinger.test"), municipality)
    beto = make_user("zz@noetinger.test")
    make_membership(beto, municipality)
    with admin_session() as session, session.begin():
        session.merge(beto).full_name = "beto"
    make_membership(make_user("ida@noetinger.test", active=False), municipality)
    make_membership(make_user("otro@saira.test"), make_municipality("Saira"))
    # No dashboard at all.
    login(client, "ana@noetinger.test")

    members = client.get("/api/members").json()

    assert [m["full_name"] for m in members] == ["Álvaro", "Ana", "beto", "Zoe"]
    assert set(members[0]) == {"id", "full_name"}


def test_the_directory_needs_a_session_and_a_municipality(client):
    assert client.get("/api/members").status_code == 401
    make_user("operador@gobernar360.test", operator=True)
    login(client, "operador@gobernar360.test")
    assert client.get("/api/members").status_code == 403
