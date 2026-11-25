"""Settings that build what people receive."""

from gobernar360.core.config import Settings, get_settings


def test_links_to_the_web_app_have_a_single_slash():
    for base in ("https://muni.gob.ar", "https://muni.gob.ar/", "https://muni.gob.ar//"):
        settings = get_settings().model_copy(update={"app_url": base})
        assert settings.app_link("/login") == "https://muni.gob.ar/login"


def test_single_sign_on_needs_an_issuer_and_a_client():
    settings = get_settings()

    def configured(**values) -> bool:
        return settings.model_copy(update=values).sso_enabled

    assert configured(oidc_issuer="https://idp.test", oidc_client_id="app")
    assert not configured(oidc_issuer="", oidc_client_id="app")
    assert not configured(oidc_issuer="https://idp.test", oidc_client_id="")


def test_links_have_one_slash_between_the_address_and_the_path():
    for address in ("https://app.test", "https://app.test/", "https://app.testX"):
        link = Settings(app_url=address).app_link("/login")
        assert link == address.rstrip("/") + "/login"
