#!/usr/bin/env python3
"""
前日 verify 自動実行スクリプト
===============================
朝のスケジュールタスクから呼ばれ、前日（または指定日）の
全予測対象会場の結果を取得して verify を実行する。

処理フロー:
  1. 対象日の data/logs/{date}/ を検索し、予測済み JCD を列挙
  2. 並列リクエストで boatrace.jp から全レース結果を取得
  3. results_csv/{date}.csv に追記（--replace で既存行を置換）
  4. 各 JCD について verify.py を実行
  5. verify_history.json / verify_log.html を更新

使い方:
  # 昨日分（デフォルト）
  python3 scripts/morning_verify.py

  # 日付を指定
  python3 scripts/morning_verify.py --date 20260323

  # 結果CSV取得のみ（verify実行しない）
  python3 scripts/morning_verify.py --fetch-only

  # verify実行のみ（結果CSVは既存を使う）
  python3 scripts/morning_verify.py --verify-only
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import json
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR     = Path(__file__).parent.parent
DATA_DIR     = BASE_DIR / "data"
LOG_DIR      = DATA_DIR / "logs"
CSV_DIR      = DATA_DIR / "results_csv"
SCRIPTS_DIR  = BASE_DIR / "scripts"
PENDING_FILE = DATA_DIR / "pending_tasks.json"

# fetch_results_official のユーティリティを再利用
sys.path.insert(0, str(SCRIPTS_DIR))
from fetch_results_official import (
    parse_result_page,
    write_day_csv,
    JCD_TO_VENUE,
    RACERESULT_URL,
    RESULTLIST_URL,
)

MAX_WORKERS  = 8    # 並列リクエスト数
REQ_TIMEOUT  = 30   # 1リクエストあたりのタイムアウト（秒）


def yesterday() -> str:
    return (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")


def cleanup_old_pending_tasks() -> None:
    """pending_tasks.json から前日以前の積み残しを削除する。

    morning 定期タスクの先頭で呼ばれる。本日以降の date を持つタスクだけを残し、
    それ以前のタスクは deadline 有無にかかわらず一律で破棄する。
    """
    if not PENDING_FILE.exists():
        return
    try:
        with open(PENDING_FILE, encoding="utf-8") as f:
            tasks = json.load(f)
    except Exception as e:
        print(f"  [WARN] pending_tasks.json 読込失敗: {e}")
        return

    today_str = datetime.date.today().strftime("%Y%m%d")
    keep, dropped = [], []
    for t in tasks:
        d = str(t.get("date", ""))
        if d and d < today_str:
            dropped.append(t.get("id", "?"))
        else:
            keep.append(t)

    if not dropped:
        print(f"  積み残しクリーンアップ: 削除対象なし（残 {len(keep)}件）")
        return

    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(keep, f, ensure_ascii=False, indent=2)

    # output/pending_tasks.md も同時更新（run_pending の _update_md を再利用）
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        import run_pending as rp_mod
        rp_mod._update_md(keep)
    except Exception as e:
        print(f"  [WARN] pending_tasks.md 更新失敗: {e}")

    print(f"  積み残しクリーンアップ: {len(dropped)}件削除 / 残 {len(keep)}件")
    for tid in dropped[:10]:
        print(f"    - {tid}")
    if len(dropped) > 10:
        print(f"    ... 他 {len(dropped) - 10}件")


def publish_review_to_wordpress(jcd: str, date_str: str) -> None:
    """verify 完了後に review_summary 入り payload を WordPress へ再送信する。

    WP_SYNC_URL / WP_SYNC_TOKEN が未設定ならスキップ。送信失敗は警告扱いで verify 結果には影響させない。
    run_pending.py の同名ヘルパーと同じ挙動。
    """
    sync_url = os.getenv("WP_SYNC_URL", "")
    token    = os.getenv("WP_SYNC_TOKEN", "")
    if not sync_url or not token:
        print("  [WP] WP_SYNC_URL / WP_SYNC_TOKEN 未設定 → WordPress 再送信スキップ")
        return
    try:
        import importlib
        sys.path.insert(0, str(SCRIPTS_DIR))
        import publish_wordpress as pw_mod
        importlib.reload(pw_mod)
        timeout  = float(os.getenv("WP_SYNC_TIMEOUT", "10"))
        payload  = pw_mod.build_request_payload(jcd, date_str)
        pw_mod.write_payload_file(jcd, date_str, payload)
        response = pw_mod.publish_payload(payload, sync_url, token, timeout)
        post_id  = response.get("id", "?")
        print(f"  [WP] 振り返り反映完了 jcd={jcd} (post_id={post_id})")
    except Exception as e:
        print(f"  [WP] WordPress 再送信失敗 jcd={jcd}（verify 結果は保存済み）: {e}")


def find_predicted_jcds(date_str: str) -> list[str]:
    """data/logs/{date}/ の pred.json から予測済み JCD を返す"""
    day_dir = LOG_DIR / date_str
    if not day_dir.exists():
        return []
    jcds = sorted({f.name.split("_")[0] for f in day_dir.glob("*_pred.json")})
    return jcds


def fetch_race_result(session: requests.Session, jcd: str, race_no: int, date_str: str):
    url = RACERESULT_URL.format(date=date_str, jcd=jcd, rno=race_no)
    r = session.get(url, timeout=REQ_TIMEOUT)
    rows = parse_result_page(r.text, date_str, jcd, race_no)
    return jcd, race_no, rows


def fetch_results_parallel(date_str: str, jcds: list[str]) -> dict[str, list]:
    """全 JCD × 全レースを並列取得。{jcd: [rows]} を返す"""
    session = requests.Session()

    # タスクリストを構築（全 JCD × R1〜R12）
    tasks = [(jcd, rno) for jcd in jcds for rno in range(1, 13)]
    print(f"  {len(tasks)} リクエストを並列取得（workers={MAX_WORKERS}）")

    all_rows: dict[str, list] = {jcd: [] for jcd in jcds}
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(fetch_race_result, session, jcd, rno, date_str): (jcd, rno)
            for jcd, rno in tasks
        }
        for fut in as_completed(futures):
            jcd, rno = futures[fut]
            try:
                _, _, rows = fut.result()
                all_rows[jcd].extend(rows)
                done += 1
                venue = JCD_TO_VENUE.get(jcd, jcd)
                if rows:
                    print(f"    [{done:2d}/{len(tasks)}] {venue}(JCD:{jcd}) R{rno:2d} → {len(rows)}行")
                else:
                    print(f"    [{done:2d}/{len(tasks)}] {venue}(JCD:{jcd}) R{rno:2d} → データなし")
            except Exception as e:
                done += 1
                print(f"    [{done:2d}/{len(tasks)}] JCD:{jcd} R{rno} → エラー: {e}")

    return all_rows


def save_results_csv(date_str: str, all_rows: dict[str, list]) -> list[str]:
    """結果を CSV に保存。成功した JCD リストを返す"""
    saved = []
    for jcd, rows in all_rows.items():
        venue = JCD_TO_VENUE.get(jcd, jcd)
        if rows:
            path = write_day_csv(date_str, jcd, rows, replace=True)
            print(f"  ✓ {venue}({jcd})  {len(rows)}行 → {path.name}")
            saved.append(jcd)
        else:
            print(f"  ✗ {venue}({jcd})  結果なし（当日開催なし or データ未公開）")
    return saved


def run_verify(date_str: str, jcds: list[str]):
    """各 JCD について verify.py を実行し、成功した JCD は WordPress へ振り返りを再送信する"""
    for jcd in jcds:
        venue = JCD_TO_VENUE.get(jcd, jcd)
        print(f"\n  --- verify: {venue}({jcd}) {date_str} ---")
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "verify.py"),
            "--jcd", jcd,
            "--from", date_str,
            "--to",   date_str,
        ]
        result = subprocess.run(cmd, capture_output=False, text=True, cwd=str(BASE_DIR))
        if result.returncode != 0:
            print(f"  [WARN] verify.py が異常終了 (exit={result.returncode})")
            continue
        publish_review_to_wordpress(jcd, date_str)


def main():
    ap = argparse.ArgumentParser(description="前日 verify 自動実行")
    ap.add_argument("--date",        default=None, help="対象日 YYYYMMDD（デフォルト: 昨日）")
    ap.add_argument("--fetch-only",  action="store_true", help="結果CSV取得のみ（verify なし）")
    ap.add_argument("--verify-only", action="store_true", help="verify のみ（結果取得なし）")
    args = ap.parse_args()

    date_str = args.date or yesterday()
    print(f"\n{'='*60}")
    print(f"  前日 verify 実行: {date_str}")
    print(f"{'='*60}")

    # 前日以前の積み残しタスクを一括削除（morning 定期タスクのクリーンアップ）
    print(f"\n【pending_tasks クリーンアップ】")
    cleanup_old_pending_tasks()

    # 予測済み JCD を特定
    jcds = find_predicted_jcds(date_str)
    if not jcds:
        print(f"  data/logs/{date_str}/ に予測ログなし。終了します。")
        return

    venues = [f"{JCD_TO_VENUE.get(j, j)}({j})" for j in jcds]
    print(f"  対象会場: {', '.join(venues)}")

    # ① 結果取得
    if not args.verify_only:
        print(f"\n【結果取得】{date_str}")
        all_rows = fetch_results_parallel(date_str, jcds)
        saved_jcds = save_results_csv(date_str, all_rows)
    else:
        # verify-only の場合は CSV 既存前提で全 JCD を対象にする
        saved_jcds = jcds

    # ② verify 実行
    if not args.fetch_only:
        print(f"\n【verify 実行】{date_str}")
        run_verify(date_str, saved_jcds)

    print(f"\n{'='*60}")
    print(f"  完了: {date_str}  対象={len(saved_jcds)} 会場")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
