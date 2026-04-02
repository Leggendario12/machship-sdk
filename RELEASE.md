# Release Checklist

Use this checklist before publishing `machship-sdk` to PyPI.

## Before You Tag

1. Update the version in [pyproject.toml](pyproject.toml).
2. Regenerate the MachShip models if the schema changed.
3. Run the test suite.
4. Build the release artifacts.
5. Check the built distributions.

```bash
uv run pytest
uv run python -m build
uv run twine check dist/*
```

## PyPI Setup

Configure a PyPI trusted publisher for this repository:

- Owner: `Leggendario12`
- Repository: `machship-sdk`
- Workflow file: `.github/workflows/publish.yml`
- Environment: `pypi`

See the PyPI trusted publishing docs for the exact UI flow:
https://docs.pypi.org/trusted-publishers/adding-a-publisher/

## Publish

1. Create a release tag that matches the version in `pyproject.toml`.
2. Push the tag to `origin`.

```bash
git tag v0.1.1
git push origin v0.1.1
```

GitHub Actions will run [.github/workflows/publish.yml](.github/workflows/publish.yml),
build the source distribution and wheel, validate them with `twine check`,
and publish to PyPI.

## After Publish

1. Confirm the release appears on PyPI.
2. Verify the install command works from a clean environment.
3. Create a GitHub release if you use one for changelog tracking.
