# Staged rollout and phased release

## Google Play

- Tracks: internal testing (up to 100 testers, available within minutes) > closed testing
  > open testing > production. New personal developer accounts must run a closed test
  with enough testers for a period before production access; check Play Console for the
  current rule on your account.
- Production staged rollout: choose a percentage when releasing; increase it later from
  the release page. Suggested plan for an established app:

  | Step | Rollout | Wait at least |
  | --- | --- | --- |
  | 1 | 1-2% | 24 h (enough sessions for crash rates) |
  | 2 | 10% | 24 h |
  | 3 | 50% | 24-48 h |
  | 4 | 100% | - |

- **Halt rollout** stops new users from getting the release; users who already updated
  keep it. To recover: fix, upload a higher versionCode, roll out again. Resuming a
  halted release is possible if the issue was not in the app.
- Android vitals: watch user-perceived crash rate and ANR rate against the previous
  release; Play uses bad-behaviour thresholds for visibility.

## App Store

- TestFlight: internal testers (team members, no review) and external groups (Beta App
  Review for the first build of a version).
- Phased release for automatic updates spreads over 7 days (roughly 1%, 2%, 5%, 10%, 20%,
  50%, 100%). Users can still update manually from the store page at any time.
- You can pause a phased release (up to 30 days in total) or release to everyone at once.
- No rollback: to fix, submit a new build (expedited review can be requested for
  critical bugs).

## Stop rules (write them before starting)

Stop or pause when any of these is true at a rollout step:

- Crash-free users (or sessions) lower than the previous version by more than an agreed
  margin (e.g. 0.3 percentage points)
- A crash group that did not exist in the previous version reaches an agreed share
  (`triage_crashes.py --baseline previous.json` lists new signatures)
- ANR rate above the Play bad-behaviour threshold or clearly above the previous version
- Login, payment or sync error rates spike in backend monitoring
- Several 1-star reviews describing the same regression

## Server-side safety nets

- Feature flags / remote config to switch off a new feature without a release
- Minimum supported version check at startup to force-update in emergencies
- Backward-compatible APIs while old versions are still in use
