"""Undocumented enum values MachShip sends must not fail a whole response.

MachShip's ``getCompleted`` returns ``company.companyType`` 0, which its
published schema does not list. Before 0.1.22 the generated ``CompanyType``
accepted only 1-5, so every consignment page carrying it failed validation and
callers saw no consignments at all.
"""

from __future__ import annotations

import logging
from enum import IntEnum

import httpx
import pytest
import respx
from pydantic import ValidationError

from machship_sdk import MachShipClient, MachShipConfig
from machship_sdk.models.base import MachShipBaseModel
from machship_sdk.models.generated import (
    CompanyLite,
    CompanyType,
    ConsignmentsForListGridDomainEntityV2,
)


def _completed_page(company_type: int) -> dict:
    """Build a ``getCompleted`` page whose one row carries ``company_type``."""
    return {
        "object": [
            {
                "id": 41,
                "attachmentCount": 2,
                "company": {"id": 7, "name": "IBS", "companyType": company_type},
            }
        ],
        "errors": [],
    }


def test_company_type_zero_is_a_member() -> None:
    """0 is the value MachShip actually sends, so it is a real member."""
    company = CompanyLite.model_validate({"companyType": 0})

    assert company.company_type is CompanyType.integer_0


def test_a_completed_page_with_company_type_zero_validates() -> None:
    """The consignment rows survive, attachment counts included."""
    page = ConsignmentsForListGridDomainEntityV2.model_validate(_completed_page(0))

    assert page.object is not None
    assert page.object[0].id == 41
    assert page.object[0].attachment_count == 2


def test_an_unknown_optional_enum_value_reads_as_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A code no release knows yet is logged and dropped, not fatal."""
    with caplog.at_level(logging.WARNING, logger="machship_sdk.models.base"):
        page = ConsignmentsForListGridDomainEntityV2.model_validate(
            _completed_page(9)
        )

    assert page.object is not None
    assert page.object[0].id == 41
    assert page.object[0].company is not None
    assert page.object[0].company.company_type is None
    assert "Unknown CompanyType value 9" in caplog.text


def test_a_known_value_is_kept() -> None:
    """Valid values are untouched by the tolerance."""
    company = CompanyLite.model_validate({"companyType": 4})

    assert company.company_type is CompanyType.integer_4


class _Colour(IntEnum):
    RED = 1


class _Required(MachShipBaseModel):
    colour: _Colour


class _Optional(MachShipBaseModel):
    colour: _Colour | None = None
    count: int | None = None


class _EitherOr(MachShipBaseModel):
    colour: _Colour | int


def test_a_required_enum_still_refuses_an_unknown_value() -> None:
    """Only optional fields are relaxed, so a required one still fails loudly."""
    with pytest.raises(ValidationError):
        _Required.model_validate({"colour": 2})


def test_a_member_passed_in_is_kept() -> None:
    """An enum member, not just its value, passes straight through."""
    assert _Optional.model_validate({"colour": _Colour.RED}).colour is _Colour.RED


def test_a_union_without_none_is_not_relaxed() -> None:
    """Only ``Enum | None`` is relaxed; other unions validate as before."""
    assert _EitherOr.model_validate({"colour": 2}).colour == 2


def test_other_optional_fields_still_validate() -> None:
    """The relaxation is for enums only; a bad int is still an error."""
    assert _Optional.model_validate({"colour": 2}).colour is None
    with pytest.raises(ValidationError):
        _Optional.model_validate({"count": "many"})


def test_get_completed_through_the_client_returns_rows() -> None:
    """The portal's call path: a typed request over a companyType 0 page."""
    with MachShipClient(
        MachShipConfig(base_url="https://example.com", token="secret"),
    ) as client, respx.mock(base_url="https://example.com") as mock:
        mock.get("/apiv2/consignments/getCompleted").mock(
            return_value=httpx.Response(200, json=_completed_page(0))
        )

        page = client.request(
            "GET",
            "/apiv2/consignments/getCompleted",
            response_model=ConsignmentsForListGridDomainEntityV2,
        )

    assert page.object is not None
    assert [row.id for row in page.object] == [41]
