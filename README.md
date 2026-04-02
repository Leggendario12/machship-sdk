<div align="center">

# machship-sdk

Unofficial Python SDK for MachShip integrations

![Unofficial](https://img.shields.io/badge/Project-unofficial-critical)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![pip install](https://img.shields.io/badge/pip-machship--sdk-2ea44f?logo=pypi&logoColor=white)](#install)
![Community maintained](https://img.shields.io/badge/Status-community%20maintained-orange)

</div>

> **Unofficial notice**
> This project is a community-maintained SDK. It is not affiliated with,
> endorsed by, or supported by MachShip.

MachShip SDK for Python, with dedicated FusedShip support for live pricing,
ecommerce session tokens, and the direct MachShip API surface when you still
need it.

## What this includes

- `FusedShipClient` for live pricing and ecommerce flows.
- `MachShipClient` for the direct MachShip API surface.
- Sync and async clients.
- Typed Pydantic request and response models.

## When to use which client

- Use `FusedShipClient` for live pricing and ecommerce UI access.
- Use `MachShipClient` if you still need the direct MachShip API surface.

## Install

```bash
pip install machship-sdk
```

If you want to install from git:

```bash
pip install "machship-sdk @ git+ssh://git@github.com/<org>/machship-sdk.git@v0.1.4"
```

## Optional Extras

Install the full feature set:

```bash
pip install "machship-sdk[all]"
```

Install only the pieces you need:

```bash
pip install "machship-sdk[settings]"
pip install "machship-sdk[retries]"
pip install "machship-sdk[logging]"
pip install "machship-sdk[telemetry]"
pip install "machship-sdk[cache]"
pip install "machship-sdk[json]"
pip install "machship-sdk[testing]"
```

Use cases:

- `settings` adds `pydantic-settings` for app-level env loading in Django,
  FastAPI, CLI tools, or workers.
- `retries` adds `tenacity` for transient request retries and backoff on
  429/5xx responses.
- `logging` adds `structlog` for structured request logs.
- `telemetry` adds OpenTelemetry tracing support for outbound API calls.
- `cache` adds `cachetools` for TTL caches around carrier, company, or rate
  lookups.
- `json` adds `orjson` for faster JSON encoding and decoding.
- `testing` adds `respx` for HTTPX request mocking in tests.

## Environment

The clients can read their configuration from environment variables through
`from_env()`.

MachShip:

- `MACHSHIP_BASE_URL`
- `MACHSHIP_TOKEN` or `MACHSHIP_API_TOKEN`

FusedShip:

- `FUSEDSHIP_BASE_URL`
- `FUSEDSHIP_TOKEN`
- `FUSEDSHIP_INTEGRATION_ID`
- `FUSEDSHIP_CLIENT_TOKEN`
- `FUSEDSHIP_STORE_ID`

## App Settings

If you want a single settings object for a Django app or plain Python service,
use `MachShipSDKSettings` from `machship_sdk.settings`:

```python
from machship_sdk import MachShipClient
from machship_sdk.settings import MachShipSDKSettings

app_settings = MachShipSDKSettings(_env_file=".env")

machship_client = MachShipClient(app_settings.to_machship_config())
fusedship_config = app_settings.to_fusedship_config()
```

## Location Lookup

MachShip exposes suburb and postcode lookup endpoints rather than a full
street-address verifier. You can use them to match raw locations or search by
suburb/postcode text:

```python
from machship_sdk import MachShipClient
from machship_sdk.models import (
    LocationSearchOptions,
    LocationSearchOptionsV2,
    RawLocation,
    RawLocationsWithLocationSearchOptions,
)

client = MachShipClient.from_env()

verified_locations = client.return_locations(
    RawLocationsWithLocationSearchOptions(
        raw_locations=[RawLocation(suburb="Melbourne", postcode="3000")],
        location_search_options=LocationSearchOptions(company_id=123),
    )
)

search_results = client.return_locations_with_search_options(
    LocationSearchOptionsV2(company_id=123, retrieval_size=10),
    search="Mel 3000",
)
```

## Usage

### MachShip

```python
from machship_sdk import MachShipClient

client = MachShipClient.from_env()
```

### Enhancements

```python
from machship_sdk.cache import ttl_cache
from machship_sdk.logging import get_logger
from machship_sdk.retries import RetryPolicy
from machship_sdk.telemetry import get_tracer

logger = get_logger()
tracer = get_tracer()

client = MachShipClient(
    machship_config,
    retry_policy=RetryPolicy(attempts=3),
    logger=logger,
    tracer=tracer,
)

@ttl_cache(maxsize=64, ttl=300)
def get_carriers():
    return client.get_available_carriers_accounts_and_services()
```

If you need HTTP mocking in tests, install `machship-sdk[testing]` and use
`respx`:

```python
import httpx
import respx

from machship_sdk import MachShipClient, MachShipConfig

client = MachShipClient(MachShipConfig(base_url="https://example.com", token="secret"))

with respx.mock(base_url="https://example.com") as mock:
    mock.post("/apiv2/authenticate/ping").respond(
        200,
        json={"object": True, "errors": []},
    )
    client.ping()
```

### FusedShip live pricing

```python
from machship_sdk.fusedship import (
    FusedShipAddress,
    FusedShipClient,
    FusedShipLivePricingRequest,
    FusedShipQuote,
    FusedShipQuoteItem,
    FusedShipShippingItem,
    FusedShipShippingOptions,
)

client = FusedShipClient.from_env()

request = FusedShipLivePricingRequest(
    quote=FusedShipQuote(
        warehouse=FusedShipAddress(
            country="AU",
            postal_code="3076",
            province="VIC",
            city="Epping",
            address1="123 main st",
            name="ABC123",
        ),
        shipping_address=FusedShipAddress(
            country="AU",
            postal_code="6720",
            province="WA",
            city="Wickham",
            address1="123 main st",
            name="ABC123",
        ),
        shipping_options=FusedShipShippingOptions(
            authority_to_leave=True,
            residential=False,
        ),
        items=[
            FusedShipQuoteItem(
                name="Banana Bottle 200ml",
                sku="BCE345",
                quantity=5,
                price=328,
                categories=["flavoured_drinks", "bottles"],
                shipping_items=[
                    FusedShipShippingItem(
                        weight=240,
                        length=100,
                        width=20,
                        height=10,
                        item_type="Carton",
                    )
                ],
            )
        ],
    )
)

response = client.quote_live_pricing("your_platform", request)
```

### Ecommerce token

```python
session = client.request_token(
    client_token="your_client_token_here",
    store_id="your_store_id_here",
)

iframe_url = client.build_ecommerce_url(session.session_key, active_tab="quote")
```

### Django or plain Python

The SDK does not require Django. It only reads environment variables, so you
can populate them in any application style:

- `.env` file loaded at startup
- shell environment variables
- Docker or Kubernetes secrets
- Django settings that proxy to `os.environ`

For HTTP mocking in tests, install `machship-sdk[testing]` and use `respx` to
stub the outbound `httpx` calls cleanly.

## Data mapping

FusedShip payloads in this package are modeled with snake_case fields so they
match the example request and response format from the handbook. The models
accept extra fields, which keeps the SDK flexible when FusedShip mappings
evolve.

## Generating Models

The MachShip model file is generated from
[`macship_api_schema/macship_schema.json`](macship_api_schema/macship_schema.json)
with `datamodel-code-generator`. Run this from the repository root:

```bash
uv run datamodel-codegen \
  --input macship_api_schema/macship_schema.json \
  --input-file-type openapi \
  --output src/machship_sdk/models/generated.py \
  --base-class machship_sdk.models.base.MachShipBaseModel \
  --custom-file-header-path macship_api_schema/generated_header.txt \
  --disable-timestamp \
  --use-annotated \
  --use-schema-description \
  --use-field-description \
  --use-inline-field-description \
  --snake-case-field \
  --extra-fields ignore \
  --target-pydantic-version 2.11 \
  --output-model-type pydantic_v2.BaseModel \
  --formatters black isort
```

The schema descriptions populate class and field docstrings where the OpenAPI
spec provides them. The generated file is checked in, so it should be
regenerated rather than edited by hand.

## Publishing To PyPI

Recommended release flow:

1. Bump `version` in `pyproject.toml`.
2. Run `uv run pytest`.
3. Run `uv run python -m build`.
4. Run `uv run twine check dist/*`.
5. Configure a PyPI trusted publisher for this repository:
   - Owner: `Leggendario12`
   - Repository: `machship-sdk`
   - Workflow file: `.github/workflows/publish.yml`
   - Environment: `pypi`
6. Tag the release and push it:

```bash
git tag v0.1.4
git push origin v0.1.4
```

GitHub Actions will build the sdist and wheel, validate the metadata, and
publish the release from `.github/workflows/publish.yml`.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
