import json

from conftest import fixture, load_script, run_script

SKILL = "crash-log-triage"
SCRIPT = "triage_crashes.py"
mod = load_script(SKILL, SCRIPT)
CRASHES = fixture("crashes")


def groups_for(name, app=()):
    return mod.group(mod.parse_file(CRASHES / name), tuple(app))


def test_android_logcat_root_cause_and_grouping():
    groups = groups_for("android-logcat.txt")
    assert [g["count"] for g in groups] == [2, 1]
    top = groups[0]
    assert top["signature"] == "java.lang.IllegalStateException @ com.example.pocketbudget.data.BudgetRepository.load"
    assert top["platform"] == "android"
    assert "jane@example.com" not in top["sample_message"] and "<email>" in top["sample_message"]
    assert "12345" not in top["sample_message"]
    second = groups[1]
    assert second["app_frame"] == "com.example.pocketbudget.sync.SyncWorker$doWork.invokeSuspend"


def test_keep_lines_splits_groups():
    crashes = mod.parse_file(CRASHES / "android-logcat.txt", keep_lines=True)
    assert len(mod.group(crashes)) == 3


def test_flutter_traces():
    groups = groups_for("flutter.txt")
    sigs = {g["signature"] for g in groups}
    assert "Bad state @ package:pocket_budget/screens/expense_list.dart ExpenseList._selected" in sigs
    assert "TypeError @ package:pocket_budget/models/expense.dart Expense.fromJson" in sigs
    assert all(g["platform"] == "flutter" for g in groups)


def test_react_native_dev_and_release_bundles_group_together():
    groups = groups_for("react-native.txt")
    assert len(groups) == 1 and groups[0]["count"] == 2
    assert groups[0]["signature"] == "TypeError @ bundle BudgetSummary"


def test_apple_crash_text():
    groups = groups_for("ios.crash")
    by_type = {g["type"]: g for g in groups}
    abort = by_type["EXC_CRASH (SIGABRT)"]
    assert abort["app_frame"] == "Runner -[ReceiptScanner startSession]"  # from Last Exception Backtrace
    segv = by_type["EXC_BAD_ACCESS (SIGSEGV)"]
    assert segv["unsymbolicated"] is True
    assert segv["top_frames"][0].startswith("Flutter")


def test_ips_json():
    groups = groups_for("runner.ips")
    assert groups[0]["signature"] == "EXC_BREAKPOINT (SIGTRAP) @ Runner BudgetStore.total(for:)"
    assert groups[0]["versions"] == ["2.3.0"]


def test_crashlytics_bigquery_rows():
    groups = groups_for("crashlytics-bigquery.json")
    assert len(groups) == 1
    g = groups[0]
    assert g["app_frame"] == "com.example.pocketbudget.ui.AddExpenseViewModel.save"
    assert g["versions"] == ["2.2.0", "2.3.0"] and g["count"] == 2


def test_json_export_with_counts():
    groups = groups_for("export.json")
    assert [g["count"] for g in groups] == [120, 30]
    assert groups[0]["percent"] == 80.0
    assert groups[1]["type"] == "java.lang.OutOfMemoryError"


def test_jsonl():
    groups = groups_for("events.jsonl")
    assert groups[0]["count"] == 2 and groups[0]["versions"] == ["1.8.0", "1.8.1"]


def test_app_prefix_option():
    crashes = mod.parse_file(CRASHES / "android-logcat.txt")
    groups = mod.group(crashes, ("android.app.",))
    assert groups[0]["app_frame"].startswith("android.app.")


def test_scrub():
    msg = mod.scrub("user 4f1c2a9e-1111-2222-3333-444455556666 at https://x.example.com/a?b=1 id 998877 ptr 0xdeadbeef")
    assert msg == "user <uuid> at <url> id <n> ptr <hex>"


def test_directory_and_baseline(tmp_path):
    files = mod.collect([str(CRASHES)])
    assert len(files) == 8
    crashes = [c for f in files for c in mod.parse_file(f)]
    groups = mod.group(crashes)
    assert len(groups) >= 10
    base = tmp_path / "baseline.json"
    base.write_text(json.dumps({"groups": groups[1:]}))
    assert len(mod.load_baseline(base)) == len(groups) - 1


def test_cli(tmp_path):
    r = run_script(SKILL, SCRIPT, str(CRASHES / "android-logcat.txt"))
    assert r.returncode == 0 and "IllegalStateException" in r.stdout and "jane@" not in r.stdout
    r = run_script(SKILL, SCRIPT, str(CRASHES), "--json", "--top", "3")
    data = json.loads(r.stdout)
    assert data["files"] == 8 and len(data["groups"]) == 3
    base = tmp_path / "base.json"
    base.write_text(r.stdout)
    r = run_script(SKILL, SCRIPT, str(CRASHES), "--baseline", str(base))
    assert r.returncode == 1 and "NEW" in r.stdout
    full = run_script(SKILL, SCRIPT, str(CRASHES), "--json", "--top", "100").stdout
    base.write_text(full)
    assert run_script(SKILL, SCRIPT, str(CRASHES), "--baseline", str(base)).returncode == 0
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing.txt")).returncode == 2
    assert run_script(SKILL, SCRIPT, "--help").returncode == 0
