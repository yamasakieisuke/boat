#!/usr/bin/env python3
from __future__ import annotations
"""
積み残しタスク管理・実行スクリプト
──────────────────────────────────────────────────────────────
data/pending_tasks.json に登録されたタスクを順番に再試行し、
・成功 → タスク削除
・レース発走時刻を過ぎていた → タスク削除（手遅れ）
・未公開のまま → タスクを保持（次回実行まで積み残し）

タスクの種類:
  exhibition : 展示データ取得（fetch_at = 発走10分前）。福岡(22)はオリジナル展示も同時取得。
  odds       : 3連単オッズ取得（fetch_at = 発走10分前）
  results    : 結果CSV取得（翌朝以降に公開）
  verify     : 的中率照合（results取得済みが前提）

タスクのタイミング制御:
  fetch_at   : この時刻より前は試行しない（展示・オッズ = 発走10分前）
  next_try_at: 失敗時の次回試行時刻（5分後 = 発走5分前に再試行）
  retry_count: 試行回数。MAX_RETRY_COUNT=2 で打ち切り（1回目失敗→5分前再試行→失敗で削除）
  deadline   : この時刻を過ぎたらタスクを自動削除（展示・オッズ = 発走時刻）

依頼キュー連携:
  data/fetch_requests.json に {jcd, date, [r1_start], [races]} を入れておくと、
  run_all() 冒頭の process_fetch_requests() が pending に変換してから処理する。
  morning は予測のみ生成し、追跡対象会場は依頼ベースで明示的に登録する設計。

使い方:
  python3 scripts/run_pending.py             # 全タスクを試行（依頼キューも自動消化）
  python3 scripts/run_pending.py --list      # タスク一覧を表示するだけ
  python3 scripts/run_pending.py --add ...   # タスクを手動登録
  python3 scripts/run_pending.py --process-requests  # 依頼キューだけ処理して終了
──────────────────────────────────────────────────────────────
"""

import json
import datetime
import argparse
import time
import sys
import os
from pathlib import Path

BASE_DIR         = Path(__file__).parent.parent
DATA_DIR         = BASE_DIR / "data"
OUTPUT_DIR       = BASE_DIR / "output"
PENDING_FILE     = DATA_DIR / "pending_tasks.json"
PENDING_MD_FILE  = OUTPUT_DIR / "pending_tasks.md"
FETCH_REQUESTS_FILE = DATA_DIR / "fetch_requests.json"
EXHIBITION_FETCH_LEAD_MIN = 10   # 発走の何分前から取得を試みるか（v5.22: 15→10）
ODDS_FETCH_LEAD_MIN       = 10   # 同上（v5.22: 15→10）
RETRY_INTERVAL_MIN        = 5    # 失敗時の次回試行までの間隔（v5.22: 2→5。10分前失敗→5分前で再試行）
MAX_RETRY_COUNT           = 2    # 試行回数の上限。これに達したら deadline 待たず削除（v5.22 新規）

QUIET = False  # --quiet 指定時に True（積み残し 0件のときに出力を抑制）

VENUE_NAMES = {
    "01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川",
    "06":"浜名湖","07":"蒲郡","08":"常滑","09":"津","10":"三国",
    "11":"びわこ","12":"住之江","13":"尼崎","14":"鳴門","15":"丸亀",
    "16":"児島","17":"宮島","18":"徳山","19":"下関","20":"若松",
    "21":"芦屋","22":"福岡","23":"唐津","24":"大村",
}


# ── タスクファイル I/O ────────────────────────────────────────────

