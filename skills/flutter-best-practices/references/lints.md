# Lint baseline

`pubspec.yaml`:

```yaml
dev_dependencies:
  flutter_lints: ^5.0.0   # or very_good_analysis for a stricter set
```

`analysis_options.yaml`:

```yaml
include: package:flutter_lints/flutter.yaml

analyzer:
  language:
    strict-casts: true
    strict-inference: true
    strict-raw-types: true
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"

linter:
  rules:
    - always_declare_return_types
    - avoid_dynamic_calls
    - cancel_subscriptions
    - close_sinks
    - prefer_final_locals
    - unawaited_futures
    - use_build_context_synchronously
    - avoid_print
```

Use the latest `flutter_lints` major that your Flutter SDK supports (`flutter pub outdated`).

Rollout on an existing codebase:

1. Add the include and strict modes, run `flutter analyze | tail -1` to count issues.
2. `dart fix --dry-run` shows mechanical fixes; `dart fix --apply` after approval.
3. Fix the rest by directory, or temporarily downgrade a noisy rule to `info` under
   `analyzer: errors:` with a ticket to clean up. Do not `ignore` safety lints
   (`use_build_context_synchronously`, `unawaited_futures`) permanently.
4. Add `flutter analyze --fatal-infos` (or `--fatal-warnings`) to CI.

Formatting: `dart format .` in CI with `--set-exit-if-changed`. Since Dart 3.7 the
formatter uses the "tall" style and respects `formatter: page_width:` in
`analysis_options.yaml`.
