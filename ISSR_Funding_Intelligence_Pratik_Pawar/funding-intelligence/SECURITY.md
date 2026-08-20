# Security Policy

## Reporting a vulnerability

Please report security issues privately rather than opening a public issue.

Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository, or email the maintainer at pratikpawar1565@gmail.com.

Please include what you were doing, what happened, and how to reproduce it.
You should expect an acknowledgement within a week. This is a small
research-oriented project maintained by volunteers, so please be patient with
response times.

## Scope and deployment expectations

This system ingests **public** federal funding announcements. It stores no
credentials, no personal data, and no proprietary content. That shapes what
counts as a vulnerability here.

The API is currently designed for **single-institution, trusted-network
deployment** and ships with no authentication. This is a deliberate scope
decision, not an oversight, but it means:

- **Do not expose the API directly to the public internet** without putting
  authentication and a reverse proxy in front of it.
- Rate limiting is in-process and per worker (`API_RATE_LIMIT_PER_MINUTE`).
  It protects against a single noisy client, not a distributed attack. Behind
  multiple workers or replicas, enforce limits at the proxy instead.
- CORS origins are configurable via `API_CORS_ORIGINS` and default to
  localhost. Setting it to `*` disables credentialed requests.

Reports we're particularly interested in:

- SQL injection or path traversal in ingestion, storage, or the API
- Unsafe deserialisation of scraped or downloaded content
- Anything allowing a malicious PDF or scraped page to execute code
- Dependency vulnerabilities with a practical exploit path in this codebase

Out of scope:

- Missing authentication on the API (documented above)
- Rate-limit bypass via distributed clients (documented above)
- Vulnerabilities requiring an already-compromised host or database

## Supported versions

The project is pre-1.0 and under active development. Fixes land on `main`;
there are no maintained release branches yet.
