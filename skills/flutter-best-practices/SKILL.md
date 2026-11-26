---
name: flutter-best-practices
description: Review and improve Flutter apps - choose state management (setState, Provider, Riverpod, Bloc/Cubit, signals) for the app's size and team, set up strict lints (flutter_lints or very_good_analysis, strict-casts/inference/raw-types), structure features and layers, and fix performance (const widgets, builder lists, futures created in build, MediaQuery.of rebuilds, shrinkWrap, image caching, jank, isolates) and security basics (secure storage, HTTPS). A script audits pubspec.yaml, analysis_options.yaml and lib/ for unpinned or git dependencies without ref, dependency_overrides, mixed state libraries, missing lints, FutureBuilder/StreamBuilder futures created inline, non-lazy ListViews, print(), plain HTTP and tokens in SharedPreferences. Use when the user asks to review a Flutter codebase, pick a state management approach, set up lints, fix jank or rebuild storms, or prepare a Flutter app for production.
license: MIT
compatibility: Python 3.8+ standard library only. The script is a fast static pre-check; `flutter analyze` and DevTools remain the source of truth.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# Flutter best practices

Opinionated, current guidance for production Flutter apps, backed by a quick static
audit. Recommend; do not rewrite the app's architecture without agreement.

Paths below are relative to this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`).

## When to use

- "Review my Flutter app", "is this production ready?", "set up lints"
- "Provider, Riverpod or Bloc?", "how should I structure features?"
- Jank, slow lists, too many rebuilds, a FutureBuilder that keeps reloading
- Onboarding a codebase: quick health check before deeper work

## When not to use

- React Native: `react-native-best-practices`
- App size: `app-size-reduction`; crashes from production: `crash-log-triage`
- Store permission strings and manifests: `ios-plist-audit`, `android-permissions-audit`

## Workflow

1. **Run the official tools first** (the user's toolchain):
   ```bash
   flutter --version
   flutter analyze
   dart format --output=none --set-exit-if-changed lib test
   flutter test
   flutter pub outdated
   ```
2. **Run the audit (read-only).**
   ```bash
   python3 scripts/flutter_audit.py .
   python3 scripts/flutter_audit.py . --json --min-severity low
   ```
   Exit 1 = findings at or above `--fail-on` (default `medium`). Findings are line-based
   heuristics: open each file and confirm before reporting it as a bug.
3. **Lints.** If `lints.*` findings appear, propose the baseline from
   [references/lints.md](references/lints.md) (include + strict modes + a few extra rules),
   run `dart fix --dry-run`, then `dart fix --apply` only after approval.
4. **State management.** If `state.mixed` appears or the user asks, use the decision
   table in [references/state-management.md](references/state-management.md). Recommend
   one approach for app state; do not churn a working codebase to a new library without
   a concrete problem it solves.
5. **Performance.** For each `build.*` / `perf.*` finding, and for reported jank, follow
   [references/performance.md](references/performance.md): profile in `--profile` mode on
   a real device with DevTools (Performance, rebuild counts) before and after the change.
6. **Security basics.** Tokens in `flutter_secure_storage`, HTTPS only, no secrets in
   the app binary (API keys that matter belong on a server), certificate pinning only
   with a rotation plan.
7. **Report and propose** a prioritized list (correctness > performance > style) with
   small diffs; apply after approval; re-run `flutter analyze`, tests and the audit.

## Output

```
Flutter review (Flutter 3.x, Dart 3.x): 2 medium, 4 low, 3 info

MED  lib/screens/home.dart:12  FutureBuilder(future: loadBudgets()) refetches on every rebuild
     -> late final Future<List<Budget>> _budgets = repo.load(); in State
MED  no lint package -> add flutter_lints + strict analyzer modes (diff below)
LOW  provider + flutter_bloc + get mixed -> standardise on Bloc (already 80% of screens)
LOW  ListView(children: map) for 500 expenses -> ListView.builder

Verified: flutter analyze 0 issues after changes, tests pass, DevTools rebuild count
for Home drops from 14 to 2 per scroll.
```
