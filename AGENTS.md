# AGENTS.md

Guidance for Codex CLI and other coding agents that use or work on this repository.

## Using the skills

The skills live in `skills/<name>/SKILL.md` and follow the Agent Skills format. Codex
discovers them when they are copied to `~/.agents/skills/` or `.agents/skills/` (see
README "Install"). If you are reading this file inside the repository instead:

1. Pick the skill whose `description` matches the user's request:

   | Request is about | Skill |
   | --- | --- |
   | store title, subtitle, keywords, description, release notes, ASO, fastlane metadata | `store-listing-writer` |
   | Android permissions, Play permission declarations, exported components, AndroidManifest.xml | `android-permissions-audit` |
   | iOS purpose strings, Info.plist, ATS, privacy manifest, App Review 5.1.1 | `ios-plist-audit` |
   | versions, build numbers, signing, TestFlight, staged rollout, phased release, rollback | `release-checklist` |
   | stack traces, crash exports, top crashes, new crashes in a release | `crash-log-triage` |
   | APK/AAB/IPA size, download size, size budget | `app-size-reduction` |
   | Flutter code review, state management, lints, jank | `flutter-best-practices` |
   | React Native / Expo review, Hermes, New Architecture, upgrades, list performance | `react-native-best-practices` |

2. Read that `SKILL.md` completely and follow its Workflow section in order.
3. Paths such as `scripts/x.py` and `references/y.md` are relative to the skill folder.
   `${CLAUDE_SKILL_DIR}` in the text means that folder; Codex does not expand it.
4. Read files in `references/` only when a workflow step points to them.

## Safety rules (apply to every skill)

- The scripts are read-only and offline. Do not build, sign, upload, publish, change a
  rollout percentage or submit for review on the user's behalf; prepare the change or the
  command and let the user run it.
- Never create, move, print, paste or commit signing material: keystores, `key.properties`,
  `.p12`/`.p8` files, provisioning profiles, store passwords, App Store Connect or Play
  service-account keys, API keys. The scripts report where they are, never their values.
- When signing material or a key was committed, tell the user to rotate it; deleting the
  file is not enough.
- Crash reports, logs and analytics exports can contain personal data. Work on the files
  locally and quote only stack frames and scrubbed messages.
- Store policy claims (what Google Play or App Review allows) can change. Say which
  official page to re-check when a decision depends on it.
- Propose diffs to manifests, plists, Gradle and Xcode files and wait for approval before
  applying them; never edit generated `build/` outputs.

## Working on this repository

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py   # frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

- Scripts: Python 3.8+ standard library only, `#!/usr/bin/env python3`, `argparse` with
  `--help`, `--json` where output is structured, exit 0/1/2 (ok / findings / error).
- Scripts must stay standalone (one file each, no shared module) so a single skill folder
  can be copied on its own.
- Every script needs tests in `tests/test_<skill_with_underscores>.py` with fixtures in
  `tests/fixtures/<area>/`. Use `example.com` hosts and obviously fake values; build
  anything that looks like a key from pieces in test code so secret scanners do not match.
- Keep each `SKILL.md` under 400 lines; move detail to `references/`.
- A new skill must be added to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the
  README table, the table above and `CHANGELOG.md`. The validator enforces the manifest.
