#!/usr/bin/env python3
"""Audit a React Native or Expo project for engine, architecture, dependency and performance issues.

Reads package.json, app.json / app.config.json, android/gradle.properties,
android/app/build.gradle, ios/Podfile, babel.config.js and the JS/TS sources, and reports:
  * Hermes disabled (gradle.properties, Podfile, Expo jsEngine)
  * New Architecture opted out (before 0.82) or a dead opt-out flag (0.82+, New Architecture only)
  * deprecated or heavy packages (moment, full lodash, legacy community packages)
  * ScrollView with mapped children, FlatList without keyExtractor, useNativeDriver: false,
    console.log without a strip plugin, tokens in AsyncStorage, plain HTTP URLs
  * R8/ProGuard off for Android release builds
Line-based heuristics: treat code findings as review prompts.

Exit codes: 0 = ok, 1 = findings at or above --fail-on, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERITIES = ["info", "low", "medium", "high"]
SKIP_DIRS = {"node_modules", "android", "ios", "build", "dist", ".expo", ".git", "coverage", "vendor", "__tests__"}
CODE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}

PACKAGE_ADVICE = {
    "moment": ("low", "moment is large and in maintenance mode", "use date-fns, dayjs or Intl APIs"),
    "lodash": ("low", "full lodash import adds weight", "import per method (lodash/debounce) or use lodash-es"),
    "@react-native-community/async-storage": (
        "medium",
        "deprecated package name",
        "switch to @react-native-async-storage/async-storage",
    ),
    "react-native-camera": ("medium", "deprecated and unmaintained", "use react-native-vision-camera or expo-camera"),
    "react-native-fast-image": (
        "low",
        "unmaintained upstream",
        "consider expo-image or a maintained fork; check New Architecture support",
    ),
    "react-native-push-notification": (
        "low",
        "unmaintained",
        "use @notifee/react-native, expo-notifications or Firebase Messaging",
    ),
    "@react-native-community/cameraroll": (
        "medium",
        "deprecated package name",
        "use @react-native-camera-roll/camera-roll",
    ),
    "react-native-navigation-bar-color": ("info", "check New Architecture support", "see reactnative.directory"),
}

CODE_CHECKS = [
    (
        "perf.native_driver_off",
        "info",
        re.compile(r"useNativeDriver:\s*false"),
        "animation runs on the JS thread",
        "use useNativeDriver: true for transform/opacity, or Reanimated",
    ),
    (
        "security.token_in_asyncstorage",
        "medium",
        re.compile(r"AsyncStorage\.(setItem|multiSet)\(\s*['\"`][^'\"`]*(token|password|secret|jwt|session)", re.I),
        "secret stored in AsyncStorage (unencrypted)",
        "use react-native-keychain or expo-secure-store",
    ),
    (
        "net.plain_http",
        "low",
        re.compile(r"[\"'`]http://(?!localhost|127\.0\.0\.1|10\.0\.2\.2)[^\"'`]+"),
        "plain HTTP URL (blocked by default on Android 9+ and iOS ATS)",
        "use HTTPS",
    ),
    (
        "deps.lodash_full",
        "low",
        re.compile(r"""from\s+['"]lodash['"]|require\(\s*['"]lodash['"]\s*\)"""),
        "imports all of lodash",
        "import the method: import debounce from 'lodash/debounce'",
    ),
]


class Finding:
    __slots__ = ("check", "fix", "message", "severity", "where")

    def __init__(self, check, severity, where, message, fix):
        self.check, self.severity, self.where, self.message, self.fix = check, severity, where, message, fix

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("check", "severity", "where", "message", "fix")}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def version_tuple(spec: str | None) -> tuple[int, int] | None:
    if not spec:
        return None
    m = re.search(r"(\d+)\.(\d+)", spec)
    return (int(m.group(1)), int(m.group(2))) if m else None


