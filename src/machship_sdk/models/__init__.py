"""Public exports for MachShip model types."""

from __future__ import annotations

from .base import MachShipBaseModel
from .generated import (
    CarrierAccountLite,
    CarrierServiceLite,
    CarrierWithAccountsAndServicesLite,
    CompanyLocationV2,
    CompanyV2,
    ConsignmentV2,
    CreateConsignmentComplexItemsV2,
    CreateConsignmentItemV2,
    CreateConsignmentResponseV2,
    CreateConsignmentV2,
    FileInfo,
    MachshipValidationResultV2,
    ManifestForListWithConsignments,
    RouteRequestComplexItemsV2,
    RouteRequestV2,
    RoutesResponseV2,
)

RouteRequest = RouteRequestV2
RouteRequestComplex = RouteRequestComplexItemsV2
CreateConsignmentRequest = CreateConsignmentV2
CreateConsignmentComplexRequest = CreateConsignmentComplexItemsV2
CreateConsignmentResponse = CreateConsignmentResponseV2
QuoteResponse = RoutesResponseV2
QuoteRequest = RouteRequestV2
QuoteRequestComplex = RouteRequestComplexItemsV2
Consignment = ConsignmentV2
Company = CompanyV2
CompanyLocation = CompanyLocationV2
Carrier = CarrierWithAccountsAndServicesLite
CarrierAccount = CarrierAccountLite
CarrierService = CarrierServiceLite
Manifest = ManifestForListWithConsignments
FileInfoResponse = FileInfo
ValidationResult = MachshipValidationResultV2

__all__ = [
    "MachShipBaseModel",
    "RouteRequestV2",
    "RouteRequestComplexItemsV2",
    "CreateConsignmentV2",
    "CreateConsignmentItemV2",
    "CreateConsignmentComplexItemsV2",
    "CreateConsignmentResponseV2",
    "RoutesResponseV2",
    "ConsignmentV2",
    "CompanyV2",
    "CompanyLocationV2",
    "CarrierWithAccountsAndServicesLite",
    "CarrierAccountLite",
    "CarrierServiceLite",
    "ManifestForListWithConsignments",
    "FileInfo",
    "MachshipValidationResultV2",
    "RouteRequest",
    "RouteRequestComplex",
    "CreateConsignmentRequest",
    "CreateConsignmentComplexRequest",
    "CreateConsignmentResponse",
    "QuoteResponse",
    "QuoteRequest",
    "QuoteRequestComplex",
    "Consignment",
    "Company",
    "CompanyLocation",
    "Carrier",
    "CarrierAccount",
    "CarrierService",
    "Manifest",
    "FileInfoResponse",
    "ValidationResult",
]
