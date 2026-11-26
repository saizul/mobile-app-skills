# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## What counts as a vulnerability

These skills are run by AI agents on real app projects that hold signing keys and user
data, so unsafe guidance is treated like a code vulnerability:

- A script that prints a secret value (keystore or key passwords, API keys, tokens from
  `key.properties`, Gradle files or plists) instead of only its location
- A script that writes files, makes network calls, executes project code or build tools
- Code injection or path traversal through crafted manifests, plists, crash exports or
  archives (for example a zip entry name that makes the size report read outside the archive)
- Crash triage output that leaks personal data the scrubber should have removed
- A `SKILL.md` workflow that tells the agent to sign, upload, publish, change a rollout,
  or handle signing material without asking the user first
- Security advice that is wrong in a way that leaves users exposed, e.g. recommending an
  ATS or network security exception that disables TLS for all hosts

A check that misses a problem (false negative) is a normal bug: please open an issue.

## Reporting

Please **do not** open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/saizul/mobile-app-skills/security/advisories/new)
with the affected skill, version, impact and steps to reproduce. Remove real app
identifiers, user data and secrets from examples.

You will get an answer within 5 working days. Fixes are released as soon as possible and
credited in the changelog unless you prefer otherwise.

Vulnerabilities in Flutter, React Native, the Android SDK or Xcode belong to those projects.