def expo_config(root: Path) -> dict:
    for name in ("app.json", "app.config.json"):
        try:
            data = json.loads(_read(root / name) or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data.get("expo", data) if isinstance(data.get("expo", data), dict) else {}
    return {}


def check_engine(root: Path, rn: tuple[int, int] | None) -> list[Finding]:
    out: list[Finding] = []
    props = _read(root / "android" / "gradle.properties")
    podfile = _read(root / "ios" / "Podfile")
    expo = expo_config(root)
    if re.search(r"^\s*hermesEnabled\s*=\s*false", props, re.M):
        out.append(
            Finding(
                "engine.hermes_off",
                "medium",
                "android/gradle.properties",
                "hermesEnabled=false",
                "enable Hermes: faster startup, less memory, smaller bundles",
            )
        )
    if re.search(r":hermes_enabled\s*=>\s*false", podfile):
        out.append(
            Finding(
                "engine.hermes_off",
                "medium",
                "ios/Podfile",
                ":hermes_enabled => false",
                "remove it (Hermes is the default) and run pod install",
            )
        )
    engines = [
        expo.get("jsEngine"),
        (expo.get("ios") or {}).get("jsEngine"),
        (expo.get("android") or {}).get("jsEngine"),
    ]
    if "jsc" in engines:
        out.append(
            Finding(
                "engine.hermes_off",
                "medium",
                "app.json",
                'Expo jsEngine "jsc"',
                "remove jsEngine (Hermes is the default)",
            )
        )
    opt_out = []
    if re.search(r"^\s*newArchEnabled\s*=\s*false", props, re.M):
        opt_out.append("android/gradle.properties newArchEnabled=false")
    if re.search(r"RCT_NEW_ARCH_ENABLED['\"]?\]?\s*=\s*['\"]?0", podfile):
        opt_out.append("ios/Podfile RCT_NEW_ARCH_ENABLED=0")
    if expo.get("newArchEnabled") is False:
        opt_out.append("app.json newArchEnabled: false")
    if opt_out:
        if rn and rn >= (0, 82):
            out.append(
                Finding(
                    "arch.dead_flag",
                    "low",
                    "; ".join(opt_out),
                    "React Native 0.82+ runs only on the New Architecture; the opt-out is ignored",
                    "remove the flag and test the libraries that needed it",
                )
            )
        else:
            out.append(
                Finding(
                    "arch.legacy",
                    "medium",
                    "; ".join(opt_out),
                    "New Architecture disabled; 0.81 / Expo SDK 54 are the last versions allowing this",
                    "migrate libraries, enable it, then upgrade (see references/new-architecture.md)",
                )
            )
    if rn and rn < (0, 76) and not opt_out:
        out.append(
            Finding(
                "rn.old",
                "low",
                "package.json",
                f"react-native {rn[0]}.{rn[1]}",
                "upgrade with the React Native Upgrade Helper; 0.76+ enables the New Architecture by default",
            )
        )
    gradle = _read(root / "android" / "app" / "build.gradle")
    if re.search(r"enableProguardInReleaseBuilds\s*=\s*false", gradle):
        out.append(
            Finding(
                "build.r8_off",
                "info",
                "android/app/build.gradle",
                "enableProguardInReleaseBuilds = false",
                "enable it for release, add keep rules for reflection-based libraries, test the release build",
            )
        )
    return out


def check_packages(pkg: dict) -> list[Finding]:
    out = []
    deps = pkg.get("dependencies") or {}
    for name, (sev, msg, fix) in PACKAGE_ADVICE.items():
        if name in deps:
            out.append(Finding("deps.advice", sev, f"package.json {name}", msg, fix))
    if (
        "react-native" in deps
        and "expo" not in deps
        and not (pkg.get("devDependencies") or {}).get("@react-native/eslint-config")
    ):
        if not any(k.startswith("eslint") for k in pkg.get("devDependencies") or {}):
            out.append(
                Finding(
                    "lint.none",
                    "low",
                    "package.json",
                    "no ESLint setup",
                    "add @react-native/eslint-config (or eslint-config-expo) and run it in CI",
                )
            )
    return out


def iter_code(root: Path):
    for path in sorted(root.rglob("*")):
        if path.suffix not in CODE_SUFFIXES or not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if path.name.endswith((".config.js", ".test.js", ".test.tsx", ".test.ts", ".spec.ts", ".spec.tsx")):
            continue
        yield path, str(rel)


def check_code(root: Path) -> list[Finding]:
    out: list[Finding] = []
    babel = _read(root / "babel.config.js") + _read(root / ".babelrc")
    strip_console = "transform-remove-console" in babel
    console_count, console_files = 0, 0
    for path, rel in iter_code(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith(("//", "*")):
                continue
            for check, sev, rx, msg, fix in CODE_CHECKS:
                if rx.search(line):
                    out.append(Finding(check, sev, f"{rel}:{i}", msg, fix))
            if re.search(r"<ScrollView\b", line):
                window = "\n".join(lines[i - 1 : i + 15])
                if re.search(r"\.map\(\s*\(?", window):
                    out.append(
                        Finding(
                            "perf.scrollview_map",
                            "low",
                            f"{rel}:{i}",
                            "ScrollView renders every mapped child at once",
                            "use FlatList / FlashList for long or dynamic lists",
                        )
                    )
            if re.search(r"<FlatList\b", line):
                window = "\n".join(lines[i - 1 : i + 15])
                if "keyExtractor" not in window and not re.search(r"\bkey\b", window):
                    out.append(
                        Finding(
                            "perf.flatlist_key",
                            "info",
                            f"{rel}:{i}",
                            "FlatList without keyExtractor",
                            "add keyExtractor={item => item.id} so rows are reused correctly",
                        )
                    )
        n = len(re.findall(r"\bconsole\.log\(", text))
        if n:
            console_count += n
            console_files += 1
    if console_count and not strip_console:
        out.append(
            Finding(
                "perf.console_log",
                "info",
                f"{console_files} file(s)",
                f"{console_count} console.log call(s) and no transform-remove-console in Babel",
                "strip console.* in production builds (babel-plugin-transform-remove-console)",
            )
        )
    return out


def audit(root: Path) -> tuple[list[Finding], dict]:
    try:
        pkg = json.loads(_read(root / "package.json") or "null")
    except json.JSONDecodeError as exc:
        raise ValueError(f"package.json is not valid JSON: {exc}") from exc
    if not isinstance(pkg, dict):
        raise ValueError(f"{root}: no package.json")
    deps = {**(pkg.get("devDependencies") or {}), **(pkg.get("dependencies") or {})}
    if "react-native" not in deps and "expo" not in deps:
        raise ValueError(f"{root}: package.json has no react-native or expo dependency")
    rn = version_tuple(deps.get("react-native"))
    info = {"react_native": deps.get("react-native"), "expo": deps.get("expo")}
    return check_engine(root, rn) + check_packages(pkg) + check_code(root), info


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("project", type=Path, nargs="?", default=Path("."), help="project root (default .)")
    p.add_argument("--fail-on", choices=[*SEVERITIES, "none"], default="medium")
    p.add_argument("--min-severity", choices=SEVERITIES, default="info")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        findings, info = audit(args.project)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rank = SEVERITIES.index(args.min_severity)
    shown = sorted(
        (f for f in findings if SEVERITIES.index(f.severity) >= rank), key=lambda f: -SEVERITIES.index(f.severity)
    )
    if args.json:
        print(json.dumps({**info, "findings": [f.as_dict() for f in shown]}, indent=2))
    else:
        print(f"react-native {info['react_native'] or '-'}  expo {info['expo'] or '-'}")
        for f in shown:
            print(f"{f.severity.upper():<6} [{f.check}] {f.where}: {f.message}\n       -> {f.fix}")
        print(f"\n{len(shown)} finding(s)")
    if args.fail_on == "none":
        return 0
    fail = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.severity) >= fail for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