def load_tasks() -> list[dict]:
    if PENDING_FILE.exists():
        with open(PENDING_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_tasks(tasks: list[dict]):
    DATA_DIR.mkdir(exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    _update_md(tasks)


def add_task(task: dict):
    """タスクを追加（同一IDがあれば上書き）"""
    tasks = load_tasks()
    tasks = [t for t in tasks if t["id"] != task["id"]]
    tasks.append(task)
    save_tasks(tasks)
    print(f"  ➕ タスク登録: [{task['id']}]  期限={task['deadline']}")


def remove_task(task_id: str):
    tasks = [t for t in load_tasks() if t["id"] != task_id]
    save_tasks(tasks)


def _update_md(tasks: list[dict]):
    """output/pending_tasks.md を更新（目視用）"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 積み残しタスク\n",
        f"*最終更新: {now_str}*\n\n",
    ]
    if not tasks:
        lines.append("（積み残しタスクなし）\n")
    else:
        lines.append("| ID | 種別 | 会場 | 日付 | R | 取得開始(10分前) | 期限(発走) | 登録日時 |\n")
        lines.append("|---|---|---|---|---|---|---|---|\n")
        for t in sorted(tasks, key=lambda x: x.get("fetch_at", x.get("deadline", ""))):
            vname = VENUE_NAMES.get(t.get("jcd", ""), t.get("jcd", "-"))
            fetch_at = t.get("fetch_at", "—")
            lines.append(
                f"| {t['id']} "
                f"| {t['type']} "
                f"| {vname}({t.get('jcd','-')}) "
                f"| {t.get('date','-')} "
                f"| R{t.get('race_no','-')} "
                f"| {fetch_at} "
                f"| {t.get('deadline','-')} "
                f"| {t.get('created_at','-')} |\n"
            )
    with open(PENDING_MD_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ── 発走時刻の推定 ────────────────────────────────────────────────

def get_race_start_time(jcd: str, date: str, race_no: int) -> datetime.datetime | None:
    """
    出走表 JSON の race_start_time フィールドを優先参照。
    なければ boatrace.jp の racelist ページから取得して推定。
    """
    # ① 出走表に start_time があれば使う
    rc_path = DATA_DIR / "racecards" / date / f"{jcd}_R{race_no:02d}.json"
    if rc_path.exists():
        with open(rc_path, encoding="utf-8") as f:
            rc = json.load(f)
        st = rc.get("race_start_time") or rc.get("start_time")
        if st:
            try:
                return datetime.datetime.strptime(f"{date} {st}", "%Y%m%d %H:%M")
            except Exception:
                pass

    # ② scraper 側の共通ロジックで全12Rの実際の発走時刻を取得
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from scraper import scrape_start_times
        times = scrape_start_times(jcd, date)
        st = times.get(race_no)
        if st:
            return datetime.datetime.strptime(f"{date} {st}", "%Y%m%d %H:%M")
    except Exception as e:
        print(f"  [WARN] 発走時刻取得失敗: {e}")

    return None


# ── 各タスクの実行 ────────────────────────────────────────────────

def run_exhibition_task(task: dict) -> str:
    """
    展示データを取得する。
    戻り値: "done" | "not_yet" | "expired"
    """
    jcd      = task["jcd"]
    date     = task["date"]
    race_no  = int(task["race_no"])
    deadline = datetime.datetime.fromisoformat(task["deadline"])
    now      = datetime.datetime.now()

    # 既に有効なデータがあれば deadline 前後問わず done（再 predict トリガに乗せるため）
    ex_path = DATA_DIR / "raw" / date / f"{jcd}_R{race_no:02d}_exhibition.json"
    if ex_path.exists():
        with open(ex_path, encoding="utf-8") as f:
            ex = json.load(f)
        records = ex.get("exhibition", [])
        try:
            valid = any(float(r.get("exhibition_time", "")) > 0 for r in records)
        except (ValueError, TypeError):
            valid = False
        if valid:
            return "done"

    if now > deadline:
        return "expired"

    # 取得を試みる
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from scraper import scrape_exhibition, scrape_pitreport
        result = scrape_exhibition(jcd, date, race_no)
        if result and result.get("exhibition"):
            # R7〜12はピットレポートも同時取得（公式仕様: R7以降のみ掲載）
            if race_no >= 7:
                try:
                    scrape_pitreport(jcd, date, race_no)
                except Exception as pe:
                    print(f"  [WARN] pitreport取得失敗（続行）: {pe}")
            # 福岡(jcd=22)はオリジナル展示（一周/まわり足/直線）も同時取得（v5.21）
            if jcd == "22":
                try:
                    from scraper import scrape_fukuoka_original_exhibition
                    scrape_fukuoka_original_exhibition(date, race_no)
                except Exception as oe:
                    print(f"  [WARN] 福岡オリジナル展示取得失敗（続行）: {oe}")
            return "done"
        return "not_yet"
    except Exception as e:
        print(f"  [ERROR] exhibition取得失敗: {e}")
        return "not_yet"


def run_odds_task(task: dict) -> str:
    """
    3連単オッズデータを取得する。
    戻り値: "done" | "not_yet" | "expired"
    """
    jcd      = task["jcd"]
    date     = task["date"]
    race_no  = int(task["race_no"])
    deadline = datetime.datetime.fromisoformat(task["deadline"])
    now      = datetime.datetime.now()

    # 既に有効なデータがあれば deadline 前後問わず done（再 predict トリガに乗せるため）
    odds_path = DATA_DIR / "odds" / date / f"{jcd}_R{race_no:02d}.json"
    if odds_path.exists():
        with open(odds_path, encoding="utf-8") as f:
            od = json.load(f)
        if od.get("odds_3t"):
            return "done"

    if now > deadline:
        return "expired"

    # 取得を試みる
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from scraper import scrape_odds
        result = scrape_odds(jcd, date, race_no)
        if result and result.get("odds_3t"):
            return "done"
        return "not_yet"
    except Exception as e:
        print(f"  [ERROR] odds取得失敗: {e}")
        return "not_yet"


def run_results_task(task: dict) -> str:
    """
    結果CSVを取得する。
    戻り値: "done" | "not_yet" | "expired"
    """
    date     = task["date"]
    deadline = datetime.datetime.fromisoformat(task["deadline"])
    now      = datetime.datetime.now()

    if now > deadline:
        return "expired"

    # 既に取得済みか確認（該当会場のデータが入っているか）
    jcd       = task.get("jcd")
    csv_path  = DATA_DIR / "results_csv" / f"{date}.csv"
    if csv_path.exists() and jcd:
        import csv as csv_mod
        with open(csv_path, encoding="utf-8-sig") as f:
            rows = list(csv_mod.DictReader(f))
        venue_name = VENUE_NAMES.get(jcd, "")
        if any(r.get("venue_name", "").strip() == venue_name for r in rows):
            return "done"

    # 再取得を試みる
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from fetch_results import process_day, write_csv
        import csv as csv_mod
        from io import StringIO

        # キャッシュTXTを削除して強制再取得
        raw_txt = DATA_DIR / "results_raw" / f"K{date[2:]}.txt"
        if raw_txt.exists():
            raw_txt.unlink()

        records = process_day(date)
        if not records:
            return "not_yet"

        venue_name = VENUE_NAMES.get(jcd, "")
        if any(r.get("venue_name", "").strip() == venue_name for r in records):
            return "done"
        return "not_yet"
    except Exception as e:
        print(f"  [ERROR] results取得失敗: {e}")
        return "not_yet"


def _publish_review_to_wordpress(jcd: str, date: str) -> None:
    """verify 完了後に review_summary 入り payload を WordPress へ再送信する。

    WP_SYNC_URL / WP_SYNC_TOKEN 環境変数が未設定の場合はスキップ（エラーにしない）。
    WordPress 送信の失敗は警告のみ — verify 結果自体には影響しない。
    """
    sync_url = os.getenv("WP_SYNC_URL", "")
    token    = os.getenv("WP_SYNC_TOKEN", "")
    if not sync_url or not token:
        print("  [WP] WP_SYNC_URL / WP_SYNC_TOKEN 未設定 → WordPress 再送信スキップ")
        return
    try:
        import importlib
        sys.path.insert(0, str(Path(__file__).parent))
        import publish_wordpress as pw_mod
        importlib.reload(pw_mod)
        timeout  = float(os.getenv("WP_SYNC_TIMEOUT", "10"))
        payload  = pw_mod.build_request_payload(jcd, date)
        pw_mod.write_payload_file(jcd, date, payload)
        response = pw_mod.publish_payload(payload, sync_url, token, timeout)
        post_id  = response.get("id", "?")
        print(f"  [WP] 振り返り反映完了 (post_id={post_id})")
    except Exception as e:
        print(f"  [WP] WordPress 再送信失敗（verify 結果は保存済み）: {e}")


def run_verify_task(task: dict) -> str:
    """
    的中率照合を実行する。
    戻り値: "done" | "not_yet" | "expired"
    """
    jcd      = task["jcd"]
    date     = task["date"]
    deadline = datetime.datetime.fromisoformat(task["deadline"])
    now      = datetime.datetime.now()

    if now > deadline:
        return "expired"

    # 結果CSVに該当会場データがあるか確認
    csv_path   = DATA_DIR / "results_csv" / f"{date}.csv"
    venue_name = VENUE_NAMES.get(jcd, "")
    if not csv_path.exists():
        return "not_yet"

    import csv as csv_mod
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv_mod.DictReader(f))
    if not any(r.get("venue_name", "").strip() == venue_name for r in rows):
        return "not_yet"

    # 照合実行
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import importlib, verify as verify_mod
        importlib.reload(verify_mod)
        verify_mod.run_verification(jcd, date, date, verbose=False, save=True)
    except Exception as e:
        print(f"  [ERROR] verify失敗: {e}")
        return "not_yet"

    # verify 成功後に WordPress へ振り返り付き payload を再送信
    _publish_review_to_wordpress(jcd, date)
    return "done"


# ── メインループ ──────────────────────────────────────────────────

def run_all(dry_run: bool = False, jcd_filter: list[str] | None = None,
            success_report_file: str | None = None):
    # 先に依頼キューを消化して pending を最新化（dry_run でも消化する。
    # 依頼処理は副作用が pending 登録のみで、cron でも安全に毎回流せる）
    if not dry_run:
        try:
            process_fetch_requests()
        except Exception as e:
            print(f"  [WARN] 依頼キュー処理で例外（続行）: {e}")

    tasks   = load_tasks()
    if jcd_filter:
        tasks = [t for t in tasks if t.get("jcd") in jcd_filter]
    if not tasks:
        if not QUIET:
            if jcd_filter:
                print(f"指定会場({','.join(jcd_filter)})に積み残しタスクなし。")
            else:
                print("積み残しタスクなし。")
        return

    # --quiet 時は「今すぐ実行可能な exhibition/odds タスクが0件」なら静かに抜ける（cron ポーリング用）
    # results/verify タイプは朝の morning_verify が処理するので、cron ポーリング対象外
    if QUIET:
        now = datetime.datetime.now()
        def _is_runnable(t):
            if t.get("type") not in ("exhibition", "odds"):
                return False
            fa = t.get("fetch_at")
            nta = t.get("next_try_at")
            if fa and datetime.datetime.fromisoformat(fa) > now:
                return False
            if nta and datetime.datetime.fromisoformat(nta) > now:
                return False
            # deadline を過ぎている場合も expired として処理したいので runnable 扱い
            return True
        if not any(_is_runnable(t) for t in tasks):
            return

    print(f"\n{'='*60}")
    print(f"  🔄 積み残しタスク実行  {len(tasks)}件  {datetime.datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*60}")

    keep, done_ids, expired_ids = [], [], []
    success_pairs: set[tuple[str, str]] = set()  # (jcd, date) for exhibition/odds success

    for task in tasks:
        tid  = task["id"]
        typ  = task["type"]
        vname = VENUE_NAMES.get(task.get("jcd",""), task.get("jcd","-"))
        rno  = task.get("race_no", "-")
        label = f"[{tid}] {typ} {vname} R{rno}"

        if dry_run:
            print(f"  📋 {label}  期限={task['deadline']}")
            keep.append(task)
            continue

        # fetch_at が設定されていて、まだその時刻より前なら待機
        fetch_at_str = task.get("fetch_at")
        if fetch_at_str:
            fetch_at_dt = datetime.datetime.fromisoformat(fetch_at_str)
            if datetime.datetime.now() < fetch_at_dt:
                remaining = int((fetch_at_dt - datetime.datetime.now()).total_seconds() / 60)
                print(f"  ⏰ {label}  取得開始まであと {remaining}分（{fetch_at_str}）→ スキップ")
                keep.append(task)
                continue
        next_try_at_str = task.get("next_try_at")
        if next_try_at_str:
            next_try_at_dt = datetime.datetime.fromisoformat(next_try_at_str)
            if datetime.datetime.now() < next_try_at_dt:
                remaining = max(1, int((next_try_at_dt - datetime.datetime.now()).total_seconds() / 60))
                print(f"  ⏰ {label}  次回再試行まであと {remaining}分（{next_try_at_str}）→ スキップ")
                keep.append(task)
                continue

        print(f"  ⏳ {label} ... ", end="", flush=True)

        if typ == "exhibition":
            result = run_exhibition_task(task)
        elif typ == "odds":
            result = run_odds_task(task)
        elif typ == "results":
            result = run_results_task(task)
        elif typ == "verify":
            result = run_verify_task(task)
        else:
            print("unknown type → skip")
            keep.append(task)
            continue

        if result == "done":
            print("✅ 完了 → タスク削除")
            done_ids.append(tid)
            if typ in ("exhibition", "odds") and task.get("jcd") and task.get("date"):
                success_pairs.add((task["jcd"], task["date"]))
        elif result == "expired":
            print("⌛ 期限切れ → タスク削除")
            expired_ids.append(tid)
        else:
            if typ in ("exhibition", "odds"):
                task["retry_count"] = int(task.get("retry_count", 0) or 0) + 1
                if task["retry_count"] >= MAX_RETRY_COUNT:
                    # 最大試行回数に達した → deadline を待たず即削除
                    print(f"⛔ 試行{task['retry_count']}回失敗（上限{MAX_RETRY_COUNT}） → タスク削除")
                    expired_ids.append(tid)
                else:
                    deadline_dt = datetime.datetime.fromisoformat(task["deadline"])
                    next_try_dt = min(
                        datetime.datetime.now() + datetime.timedelta(minutes=RETRY_INTERVAL_MIN),
                        deadline_dt
                    )
                    task["next_try_at"] = next_try_dt.strftime("%Y-%m-%dT%H:%M:00")
                    print(f"⏸  未公開/未整形 → {RETRY_INTERVAL_MIN}分後に再試行（{task['retry_count']}/{MAX_RETRY_COUNT}）")
                    keep.append(task)
            else:
                # results / verify はデッドラインまで無制限に継続
                print("⏸  未公開 → 積み残し継続")
                keep.append(task)

        time.sleep(1.0)

    save_tasks(keep)

    print(f"\n  完了: {len(done_ids)}件  期限切れ: {len(expired_ids)}件  残: {len(keep)}件")
    print(f"{'='*60}\n")

    if success_report_file and success_pairs:
        try:
            with open(success_report_file, "w", encoding="utf-8") as f:
                for jcd, date in sorted(success_pairs):
                    f.write(f"{jcd}\t{date}\n")
            print(f"  [REPORT] 成功 jcd-date {len(success_pairs)}件 → {success_report_file}")
        except OSError as e:
            print(f"  [WARN] success report 書き込み失敗: {e}")


# ── タスク登録ヘルパー ────────────────────────────────────────────

def _resolve_race_dt(jcd: str, date: str, race_no: int, r1_time_str: str = "") -> datetime.datetime:
    """発走時刻を解決して返す（共通ヘルパー）。取得失敗時は翌朝6時をフォールバック。"""
    if r1_time_str:
        r1_dt = datetime.datetime.strptime(f"{date} {r1_time_str}", "%Y%m%d %H:%M")
        # ※ r1_time_str 指定時は Web 取得して実際の時刻を使う（取得失敗時のみ30分間隔で推定）
        actual_dt = get_race_start_time(jcd, date, race_no)
        if actual_dt:
            return actual_dt
        return r1_dt + datetime.timedelta(minutes=30 * (race_no - 1))
    race_dt = get_race_start_time(jcd, date, race_no)
    if race_dt:
        return race_dt
    return datetime.datetime.strptime(date, "%Y%m%d") + datetime.timedelta(days=1, hours=6)


def register_exhibition_tasks(jcd: str, date: str, races: list[int],
                               r1_time_str: str = ""):
    """
    展示タスクを一括登録。
    fetch_at  = 発走10分前（v5.22: 15→10）
    next_try  = 失敗時の5分後（=発走5分前で再試行）
    deadline  = 発走時刻（過ぎたら削除）
    最大試行 = MAX_RETRY_COUNT 回（達したら deadline 待たず削除）
    福岡(22)は exhibition 取得時に同時にオリジナル展示も取得される。
    r1_time_str: R1の発走時刻 "HH:MM"（省略時はWebから取得）
    """
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for race_no in races:
        # 既に有効な展示データがある場合はスキップ
        # ※ exhibition_time が float として読める値を持つ場合のみ「取得済み」と判断
        ex_path = DATA_DIR / "raw" / date / f"{jcd}_R{race_no:02d}_exhibition.json"
        if ex_path.exists():
            with open(ex_path, encoding="utf-8") as f:
                ex = json.load(f)
            records = ex.get("exhibition", [])
            try:
                valid = any(float(r.get("exhibition_time", "")) > 0 for r in records)
            except (ValueError, TypeError):
                valid = False
            if valid:
                continue

        race_dt    = _resolve_race_dt(jcd, date, race_no, r1_time_str)
        fetch_at   = race_dt - datetime.timedelta(minutes=EXHIBITION_FETCH_LEAD_MIN)

        task = {
            "id":         f"exhibition_{jcd}_{date}_R{race_no:02d}",
            "type":       "exhibition",
            "jcd":        jcd,
            "date":       date,
            "race_no":    race_no,
            "fetch_at":   fetch_at.strftime("%Y-%m-%dT%H:%M:00"),
            "deadline":   race_dt.strftime("%Y-%m-%dT%H:%M:00"),
            "created_at": now_str,
            "retry_count": 0,
        }
        add_task(task)


def register_odds_tasks(jcd: str, date: str, races: list[int],
                        r1_time_str: str = ""):
    """
    オッズタスクを一括登録。
    fetch_at  = 発走10分前（v5.22: 15→10）
    next_try  = 失敗時の5分後（=発走5分前で再試行）
    deadline  = 発走時刻
    最大試行 = MAX_RETRY_COUNT 回
    r1_time_str: R1の発走時刻 "HH:MM"（省略時はWebから取得）
    """
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for race_no in races:
        # 既にオッズデータがある場合はスキップ
        odds_path = DATA_DIR / "odds" / date / f"{jcd}_R{race_no:02d}.json"
        if odds_path.exists():
            with open(odds_path, encoding="utf-8") as f:
                od = json.load(f)
            if od.get("odds_3t"):
                continue

        race_dt    = _resolve_race_dt(jcd, date, race_no, r1_time_str)
        fetch_at   = race_dt - datetime.timedelta(minutes=ODDS_FETCH_LEAD_MIN)

        task = {
            "id":         f"odds_{jcd}_{date}_R{race_no:02d}",
            "type":       "odds",
            "jcd":        jcd,
            "date":       date,
            "race_no":    race_no,
            "fetch_at":   fetch_at.strftime("%Y-%m-%dT%H:%M:00"),
            "deadline":   race_dt.strftime("%Y-%m-%dT%H:%M:00"),
            "created_at": now_str,
            "retry_count": 0,
        }
        add_task(task)


def register_results_task(jcd: str, date: str, deadline_str: str = ""):
    """結果CSVタスクを登録（期限省略時は翌日昼12時）"""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if deadline_str:
        deadline = datetime.datetime.strptime(deadline_str, "%Y%m%d %H:%M")
    else:
        deadline = datetime.datetime.strptime(date, "%Y%m%d") + datetime.timedelta(days=1, hours=12)

    task = {
        "id":         f"results_{jcd}_{date}",
        "type":       "results",
        "jcd":        jcd,
        "date":       date,
        "race_no":    "all",
        "deadline":   deadline.strftime("%Y-%m-%dT%H:%M:00"),
        "created_at": now_str,
    }
    add_task(task)


# ── 依頼キュー処理 ────────────────────────────────────────────────

def load_fetch_requests() -> list[dict]:
    """fetch_requests.json から依頼一覧を読み出す。

    受け付ける形式:
      {"requests": [{"jcd":"22","date":"20260503","r1_start":"10:30","races":[1..12]}, ...]}
      または top-level list でも可。
    """
    if not FETCH_REQUESTS_FILE.exists():
        return []
    try:
        with open(FETCH_REQUESTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] fetch_requests.json 読み込み失敗（無視して続行）: {e}")
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("requests", []) or []
    return []


def save_fetch_requests(requests: list[dict]):
    """残った依頼を書き戻す（dict 形式で統一）。"""
    DATA_DIR.mkdir(exist_ok=True)
    with open(FETCH_REQUESTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"requests": requests}, f, ensure_ascii=False, indent=2)


def process_fetch_requests() -> int:
    """依頼キューを読んで pending タスク（exhibition + odds）に変換する。

    依頼スキーマ:
      jcd      : str  (必須)  会場コード "01"〜"24"
      date     : str  (必須)  "YYYYMMDD"
      r1_start : str  (任意)  "HH:MM"。省略時はWebからR1発走時刻を取得。
      races    : list (任意)  対象レース番号。省略時は [1..12] 全レース。

    処理した依頼はファイルから削除する。失敗した依頼は残して次回再試行。
    福岡(22) はオリジナル展示も exhibition タスク内で同時取得される。

    戻り値: 処理した依頼数
    """
    requests = load_fetch_requests()
    if not requests:
        return 0

    print(f"\n  📨 依頼キュー処理: {len(requests)}件 ({FETCH_REQUESTS_FILE.name})")

    remaining: list[dict] = []
    processed = 0
    for req in requests:
        jcd = str(req.get("jcd", "")).strip()
        date = str(req.get("date", "")).strip()
        if not jcd or not date:
            print(f"  [WARN] 不正な依頼（jcd/date 欠如）→ 破棄: {req}")
            continue
        r1_start = str(req.get("r1_start", "")).strip()
        races = req.get("races") or list(range(1, 13))
        try:
            races = [int(r) for r in races]
        except (TypeError, ValueError):
            print(f"  [WARN] races が不正 → 破棄: {req}")
            continue

        vname = VENUE_NAMES.get(jcd, jcd)
        race_label = f"R{min(races)}〜R{max(races)}" if len(races) > 1 else f"R{races[0]}"
        try:
            print(f"  → {vname}({jcd}) {date} {race_label} 展示+オッズ登録 (R1={r1_start or 'auto'})")
            register_exhibition_tasks(jcd, date, races, r1_start)
            register_odds_tasks(jcd, date, races, r1_start)
            processed += 1
        except Exception as e:
            print(f"  [ERROR] 依頼処理失敗（残して次回再試行）: {jcd} {date}: {e}")
            remaining.append(req)

    save_fetch_requests(remaining)
    print(f"  ✓ 処理 {processed}件 / 残 {len(remaining)}件\n")
    return processed


def register_verify_task(jcd: str, date: str, deadline_str: str = ""):
    """照合タスクを登録（期限省略時は翌日昼12時）"""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if deadline_str:
        deadline = datetime.datetime.strptime(deadline_str, "%Y%m%d %H:%M")
    else:
        deadline = datetime.datetime.strptime(date, "%Y%m%d") + datetime.timedelta(days=1, hours=12)

    task = {
        "id":         f"verify_{jcd}_{date}",
        "type":       "verify",
        "jcd":        jcd,
        "date":       date,
        "race_no":    "all",
        "deadline":   deadline.strftime("%Y-%m-%dT%H:%M:00"),
        "created_at": now_str,
    }
    add_task(task)


# ── エントリーポイント ────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="積み残しタスク管理")
    parser.add_argument("--list",  action="store_true", help="タスク一覧を表示")
    parser.add_argument("--run",   action="store_true", help="全タスクを実行（デフォルト）")
    parser.add_argument("--quiet", action="store_true", help="積み残し 0件 or 実行可能タスクなし のとき標準出力を抑制（cron ポーリング用）")
    parser.add_argument("--jcd", action="append", metavar="JCD", help="指定会場のみ実行（例: --jcd 22 --jcd 23）。複数指定可。未指定は全会場")
    parser.add_argument("--add-exhibition", nargs="+", metavar="JCD DATE [HH:MM]",
                        help="展示タスクを登録（発走10分前に自動取得）: --add-exhibition 19 20260316 [R1発走HH:MM]")
    parser.add_argument("--add-odds",      nargs="+", metavar="JCD DATE [HH:MM]",
                        help="オッズタスクを登録（発走10分前に自動取得）: --add-odds 19 20260316 [R1発走HH:MM]")
    parser.add_argument("--add-results",  nargs=2, metavar=("JCD", "DATE"),
                        help="結果タスクを登録: --add-results 19 20260316")
    parser.add_argument("--add-verify",   nargs=2, metavar=("JCD", "DATE"),
                        help="照合タスクを登録: --add-verify 19 20260316")
    parser.add_argument("--process-requests", action="store_true",
                        help="依頼キュー(fetch_requests.json)だけ処理して終了")
    parser.add_argument("--add-request", nargs="+", metavar="JCD DATE [HH:MM]",
                        help="依頼を fetch_requests.json に追加: --add-request 22 20260503 [10:30]")
    parser.add_argument("--report-success", metavar="FILE",
                        help="exhibition/odds 取得成功の (jcd, date) を TSV で FILE に書き出す（fetch_pending.yml 用）")
    args = parser.parse_args()

    if args.add_request:
        jcd  = args.add_request[0]
        date = args.add_request[1]
        r1t  = args.add_request[2] if len(args.add_request) > 2 else ""
        existing = load_fetch_requests()
        new_req = {"jcd": jcd, "date": date}
        if r1t:
            new_req["r1_start"] = r1t
        new_req["requested_at"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:00")
        # 同一 jcd+date があれば上書き（最新の依頼を優先）
        existing = [r for r in existing if not (r.get("jcd") == jcd and r.get("date") == date)]
        existing.append(new_req)
        save_fetch_requests(existing)
        print(f"  ➕ 依頼登録: {VENUE_NAMES.get(jcd, jcd)}({jcd}) {date} R1={r1t or 'auto'} → fetch_requests.json")
    elif args.process_requests:
        process_fetch_requests()
    elif args.add_exhibition:
        jcd  = args.add_exhibition[0]
        date = args.add_exhibition[1]
        r1t  = args.add_exhibition[2] if len(args.add_exhibition) > 2 else ""
        register_exhibition_tasks(jcd, date, list(range(1, 13)), r1t)
    elif args.add_odds:
        jcd  = args.add_odds[0]
        date = args.add_odds[1]
        r1t  = args.add_odds[2] if len(args.add_odds) > 2 else ""
        register_odds_tasks(jcd, date, list(range(1, 13)), r1t)
    elif args.add_results:
        register_results_task(args.add_results[0], args.add_results[1])
    elif args.add_verify:
        register_verify_task(args.add_verify[0], args.add_verify[1])
    elif args.list:
        tasks = load_tasks()
        if not tasks:
            print("積み残しタスクなし。")
        else:
            print(f"\n{'─'*60}")
            for t in sorted(tasks, key=lambda x: x.get("deadline","")):
                vname = VENUE_NAMES.get(t.get("jcd",""), "-")
                print(f"  [{t['id']}]  {t['type']}  {vname}  "
                      f"R{t.get('race_no','-')}  期限={t['deadline']}")
            print(f"{'─'*60}")
    else:
        globals()["QUIET"] = bool(args.quiet)
        run_all(jcd_filter=args.jcd, success_report_file=args.report_success)
