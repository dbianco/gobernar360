"""What the API accepts as an email address."""

import pytest

from gobernar360.platform.schemas import valid_email


@pytest.mark.parametrize(
    ("raw", "email"),
    [
        ("Ana@Noetinger.TEST", "ana@noetinger.test"),
        ("  ana.perez@muni.gob.ar ", "ana.perez@muni.gob.ar"),
    ],
)
def test_an_email_is_kept_normalised(raw, email):
    assert valid_email(raw) == email


@pytest.mark.parametrize(
    "raw",
    ["ana", "@muni.gob.ar", "ana@", "ana@localhost", "ana perez@muni.gob.ar", "ana@b c.ar", ""],
)
def test_what_cannot_be_an_address_is_refused(raw):
    with pytest.raises(ValueError, match="^must be a valid email address$"):
        valid_email(raw)


@pytest.mark.parametrize("raw", ["ana@localhost@muni.gob.ar", "ana@muni.gob.ar@localhost"])
def test_an_address_has_a_single_at_sign(raw):
    with pytest.raises(ValueError):
        valid_email(raw)
