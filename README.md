# govee-hass-connect

Omnibus Home Assistant integration for Govee products, built for segmented/VLAN networks where multicast discovery is unreliable. 

## What This Repo Contains

- `custom_components/govee_hass_connect`: Custom integration domain
- `custom_components/govee_hass_connect/govee_api`: Vendored local API implementation (no runtime PyPI dependency required)
- `.github/workflows/release.yml`: Automated semantic version + PyPI publish pipeline

## SemVer + Auto Release (Already Wired)

This repo uses `python-semantic-release`.

Commit prefixes drive version bumps:

- `feat:` -> minor bump
- `fix:` -> patch bump
- `perf:` -> patch bump
- `refactor:` -> patch bump
- `feat!:` or `BREAKING CHANGE:` -> major bump

Every push to `main` runs:

1. Semantic version calculation
2. Git tag + GitHub release creation
3. Python package build
4. Publish to PyPI

## Required One-Time GitHub Setup

1. In GitHub repo settings, enable Actions write permissions for `GITHUB_TOKEN`.
2. In PyPI, create a project named `govee-hass-connect`.
3. In PyPI Trusted Publishers, add this GitHub repo/workflow (`.github/workflows/release.yml`).

No PyPI API token is needed when using trusted publishing.

## First Release

Make a conventional commit and push to `main`:

```bash
git add .
git commit -m "feat: bootstrap omnibus integration"
git push origin main
```

That will produce the first release tag and publish to PyPI.

## Fast Iteration Mode

If you want to keep shipping aggressively, just keep committing with `fix:` and `feat:`.
Version numbers will increase automatically as far as needed.
