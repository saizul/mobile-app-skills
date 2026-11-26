# Contributing to mobile-app-skills

Thank you for helping! New checks, new skills, fixes, fixtures from real projects
(redacted) and clearer docs are all welcome.

- [Ways to contribute](#ways-to-contribute)
- [Good first issues](#good-first-issues)
- [Development setup](#development-setup)
- [Repository layout](#repository-layout)
- [Write a new skill](#write-a-new-skill)
- [Quality bar](#quality-bar)
- [Pull request process](#pull-request-process)

## Ways to contribute

| Size | Idea |
| --- | --- |
| 10 minutes | Fix a typo, clarify a workflow step, add a purpose-string example |
| 30 minutes | Add a fixture (manifest, plist, stack trace) that shows a false positive or a missed finding |
| 1-2 hours | Add a check to an existing script (see below) |
| Half a day | Write a new skill from the template |

Comment on an issue before you start so nobody else picks the same one.

## Good first issues

Each of these is self-contained and touches one script and its test file.

1. **store-listing-writer: App Store promotional text and subtitle duplicates.** Report
   `info` when the subtitle repeats words from the name (wasted indexed characters).
2. **store-listing-writer: `--locales` filter.** Check only the given locales
   (`--locales en-US,de-DE`).
3. **android-permissions-audit: `<uses-feature>` without `required="false"`.** Report
   `low` for camera/telephony/GPS features that silently hide the app from devices without
   them.
4. **android-permissions-audit: `android:taskAffinity` and `launchMode` hijacking.**
   Flag exported activities with `taskAffinity` set to another package (StrandHogg-style).
5. **ios-plist-audit: `NSBonjourServices` without `NSLocalNetworkUsageDescription`.**
   Report `high` (local network prompt needs a purpose string).
6. **ios-plist-audit: Expo `app.json` support.** Read `expo.ios.infoPlist` so managed
   projects can be audited without prebuild.
7. **release-checklist: Xcode build number mismatch.** Flag differing
   `CURRENT_PROJECT_VERSION` values between Debug and Release configurations.
8. **crash-log-triage: ANR traces.** Parse Android ANR `traces.txt` ("main" thread
   stack) and group by the top app frame of the main thread.
9. **crash-log-triage: Markdown output.** `--markdown` prints the ranked table ready for an
   issue or a release report.
10. **app-size-reduction: compare two builds.** `--compare old.aab` prints the per-category
    delta, for pull request comments.
11. **flutter-best-practices: `context` after `await`.** Detect `Navigator.of(context)` /
    `ScaffoldMessenger.of(context)` after an `await` in the same method without a
    `mounted` check.
12. **react-native-best-practices: inline functions in `renderItem`.** Report `info` for
    `renderItem={({item}) => <Row onPress={() => ...} />}` in large lists.
13. **New skill: `deep-links-audit`** (see the roadmap in the README).

## Development setup

```bash
git clone https://github.com/saizul/mobile-app-skills.git
cd mobile-app-skills
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

python tools/validate_skills.py   # SKILL.md frontmatter, sections, links, marketplace listing
ruff check . && ruff format --check .
pytest
```

To try your changes in Claude Code, either copy a skill to `~/.claude/skills/` or add your
checkout as a local marketplace:

```bash
claude plugin marketplace add ./mobile-app-skills
claude plugin install mobile-app-skills@mobile-app-skills
```

For Codex, copy the skill folder to `~/.agents/skills/`.

## Repository layout

```
.claude-plugin/
  marketplace.json      marketplace + plugin entry listing every skill
  plugin.json           plugin manifest (name, version, author)
skills/<name>/
  SKILL.md              frontmatter + workflow (the part agents read)
  scripts/*.py          standalone helpers, Python 3.8+ stdlib only
  references/*.md       detail loaded on demand
templates/skill/        copy this to start a new skill
tests/
  test_<skill>.py       one test module per skill
  fixtures/<area>/      manifests, plists, projects, crash logs, size inputs
tools/validate_skills.py
```

## Write a new skill

1. Open a "New skill proposal" issue first so we can agree on scope.
2. Copy the template:
   ```bash
   cp -r templates/skill skills/my-skill
   mv skills/my-skill/scripts/your_script.py skills/my-skill/scripts/my_check.py
   ```
3. Edit `SKILL.md`:
   - `name` equals the folder name: lowercase letters, digits, single hyphens, max 64 chars.
   - `description` (max 1024 chars) says **what** it does with concrete keywords and **when**
     to use it, starting the second part with "Use when ...". This text decides whether
     the agent picks the skill, so list the phrases and error messages users actually type
     (Play Console and App Review wording is gold).
   - Required sections: `## When to use`, `## When not to use`, `## Workflow`, `## Output`.
   - Workflow steps are imperative and numbered, with exact commands, decision points and
     the point where the agent must ask before changing anything.
   - Keep it under 400 lines; move tables, snippets and long configs to `references/`.
4. Write the script: `argparse` with a useful `--help`, `--json` output, exit codes
   0 (ok) / 1 (findings) / 2 (error), read-only, no network, never print secret values.
5. Add `tests/test_my_skill.py` with fixtures in `tests/fixtures/`. Cover a bad input, a
   good input with no findings, edge cases and the CLI exit codes.
6. Add the skill to `.claude-plugin/marketplace.json` (`plugins[0].skills`), the README
   skills table, the table in `AGENTS.md`, the bug report dropdown and `CHANGELOG.md`
   under "Unreleased".
7. Run the validator, ruff and pytest.

## Quality bar

- **Grounded in real projects.** Manifest attributes, plist keys, Gradle and Xcode syntax
  must match what Flutter, React Native and native templates generate. When you add a
  check, add a fixture made from a real (redacted) file that shows it.
- **Policy claims are sourced.** If a check encodes a Google Play or App Review rule, link
  the official page in the skill's references.
- **Safety first.** A skill must never tell the agent to sign, upload, publish, change a
  rollout or handle signing material without showing the step and getting confirmation.
- **Deterministic where it matters.** If a step is "parse this file and find X", write a
  script and test it instead of relying on the model reading a 2,000-line manifest.
- **Low false positives.** If a check is often wrong, make it `info` or drop it, and
  document known false positives in the skill's references.
- **Fake secrets only.** Never commit real keystores, certificates or keys, even expired
  ones. Build key-like test values from pieces in test code.

## Pull request process

1. Fork, create a branch, make focused commits.
2. Make sure CI passes locally (validator, ruff, pytest).
3. Fill in the pull request template.
4. A maintainer reviews within a few days. Small, focused pull requests are merged fastest.

By contributing you agree that your contributions are licensed under the MIT License.
