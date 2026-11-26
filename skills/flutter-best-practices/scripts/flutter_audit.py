#!/usr/bin/env python3
"""Audit a Flutter project's lint setup, dependencies and common performance mistakes.

Checks pubspec.yaml (unpinned `any` versions, git dependencies without a ref,
dependency_overrides, several state management libraries mixed, old Dart SDK
constraints), analysis_options.yaml (missing, no lint package, strict modes, ignored
safety lints) and Dart code under lib/ (futures and streams created inside build,
MediaQuery.of(...).size, non-lazy ListView with mapped children, shrinkWrap, print,
plain HTTP URLs, tokens in SharedPreferences). Line-based heuristics: treat findings as
review prompts, not proof.

Exit codes: 0 = ok, 1 = findings at or above --fail-on, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]
STATE_FAMILIES = {
    "provider": "provider",
    "flutter_riverpod": "riverpod",
    "riverpod": "riverpod",
    "hooks_riverpod": "riverpod",
    "flutter_bloc": "bloc",
    "bloc": "bloc",
    "hydrated_bloc": "bloc",
    "get": "getx",
    "mobx": "mobx",
    "flutter_mobx": "mobx",
    "redux": "redux",
    "flutter_redux": "redux",
    "signals": "signals",
    "signals_flutter": "signals",
}
LINT_PACKAGES = ("flutter_lints", "lints", "very_good_analysis", "lint", "pedantic_mono", "solid_lints")
SAFETY_LINTS = ("use_build_context_synchronously", "unawaited_futures", "avoid_print", "cancel_subscriptions")

CODE_CHECKS = [
    (
        "build.future_in_build",
        "medium",
        re.compile(r"\bfuture:\s*[\w.]+\s*\("),
        "FutureBuilder future created inline: it restarts on every rebuild",
        "create the Future once (initState, a provider, or a late final field) and pass the variable",
    ),
    (
        "build.stream_in_build",
        "medium",
        re.compile(r"\bstream:\s*[\w.]+\s*\("),
        "StreamBuilder stream created inline: it resubscribes on every rebuild",
        "create the stream once and pass the variable",
    ),
    (
        "perf.mediaquery_of",
        "info",
        re.compile(r"MediaQuery\.of\(\s*context\s*\)\s*\.\s*(size|padding|viewInsets|orientation|textScaler)"),
        "MediaQuery.of(context).x rebuilds on any MediaQuery change",
        "use MediaQuery.sizeOf(context) / paddingOf / viewInsetsOf (Flutter 3.10+)",
    ),
    (
        "perf.shrinkwrap",
        "info",
        re.compile(r"shrinkWrap:\s*true"),
        "shrinkWrap lays out every child",
        "prefer slivers (CustomScrollView) or a bounded height for long lists",
    ),
    (
        "code.print",
        "low",
        re.compile(r"(?<![\w.])print\("),
        "print() in app code",
        "use debugPrint or a logger (package:logging); avoid logging personal data",
    ),
    (
        "net.plain_http",
        "low",
        re.compile(r"[\"']http://(?!localhost|127\.0\.0\.1|10\.0\.2\.2)[^\"']+"),
        "plain HTTP URL (blocked by default on Android 9+ and iOS ATS)",
        "use HTTPS",
    ),
    (
        "security.token_in_prefs",
        "medium",
        re.compile(r"\.set(String|StringList)\(\s*['\"][^'\"]*(token|password|secret|jwt|session)", re.I),
        "secret stored in SharedPreferences (plain text on disk, included in backups)",
        "use flutter_secure_storage (Keychain / Android Keystore)",
    ),
]


class Finding:
    __slots__ = ("check", "fix", "message", "severity", "where")

    def __init__(self, check, severity, where, message, fix):
        self.check, self.severity, self.where, self.message, self.fix = check, severity, where, message, fix

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("check", "severity", "where", "message", "fix")}


def parse_pubspec(text: str) -> dict:
    """Small pubspec reader: top-level scalars and dependency sections (name -> raw spec)."""
    data: dict = {"sections": {}}
    section, current = None, None
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            key, _, val = line.partition(":")
            section = key.strip()
            data[section] = val.strip().strip("'\"")
            current = None
            if section in ("dependencies", "dev_dependencies", "dependency_overrides", "environment"):
                data["sections"].setdefault(section, {})
            continue
        if section not in data["sections"]:
            continue
        if indent == 2:
            key, _, val = line.strip().partition(":")
            current = key.strip()
            data["sections"][section][current] = val.strip().strip("'\"")
        elif current and indent > 2:
            prev = data["sections"][section][current]
            data["sections"][section][current] = (prev + " " if prev else "") + line.strip()
    return data


def check_pubspec(root: Path) -> list[Finding]:
    out: list[Finding] = []
    path = root / "pubspec.yaml"
    pub = parse_pubspec(path.read_text(encoding="utf-8"))
    sections = pub["sections"]
    deps = sections.get("dependencies", {})
    dev = sections.get("dev_dependencies", {})
    for sec_name in ("dependencies", "dev_dependencies"):
        for name, spec in sections.get(sec_name, {}).items():
            if spec in ("any", '"any"') or spec.strip() == "any":
                out.append(
                    Finding(
                        "deps.any",
                        "medium",
                        f"pubspec.yaml {name}",
                        f"{name}: any (unpinned)",
                        f"use a caret range, e.g. {name}: ^x.y.z",
                    )
                )
            if "git:" in spec and "ref:" not in spec:
                out.append(
                    Finding(
                        "deps.git_no_ref",
                        "low",
                        f"pubspec.yaml {name}",
                        f"git dependency {name} without ref",
                        "pin a tag or commit with ref:",
                    )
                )
    if sections.get("dependency_overrides"):
        names = ", ".join(sections["dependency_overrides"])
        out.append(
            Finding(
                "deps.overrides",
                "low",
                "pubspec.yaml",
                f"dependency_overrides: {names}",
                "remove overrides before release or document why each is needed",
            )
        )
    families = sorted({STATE_FAMILIES[d] for d in deps if d in STATE_FAMILIES})
    if len(families) > 1:
        out.append(
            Finding(
                "state.mixed",
                "low",
                "pubspec.yaml",
                f"several state management approaches: {', '.join(families)}",
                "pick one for app state; see references/state-management.md",
            )
        )
    sdk = sections.get("environment", {}).get("sdk", "")
    m = re.search(r">=?\s*(\d+)\.(\d+)", sdk) or re.search(r"\^(\d+)\.(\d+)", sdk)
    if m and int(m.group(1)) < 3:
        out.append(
            Finding(
                "sdk.old",
                "low",
                "pubspec.yaml environment",
                f"Dart SDK constraint {sdk}",
                "move to Dart 3 (sdk: ^3.x) for sound null safety, records and patterns",
            )
        )
    if not any(p in dev for p in LINT_PACKAGES):
        out.append(
            Finding(
                "lints.package_missing",
                "medium",
                "pubspec.yaml dev_dependencies",
                "no lint package",
                "add flutter_lints (or very_good_analysis) to dev_dependencies",
            )
        )
    return out


def check_analysis_options(root: Path) -> list[Finding]:
    path = root / "analysis_options.yaml"
    if not path.is_file():
        return [
            Finding(
                "lints.no_options",
                "medium",
                "analysis_options.yaml",
                "file missing: no lints run",
                "add it with: include: package:flutter_lints/flutter.yaml",
            )
        ]
    text = path.read_text(encoding="utf-8")
    out: list[Finding] = []
    if not re.search(r"^include:\s*package:(" + "|".join(LINT_PACKAGES) + r")/", text, re.M):
        out.append(
            Finding(
                "lints.no_include",
                "medium",
                "analysis_options.yaml",
                "does not include a lint set",
                "include: package:flutter_lints/flutter.yaml",
            )
        )
    strict = [
        k for k in ("strict-casts", "strict-inference", "strict-raw-types") if not re.search(rf"{k}:\s*true", text)
    ]
    if strict:
        out.append(
            Finding(
                "lints.strict_off",
                "info",
                "analysis_options.yaml",
                f"not enabled: {', '.join(strict)}",
                "under analyzer: language: set them to true",
            )
        )
    for lint in SAFETY_LINTS:
        if re.search(rf"^\s+{lint}:\s*(ignore|false)\b", text, re.M):
            out.append(
                Finding(
                    "lints.safety_disabled",
                    "low",
                    "analysis_options.yaml",
                    f"{lint} is disabled",
                    "fix the code instead of silencing the lint",
                )
            )
    return out


def check_code(root: Path) -> list[Finding]:
    out: list[Finding] = []
    lib = root / "lib"
    if not lib.is_dir():
        return out
    for path in sorted(lib.rglob("*.dart")):
        if path.name.endswith((".g.dart", ".freezed.dart", ".gr.dart", ".mocks.dart")):
            continue
        rel = str(path.relative_to(root))
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            code = line.split("//", 1)[0] if "://" not in line else line
            if code.lstrip().startswith(("//", "///", "*")):
                continue
            for check, sev, rx, msg, fix in CODE_CHECKS:
                if rx.search(code):
                    out.append(Finding(check, sev, f"{rel}:{i}", msg, fix))
            if re.search(r"\bListView\(", code):
                window = "\n".join(lines[i - 1 : i + 8])
                if "children:" in window and (".map(" in window or "for (" in window):
                    out.append(
                        Finding(
                            "perf.listview_children",
                            "low",
                            f"{rel}:{i}",
                            "ListView(children: ...) builds every item up front",
                            "use ListView.builder / ListView.separated for long or dynamic lists",
                        )
                    )
    return out


def audit(root: Path) -> list[Finding]:
    if not (root / "pubspec.yaml").is_file():
        raise ValueError(f"{root}: no pubspec.yaml (not a Flutter/Dart project root)")
    return check_pubspec(root) + check_analysis_options(root) + check_code(root)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("project", type=Path, nargs="?", default=Path("."), help="Flutter project root (default .)")
    p.add_argument("--fail-on", choices=[*SEVERITIES, "none"], default="medium")
    p.add_argument("--min-severity", choices=SEVERITIES, default="info")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        findings = audit(args.project)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rank = SEVERITIES.index(args.min_severity)
    shown = sorted(
        (f for f in findings if SEVERITIES.index(f.severity) >= rank), key=lambda f: -SEVERITIES.index(f.severity)
    )
    if args.json:
        print(json.dumps({"findings": [f.as_dict() for f in shown]}, indent=2))
    else:
        for f in shown:
            print(f"{f.severity.upper():<6} [{f.check}] {f.where}: {f.message}\n       -> {f.fix}")
        print(f"\n{len(shown)} finding(s)")
    if args.fail_on == "none":
        return 0
    fail = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= fail for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
