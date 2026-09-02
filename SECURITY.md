[🇫🇷 Version française](SECURITY.fr.md) | 🇬🇧 English version

---

# Security Policy

## Supported Versions

This project follows a single rolling `main` branch. There are no maintained release branches; only the latest commit on `main` is supported.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting: go to the [Security tab](https://github.com/MarvinLeRouge/GeoChallenge-Tracker/security/advisories/new) of this repository and click "Report a vulnerability". This keeps the report private until a fix is available.

This project is maintained by a single developer, so response times are best-effort rather than guaranteed on an SLA.

## Scope

In scope: the backend API (`backend/`), the frontend application (`frontend/`), and the Docker/deployment configuration (`docker-compose*.yml`, `ops/`) as defined in this repository.

Out of scope: third-party services the application integrates with (e.g. Geocaching.com, Brevo, tile providers). Report issues with those services directly to their maintainers.
