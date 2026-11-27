# mobile-app-skills

[![CI](https://github.com/saizul/mobile-app-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/mobile-app-skills/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/saizul/mobile-app-skills?sort=semver)](https://github.com/saizul/mobile-app-skills/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/saizul/mobile-app-skills?style=social)](https://github.com/saizul/mobile-app-skills/stargazers)

**Agent Skills that help Claude Code and Codex ship Flutter and React Native apps to Google Play and the App Store - with tested scripts that read your manifest, plist, crash logs and build artifacts instead of guessing.**

Eight skills for the work around every mobile release: listing text that fits the store
limits, Android permissions and exported components, iOS purpose strings and ATS,
versioning, signing and staged rollouts, grouping crash reports, shrinking the APK/AAB/IPA,
and framework-specific best practices. Every skill ships a standard-library-only Python
script that works offline.

- **Deterministic checks.** Scripts parse `AndroidManifest.xml` (xml.etree), `Info.plist`
  (plistlib, XML or binary), Gradle and Xcode project files, fastlane metadata, crash
  exports and APK/AAB/IPA zips. Text or `--json` output, CI-friendly exit codes.
- **Safe by default.** Read-only. Nothing is built, signed or uploaded; no network calls.
  Keystore passwords and API keys are never printed; crash messages are scrubbed of
  emails, ids and URLs.
- **Tested.** 100+ tests with fixture manifests, plists, Flutter/RN/Expo projects, logcat,
  `.crash`, `.ips` and Crashlytics exports, run on Python 3.11-3.13 in CI.
- **Current platforms.** Play target API 36, restricted-permission policies, Android 13/14
  permission changes, iOS 17 calendar keys and privacy manifests, React Native 0.82+
  New-Architecture-only, Hermes, Flutter 3 / Dart 3.

## Skills

| Skill | What it does | Try asking |
| --- | --- | --- |
| [store-listing-writer](skills/store-listing-writer/SKILL.md) | Writes Play and App Store titles, subtitles, keywords, descriptions and release notes; checker validates every locale against field limits (keywords in bytes) and flags promotional words, emoji, other-platform mentions, keyword stuffing; reads fastlane metadata | "Write our App Store keywords and Play short description in English and German" |
| [android-permissions-audit](skills/android-permissions-audit/SKILL.md) | Audits AndroidManifest.xml: dangerous and Play-restricted permissions, legacy storage, unused permissions, exported components without permissions, missing `android:exported`, debuggable, cleartext, backup, network security config | "Why did Play reject our app for READ_SMS, and which permissions can we drop?" |
| [ios-plist-audit](skills/ios-plist-audit/SKILL.md) | Infers capabilities from pubspec/package.json/Swift/entitlements and finds missing or vague `NS*UsageDescription` strings, location key pairs, untranslated or placeholder `InfoPlist.strings`, ATS exceptions, export compliance, privacy manifest | "App Review says our camera purpose string is not specific enough" |
| [release-checklist](skills/release-checklist/SKILL.md) | Preflight for versions and build numbers (pubspec, Gradle, Xcode, Expo), debug-signed releases, committed keystores, target SDK; checklist, signing, staged rollout and phased release, stop rules | "Prepare release 2.4.0 and plan a staged rollout" |
| [crash-log-triage](skills/crash-log-triage/SKILL.md) | Groups Android, Flutter, React Native and iOS crash reports (text, `.ips`, JSON, Crashlytics BigQuery) by root exception and first app frame, ranks them, flags new signatures against a baseline; fix patterns per crash type | "Here is last week's crash export - what should we fix first?" |
| [app-size-reduction](skills/app-size-reduction/SKILL.md) | Size breakdown of APK/AAB/IPA, `bundletool get-size` CSV or Flutter `--analyze-size` JSON; finds universal APKs, unstripped libs, non-Hermes bundles, heavy images, duplicates; size budget for CI | "Our AAB grew 12 MB this release - where did it go?" |
| [flutter-best-practices](skills/flutter-best-practices/SKILL.md) | State management choice, lint baseline, structure, performance and security; audit finds unpinned deps, mixed state libs, missing lints, futures created in build, non-lazy lists, tokens in SharedPreferences | "Review this Flutter app for production and set up strict lints" |
| [react-native-best-practices](skills/react-native-best-practices/SKILL.md) | Hermes, New Architecture migration, upgrades, list/animation performance, secure storage; audit finds Hermes off, architecture opt-outs, deprecated packages, ScrollView+map, tokens in AsyncStorage | "Can we upgrade to the latest React Native? We still have newArchEnabled=false" |

## Install

### Claude Code: plugin marketplace (recommended)

```text
/plugin marketplace add saizul/mobile-app-skills
/plugin install mobile-app-skills@mobile-app-skills
```

Or from your shell:

```bash
claude plugin marketplace add saizul/mobile-app-skills
claude plugin install mobile-app-skills@mobile-app-skills
```

Plugin skills are namespaced, e.g. `/mobile-app-skills:ios-plist-audit`. Claude also
picks them up automatically when your request matches a skill's description. Update later
with `/plugin marketplace update mobile-app-skills`.

### Claude Code: copy the skills

```bash
git clone https://github.com/saizul/mobile-app-skills.git
# all projects (personal skills)
mkdir -p ~/.claude/skills && cp -r mobile-app-skills/skills/* ~/.claude/skills/
# or just one project
mkdir -p .claude/skills && cp -r mobile-app-skills/skills/release-checklist .claude/skills/
```

Each release also has one zip per skill and an all-skills zip under
[Releases](https://github.com/saizul/mobile-app-skills/releases).

### Codex CLI

Codex reads skills from `~/.agents/skills` (all repositories) and `.agents/skills` in a
repository (from the current directory up to the repository root):

```bash
git clone https://github.com/saizul/mobile-app-skills.git
mkdir -p ~/.agents/skills && cp -r mobile-app-skills/skills/* ~/.agents/skills/
# or per repository
mkdir -p .agents/skills && cp -r mobile-app-skills/skills/crash-log-triage .agents/skills/
```

Codex also ships a `$skill-installer` skill that can install skills from a GitHub
repository; ask it to install from `saizul/mobile-app-skills`. Skill locations and the
installer are described in the [Codex skills documentation](https://developers.openai.com/codex/skills);
check it if your Codex version behaves differently. [AGENTS.md](AGENTS.md) explains how
Codex and other agents should use these skills.

### Any other agent

The skills follow the open [Agent Skills format](https://agentskills.io/specification):
a folder with `SKILL.md` (YAML frontmatter + instructions), `scripts/` and `references/`.
Point your agent at the folder, or run the scripts yourself; every script has `--help`.

## Usage examples

```text
> We're submitting 2.4.0 tomorrow. Anything that will get us rejected?
  (Runs release_preflight.py, manifest_audit.py on the merged manifest and
   plist_audit.py: release signed with the debug key, targetSdk 34, image_picker without
   NSPhotoLibraryUsageDescription; proposes diffs and a 1% > 10% > 50% > 100% rollout.)

> Here are 400 crash reports from Play Console and Crashlytics.
  (triage_crashes.py groups them into 9 signatures; the top one is an
   IllegalStateException in BudgetRepository.load on first launch, only in 2.4.0.)

> Our App Store keywords keep getting cut off in Japanese.
  (check_listing.py shows 119/100 bytes: Japanese characters take 3 bytes each; rewrites
   the field to 98 bytes and drops terms already in the subtitle.)
```

Run the scripts directly too:

```bash
python3 skills/store-listing-writer/scripts/check_listing.py fastlane/metadata
python3 skills/android-permissions-audit/scripts/manifest_audit.py android/app/src/main/AndroidManifest.xml --gradle android/app/build.gradle --source .
python3 skills/ios-plist-audit/scripts/plist_audit.py ios/Runner/Info.plist --project .
python3 skills/release-checklist/scripts/release_preflight.py . --previous-android 41 --previous-ios 41
python3 skills/crash-log-triage/scripts/triage_crashes.py crashes/ --app com.example.app --json
python3 skills/app-size-reduction/scripts/size_report.py build/app/outputs/bundle/release/app-release.aab --budget-mb 30
python3 skills/flutter-best-practices/scripts/flutter_audit.py .
python3 skills/react-native-best-practices/scripts/rn_audit.py .
```

## How skills work

At startup the agent loads only each skill's `name` and `description` (about 100 tokens
each). When your request matches a description, it reads that skill's `SKILL.md`: the
workflow, decision points and safety rules. Longer material lives in `references/` and is
read only when a step needs it. Scripts run as normal commands, so their output is exact
and repeatable.

```
skills/<skill-name>/
  SKILL.md          frontmatter (name, description) + workflow
  scripts/          standalone Python 3 helpers (stdlib only, --help, --json)
  references/       policies, checklists, patterns, snippets
```

## FAQ

**Do the scripts need Flutter, Xcode or the Android SDK?**
No. They only need Python 3.8+. Some workflows ask you to produce inputs with your own
tools (a merged manifest, `bundletool get-size`, `flutter build --analyze-size`).

**Do they upload anything or call store APIs?**
No. No network calls, no telemetry. Publishing to Play Console or App Store Connect stays
with you or your CI.

**Expo managed projects?**
Yes for `release-checklist` (app.json versions), `react-native-best-practices`,
`crash-log-triage`, `app-size-reduction` and `store-listing-writer`. For the manifest and
plist audits, run `npx expo prebuild` in a scratch copy, or audit the built APK/IPA.

**Native Kotlin/Swift apps?**
The manifest, plist, release, crash, size and listing skills work for native apps too;
only the two best-practices skills are framework-specific.

**Store policies change. How current is this?**
Written against the Google Play and App Store rules in force in late 2026 (Play target
API 36). Thresholds such as `--min-target-sdk` are options; the references link to the
official pages to re-check.

## Roadmap

Ideas for new skills (great first contributions; see [CONTRIBUTING.md](CONTRIBUTING.md)):

- `play-data-safety-helper` - draft Data safety answers from manifest, SDKs and code
- `app-privacy-labels` - App Store privacy nutrition labels and `PrivacyInfo.xcprivacy` generator
- `deep-links-audit` - Android App Links (`assetlinks.json`) and iOS Universal Links (`apple-app-site-association`) checks
- `in-app-purchase-setup` - StoreKit 2 / Play Billing products, testing and server verification
- `push-notifications-setup` - FCM/APNs setup, channels, permission prompts and delivery debugging
- `mobile-ci-pipelines` - GitHub Actions / Codemagic / EAS Build recipes with signing secrets
- `accessibility-audit` - semantics labels, touch targets, dynamic type for Flutter and RN
- `app-review-responder` - draft replies to store reviews and App Review rejections

## Contributing

Contributions are welcome: new checks, new skills, fixtures from real projects
(redacted), fixes and better docs. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the skill
template, the quality bar and how to run the validator and tests:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/validate_skills.py && ruff check . && ruff format --check . && pytest
```

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and report security issues
privately as described in [SECURITY.md](SECURITY.md).

Google Play and Android are trademarks of Google LLC; App Store and iOS are trademarks of
Apple Inc.; Flutter is a trademark of Google LLC; React Native is a trademark of Meta
Platforms, Inc. This project is independent and not affiliated with any of them.

## License

[MIT](LICENSE) (c) Saizul Amin
