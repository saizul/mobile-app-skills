#!/usr/bin/env python3
"""Group crash reports by signature (exception type + top app frame) and rank them.

Understands, in text files: Android/Java/Kotlin stack traces (logcat FATAL EXCEPTION,
"Caused by:" chains), Flutter/Dart traces (#0 frames, "Unhandled Exception:"),
React Native JavaScript errors (Hermes/JSC frames), Apple crash reports (.crash text with
"Thread N Crashed:" or "Last Exception Backtrace:") and .ips JSON reports. In JSON/JSONL
exports: a list of objects with a stack trace string ("stacktrace", "stack", "exception",
...), optional "count", "app_version", "os_version", or Crashlytics BigQuery rows with
"exceptions"[].frames. Messages are scrubbed of numbers, ids, emails and URLs.

Exit codes: 0 = ok, 1 = new signatures compared with --baseline, 2 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

JAVA_FRAME = re.compile(r"^\s*at\s+([\w$.<>/-]+)\.([\w$<>-]+)\(([^)]*)\)\s*$")
JAVA_EXC = re.compile(
    r"^\s*(?P<cause>Caused by:\s*)?(?:Fatal Exception:\s*|Exception in thread \"[^\"]*\"\s*)?"
    r"(?P<type>(?:[a-zA-Z_][\w$]*\.)+[A-Z][\w$]*(?:Exception|Error|Throwable|Failure)|[A-Z]\w+(?:Exception|Error))"
    r"(?::\s*(?P<msg>.*))?$"
)
DART_FRAME = re.compile(r"^#(\d+)\s+(.+?)\s+\(((?:package|dart|file|org-dartlang-sdk):[^)]*)\)\s*$")
DART_EXC = re.compile(r"(?:Unhandled Exception|Exception caught by [^:]+?|Error):\s*(?P<msg>.+)$")
JS_FRAME_V8 = re.compile(r"^\s*at\s+(?:(?P<fn>.+?)\s+\()?(?P<loc>[^()\s]+?):\d+(?::\d+)?\)?\s*$")
JS_FRAME_AT = re.compile(r"^\s*(?P<fn>[^@\s]*)@(?P<loc>.+?)(?::\d+){1,2}\s*$")
JS_EXC = re.compile(
    r"^\s*(?:Error:\s*)?(?P<type>TypeError|ReferenceError|RangeError|SyntaxError|EvalError|URIError|"
    r"Invariant Violation|[A-Z]\w*Error)(?::\s*(?P<msg>.*))?$"
)
IOS_FRAME = re.compile(r"^(\d+)\s+(\S+)\s+0x[0-9a-fA-F]+\s+(.+?)\s*$")
IOS_EXC_TYPE = re.compile(r"^Exception Type:\s*(.+)$")
IOS_NSEXC = re.compile(r"uncaught exception '([^']+)', reason: '(.*)'")
IOS_PROCESS = re.compile(r"^Process:\s*(\S+)")
LOGCAT_PREFIX = re.compile(
    r"^(?:.*?\b[VDIWEF] (?:AndroidRuntime|flutter|ReactNativeJS|ReactNative)\s*:"
    r"|[VDIWEF]/(?:AndroidRuntime|flutter|ReactNativeJS|ReactNative)\s*\(\s*\d+\)\s*:)\s?"
)
SEPARATOR = re.compile(r"^\s*(-{3,}|={3,}|\*{3,})\s*$")

FRAMEWORK_PREFIXES = (
    "java.",
    "javax.",
    "android.",
    "androidx.",
    "kotlin.",
    "kotlinx.",
    "com.android.",
    "dalvik.",
    "libcore.",
    "sun.",
    "jdk.",
    "com.google.android.",
    "com.google.firebase.",
    "com.google.common.",
    "io.flutter.",
    "com.facebook.react.",
    "com.facebook.hermes.",
    "com.facebook.jni.",
    "com.facebook.soloader.",
    "okhttp3.",
    "okio.",
    "retrofit2.",
    "io.reactivex.",
    "dart:",
    "package:flutter/",
    "package:flutter_test/",
    "org-dartlang-sdk:",
    "node_modules/",
    "native",
    "<anonymous>",
    "[native code]",
)
IOS_SYSTEM_IMAGES = {
    "libsystem_kernel.dylib",
    "libsystem_pthread.dylib",
    "libsystem_c.dylib",
    "libsystem_platform.dylib",
    "libdispatch.dylib",
    "libobjc.A.dylib",
    "libswiftCore.dylib",
    "libc++abi.dylib",
    "libc++.1.dylib",
    "CoreFoundation",
    "Foundation",
    "UIKitCore",
    "UIKit",
    "GraphicsServices",
    "QuartzCore",
    "CFNetwork",
    "dyld",
    "Flutter",
    "hermes",
    "React",
    "SwiftUI",
    "libswift_Concurrency.dylib",
}

STACK_KEYS = ("stacktrace", "stack_trace", "stackTrace", "stack", "trace", "exception", "crash", "error", "log")
COUNT_KEYS = ("count", "occurrences", "events", "event_count", "crashes")
VERSION_KEYS = ("app_version", "appVersion", "version", "version_name", "build")


class Crash:
    __slots__ = ("app_frame", "count", "frames", "kind", "message", "source", "type", "version")

    def __init__(self, kind, source):
        self.kind, self.source = kind, source
        self.type, self.message, self.frames = "", "", []
        self.app_frame, self.count, self.version = None, 1, None


def scrub(msg: str) -> str:
    msg = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<email>", msg)
    msg = re.sub(r"https?://\S+", "<url>", msg)
    msg = re.sub(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "<uuid>", msg)
    msg = re.sub(r"0x[0-9a-fA-F]+", "<hex>", msg)
    msg = re.sub(r"\b\d{3,}\b", "<n>", msg)
    msg = re.sub(r"@[0-9a-f]{5,}\b", "@<hash>", msg)
    return msg.strip()[:200]


def is_framework(frame: str, app_prefixes: tuple[str, ...]) -> bool:
    if app_prefixes:
        return not frame.startswith(app_prefixes) and not any(f" {p}" in frame for p in app_prefixes)
    if frame.startswith(FRAMEWORK_PREFIXES):
        return True
    image = frame.split(" ", 1)[0]
    return image in IOS_SYSTEM_IMAGES


def norm_java(cls: str, method: str, loc: str, keep_lines: bool) -> str:
    cls = re.sub(r"\$\$?(?:Lambda|ExternalSynthetic)[\w$]*", "", cls)
    cls = re.sub(r"\$\d+\b", "", cls)
    method = re.sub(r"\$lambda\$\d+|\$\d+$", "", method)
    out = f"{cls}.{method}"
    if keep_lines and ":" in loc:
        out += ":" + loc.rsplit(":", 1)[1]
    return out


def norm_dart(symbol: str, loc: str, keep_lines: bool) -> str:
    path = re.sub(r":\d+(?::\d+)?$", "", loc) if not keep_lines else loc
    symbol = re.sub(r"\.<anonymous closure>", ".<closure>", symbol)
    return f"{path} {symbol}"


def norm_js(fn: str | None, loc: str) -> str:
    loc = re.sub(r"^.*/", "", loc.split("?", maxsplit=1)[0])
    if loc.endswith((".bundle", ".jsbundle")) or "address at" in loc:
        loc = "bundle"
    return f"{loc} {fn or '<anonymous>'}"


def parse_text_block(lines: list[str], source: str, keep_lines: bool) -> Crash | None:
    text = "\n".join(lines)
    if "Thread " in text and ("Crashed" in text or "Exception Type:" in text) or "Incident Identifier:" in text:
        return parse_apple_text(lines, source)
    crash = Crash("unknown", source)
    causes: list[tuple[str, str, list[str]]] = []  # (type, message, frames)
    current: tuple[str, str, list[str]] | None = None
    for line in lines:
        m = JAVA_FRAME.match(line)
        if m:
            crash.kind = "android" if crash.kind == "unknown" else crash.kind
            if current is None:
                current = ("", "", [])
                causes.append(current)
            current[2].append(norm_java(m.group(1), m.group(2), m.group(3), keep_lines))
            continue
        m = DART_FRAME.match(line)
        if m:
            crash.kind = "flutter"
            if current is None:
                current = ("", "", [])
                causes.append(current)
            current[2].append(norm_dart(m.group(2), m.group(3), keep_lines))
            continue
        m = JS_FRAME_V8.match(line) or JS_FRAME_AT.match(line)
        if m and (".js" in line or "bundle" in line or "address at" in line or "@" in line):
            crash.kind = "react-native" if crash.kind == "unknown" else crash.kind
            if current is None:
                current = ("", "", [])
                causes.append(current)
            current[2].append(norm_js(m.group("fn"), m.group("loc")))
            continue
        m = JAVA_EXC.match(line)
        if m:
            current = (m.group("type"), m.group("msg") or "", [])
            causes.append(current)
            continue
        m = JS_EXC.match(line)
        if m:
            current = (m.group("type"), m.group("msg") or "", [])
            causes.append(current)
            crash.kind = "react-native" if crash.kind == "unknown" else crash.kind
            continue
        m = DART_EXC.search(line)
        if m:
            msg = m.group("msg")
            if msg.startswith("type '") and "is not a subtype of" in msg:
                dtype = "TypeError"
            else:
                dtype = msg.split(":", 1)[0] if ":" in msg[:40] else "DartError"
            current = (dtype.strip(), msg.split(":", 1)[1].strip() if ":" in msg[:40] else msg, [])
            causes.append(current)
            continue
    causes = [c for c in causes if c[0] or c[2]]
    if not causes or not any(c[2] for c in causes):
        return None
    # Root cause: the deepest cause that has frames (Java "Caused by" chains end with it).
    typed = [c for c in causes if c[0]]
    root = next((c for c in reversed(causes) if c[0] and c[2]), None) or causes[-1]
    crash.type = root[0] or (typed[-1][0] if typed else "UnknownError")
    crash.message = root[1] or (typed[-1][1] if typed else "")
    crash.frames = root[2] or next(c[2] for c in causes if c[2])
    if crash.kind == "unknown":
        crash.kind = "android"
    return crash


def parse_apple_text(lines: list[str], source: str) -> Crash | None:
    crash = Crash("ios", source)
    process = None
    section = None
    crashed_frames: list[str] = []
    backtrace: list[str] = []
    for line in lines:
        if m := IOS_PROCESS.match(line):
            process = m.group(1)
        if m := IOS_EXC_TYPE.match(line):
            crash.type = m.group(1).strip()
        if m := IOS_NSEXC.search(line):
            crash.type, crash.message = m.group(1), m.group(2)
        if line.startswith("Exception Reason:") and not crash.message:
            crash.message = line.split(":", 1)[1].strip()
        if line.startswith("Last Exception Backtrace"):
            section = "backtrace"
            continue
        if re.match(r"^Thread \d+( name:.*)?Crashed", line) or re.match(r"^Thread \d+ Crashed", line):
            section = "crashed"
            continue
        if re.match(r"^Thread \d+", line) or not line.strip():
            if section and (crashed_frames if section == "crashed" else backtrace) or re.match(r"^Thread \d+", line):
                section = None
            continue
        m = IOS_FRAME.match(line.strip())
        if m and section:
            image, sym = m.group(2), re.sub(r"\s+\+\s+\d+$", "", m.group(3))
            sym = re.sub(r"\s+\(.*\)$", "", sym)
            if re.match(r"^0x[0-9a-f]+$", sym) or sym == image:
                sym = "<unsymbolicated>"
            (backtrace if section == "backtrace" else crashed_frames).append(f"{image} {sym}")
    crash.frames = backtrace or crashed_frames
    if not crash.frames:
        return None
    crash.type = crash.type or "UnknownCrash"
    if process:
        crash.app_frame = next((f for f in crash.frames if f.split(" ", 1)[0] == process), None)
    return crash


def parse_ips(header: dict, body: dict, source: str) -> Crash | None:
    crash = Crash("ios", source)
    images = [i.get("name", "?") for i in body.get("usedImages") or []]
    exc = body.get("exception") or {}
    crash.type = " ".join(x for x in (exc.get("type"), f"({exc['signal']})" if exc.get("signal") else None) if x)
    asi = body.get("asi") or {}
    reason = body.get("exception", {}).get("message") or " ".join(sum((v for v in asi.values()), []))[:200]
    crash.message = reason or ""
    frames = body.get("lastExceptionBacktrace")
    if not frames:
        threads = body.get("threads") or []
        trig = next((t for t in threads if t.get("triggered")), threads[0] if threads else {})
        frames = trig.get("frames") or []
    for f in frames:
        idx = f.get("imageIndex")
        image = images[idx] if isinstance(idx, int) and 0 <= idx < len(images) else "?"
        crash.frames.append(f"{image} {f.get('symbol') or '<unsymbolicated>'}")
    proc = body.get("procName") or header.get("app_name") or header.get("name")
    if proc:
        crash.app_frame = next((x for x in crash.frames if x.split(" ", 1)[0] == proc), None)
    crash.version = header.get("app_version")
    crash.type = crash.type or "UnknownCrash"
    return crash if crash.frames else None


def split_text(text: str) -> list[list[str]]:
    """Split a text dump into report blocks."""
    lines = text.splitlines()
    if "Incident Identifier:" in text:
        blocks, cur = [], []
        for line in lines:
            if line.startswith("Incident Identifier:") and cur:
                blocks.append(cur)
                cur = []
            cur.append(line)
        return [*blocks, cur] if cur else blocks
    blocks, cur, has_frames = [], [], False
    for line in lines:
        stripped = LOGCAT_PREFIX.sub("", line)
        is_frame = bool(
            JAVA_FRAME.match(stripped)
            or DART_FRAME.match(stripped)
            or JS_FRAME_V8.match(stripped)
            or JS_FRAME_AT.match(stripped)
        )
        starts = (
            SEPARATOR.match(stripped)
            or "FATAL EXCEPTION" in stripped
            or (
                has_frames
                and not is_frame
                and stripped.strip()
                and not stripped.lstrip().startswith(("Caused by", "...", "Process:", "#"))
                and (JAVA_EXC.match(stripped) or JS_EXC.match(stripped) or DART_EXC.search(stripped))
            )
        )
        if starts and cur:
            blocks.append(cur)
            cur, has_frames = [], False
        if SEPARATOR.match(stripped):
            continue
        cur.append(stripped)
        has_frames = has_frames or is_frame
    if cur:
        blocks.append(cur)
    return blocks


def _get(obj: dict, keys: tuple[str, ...]):
    for k in keys:
        if k in obj and obj[k] not in (None, ""):
            return obj[k]
    return None


def parse_json_item(item: dict, source: str, keep_lines: bool) -> list[Crash]:
    crashes: list[Crash] = []
    if isinstance(item.get("exceptions"), list) and item["exceptions"]:
        excs = item["exceptions"]
        exc = next((e for e in excs if e.get("blamed")), excs[-1])
        c = Crash(str(item.get("platform") or "crashlytics").lower(), source)
        c.type = exc.get("type") or "UnknownError"
        c.message = exc.get("exception_message") or exc.get("message") or ""
        for f in exc.get("frames") or []:
            sym = f.get("symbol") or "?"
            name = f"{f['library']} {sym}" if f.get("library") else sym
            c.frames.append(name)
            if f.get("owned") and c.app_frame is None:
                c.app_frame = name
        if c.frames:
            crashes.append(c)
    else:
        stack = _get(item, STACK_KEYS)
        if isinstance(stack, list):
            stack = "\n".join(str(s) for s in stack)
        if isinstance(stack, str):
            for block in split_text(stack):
                c = parse_text_block(block, source, keep_lines)
                if c:
                    crashes.append(c)
    count = _get(item, COUNT_KEYS)
    version = _get(item, VERSION_KEYS)
    if version is None and isinstance(item.get("application"), dict):
        version = item["application"].get("display_version")
    for c in crashes:
        if isinstance(count, (int, float)) and count > 0:
            c.count = int(count)
        if version is not None:
            c.version = str(version)
    return crashes


def parse_file(path: Path, keep_lines: bool = False) -> list[Crash]:
    text = path.read_text(encoding="utf-8", errors="replace")
    src = path.name
    stripped = text.lstrip()
    if stripped.startswith("{") and "\n" in stripped:
        first, rest = stripped.split("\n", 1)
        try:
            header = json.loads(first)
            if isinstance(header, dict) and "bug_type" in header:
                c = parse_ips(header, json.loads(rest), src)
                return [c] if c else []
        except json.JSONDecodeError:
            pass
    if stripped.startswith(("[", "{")):
        items = None
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                for key in ("crashes", "events", "issues", "data", "items", "rows"):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
                else:
                    data = [data]
            items = data
        except json.JSONDecodeError:
            try:
                items = [json.loads(line) for line in stripped.splitlines() if line.strip()]
            except json.JSONDecodeError:
                items = None
        if items is not None:
            out = []
            for it in items:
                if isinstance(it, dict):
                    out += parse_json_item(it, src, keep_lines)
            return out
    return [c for c in (parse_text_block(b, src, keep_lines) for b in split_text(text)) if c]


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files += sorted(
                f
                for f in p.rglob("*")
                if f.is_file() and f.suffix in {".txt", ".log", ".json", ".jsonl", ".ips", ".crash"}
            )
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(f"{raw}: no such file or directory")
    return files


def signature(c: Crash, app_prefixes: tuple[str, ...]) -> tuple[str, str]:
    if c.app_frame is None or app_prefixes:
        c.app_frame = next((f for f in c.frames if not is_framework(f, app_prefixes)), None)
    top = c.app_frame or (c.frames[0] if c.frames else "?")
    ctype = re.sub(r"\s+", " ", c.type)
    return f"{ctype} @ {top}", top


def group(crashes: list[Crash], app_prefixes: tuple[str, ...] = ()) -> list[dict]:
    groups: dict[str, dict] = {}
    for c in crashes:
        sig, top = signature(c, app_prefixes)
        g = groups.setdefault(
            sig,
            {
                "signature": sig,
                "type": c.type,
                "platform": c.kind,
                "app_frame": c.app_frame,
                "top_frames": c.frames[:5],
                "count": 0,
                "reports": 0,
                "versions": set(),
                "sources": set(),
                "sample_message": scrub(c.message),
                "unsymbolicated": any("<unsymbolicated>" in f for f in c.frames[:5]),
            },
        )
        g["count"] += c.count
        g["reports"] += 1
        if c.version:
            g["versions"].add(c.version)
        g["sources"].add(c.source)
    total = sum(g["count"] for g in groups.values()) or 1
    out = sorted(groups.values(), key=lambda g: (-g["count"], g["signature"]))
    for i, g in enumerate(out, 1):
        g["rank"] = i
        g["percent"] = round(100 * g["count"] / total, 1)
        g["versions"] = sorted(g["versions"])
        g["sources"] = sorted(g["sources"])
    return out


def load_baseline(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("groups") or data.get("signatures") or []
    return {d["signature"] if isinstance(d, dict) else str(d) for d in data}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("paths", nargs="+", help="crash files or folders (.txt .log .json .jsonl .ips .crash)")
    p.add_argument("--app", action="append", default=[], help="app frame prefix, e.g. com.example.app, package:my_app")
    p.add_argument("--top", type=int, default=20, help="show this many groups (default 20)")
    p.add_argument("--keep-lines", action="store_true", help="include line numbers in signatures")
    p.add_argument("--baseline", type=Path, help="previous --json output; report and fail on new signatures")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    try:
        files = collect(args.paths)
        crashes = [c for f in files for c in parse_file(f, args.keep_lines)]
        baseline = load_baseline(args.baseline) if args.baseline else None
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    groups = group(crashes, tuple(args.app))
    new = [g for g in groups if baseline is not None and g["signature"] not in baseline]
    for g in groups:
        g["new"] = baseline is not None and g["signature"] not in baseline
    if args.json:
        print(
            json.dumps(
                {
                    "files": len(files),
                    "reports": len(crashes),
                    "total": sum(g["count"] for g in groups),
                    "groups": groups[: args.top],
                },
                indent=2,
            )
        )
    else:
        total = sum(g["count"] for g in groups)
        print(f"{len(crashes)} report(s), {total} crash(es) in {len(groups)} group(s) from {len(files)} file(s)\n")
        for g in groups[: args.top]:
            flag = " NEW" if g["new"] else ""
            print(f"#{g['rank']:<3} {g['count']:>6}  {g['percent']:>5}%  [{g['platform']}] {g['signature']}{flag}")
            if g["sample_message"]:
                print(f"       message: {g['sample_message']}")
            if g["versions"]:
                print(f"       versions: {', '.join(g['versions'])}")
            if not g["app_frame"]:
                print("       note: no app frame found (pass --app <prefix>, or the crash is in a library/OS)")
            if g["unsymbolicated"]:
                print("       note: unsymbolicated frames - upload dSYMs / symbolicate first")
        if len(groups) > args.top:
            print(f"\n... {len(groups) - args.top} more group(s); use --top")
        if baseline is not None:
            print(f"\n{len(new)} new signature(s) compared with the baseline")
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
