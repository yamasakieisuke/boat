"""毎朝バッチ統合実行 (v5.23)

SKILL.md `boat-daily-morning-v2` の STEP 0〜5 を1コマンドで完結。
Claude のターン消費を抑えるため、会場選択ロジックも Python 側に寄せている。
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

BOAT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOAT_DIR))

import scripts.scraper as sc

MAX_VENUES = 24

GRADE_ORDER = {"SG": 0, "PG1": 1, "G1": 2, "G2": 3, "G3": 4}

PRIORITY_ORDER = [
    "22", "24", "23", "19", "21", "07",
    "20",
    "01", "15", "12", "13",
    "10",
]

# 展示/オッズの polling 対象（fetch_pending.yml が読み込む fetch_requests.json に登録される）
WATCH_VENUES_ALWAYS = {"22", "24"}  # 福岡（オリジナル展示あり）, 大村
WATCH_GRADES = {"SG", "PG1", "G1", "G2", "G3"}
WATCH_CLASSES = {"lady", "ladies", "venus"}  # オールレディース系（boatrace.jp の is-* クラス）

INDEX_URL = "https://www.boatrace.jp/owpc/pc/race/index"


def fetch_active_venues(date_str: str) -> list[dict]:
    """boatrace.jp トップから開催会場+グレードを返す。

    返り値: [{"jcd": "22", "grade": "G2" | "ippan" | None}, ...]
    """
    html = sc.fetch(INDEX_URL, params={"hd": date_str}, wait=0.5)
    place_re = re.compile(r"text_place1_(\d{2})\.png")
    class_re = re.compile(
        r'class="(is-(?:SG|PG1|G1|G2|G3|ippan|lady|rookie[\w_]*|venus|sport|memorial)[\w]*?)\s'
    )
    places = list(place_re.finditer(html))
    venues: list[dict] = []
    for i, m in enumerate(places):
        jcd = m.group(1)
        start = m.end()
        end = places[i + 1].start() if i + 1 < len(places) else len(html)
        cm = class_re.search(html, start, end)
        grade_raw = cm.group(1).replace("is-", "").rstrip("b") if cm else None
        grade = grade_raw if grade_raw in GRADE_ORDER else grade_raw
        venues.append({"jcd": jcd, "grade": grade})
    # 重複 jcd は最初の出現を採用
    seen: set[str] = set()
    uniq: list[dict] = []
    for v in venues:
        if v["jcd"] in seen:
            continue
        seen.add(v["jcd"])
        uniq.append(v)
    return uniq


def select_venues(active: list[dict]) -> list[str]:
    """高グレード → PRIORITY_ORDER → 残りの順で最大 MAX_VENUES 会場選択。"""
    graded = [v for v in active if v["grade"] in GRADE_ORDER]
    graded.sort(key=lambda v: GRADE_ORDER[v["grade"]])
    selected = [v["jcd"] for v in graded][:MAX_VENUES]

    active_set = {v["jcd"] for v in active}
    for jcd in PRIORITY_ORDER:
        if len(selected) >= MAX_VENUES:
            break
        if jcd in active_set and jcd not in selected:
            selected.append(jcd)

    for v in active:
        if len(selected) >= MAX_VENUES:
            break
        if v["jcd"] not in selected:
            selected.append(v["jcd"])
    return selected


def select_watch_venues(active: list[dict]) -> list[str]:
    """展示/オッズ polling の対象会場を返す。

    - WATCH_VENUES_ALWAYS（福岡・大村）を必ず含める（その日に開催している場合のみ）
    - グレード戦（SG/PG1/G1/G2/G3）開催会場を追加
    - オールレディース系（lady/ladies/venus クラス）開催会場を追加
    """
    active_jcds = {v["jcd"] for v in active}
    selected: set[str] = set(WATCH_VENUES_ALWAYS) & active_jcds
    for v in active:
        grade = v.get("grade")
        if grade in WATCH_GRADES or grade in WATCH_CLASSES:
            selected.add(v["jcd"])
    return sorted(selected)


def write_fetch_requests(date_str: str, watch_jcds: list[str]) -> None:
    """fetch_requests.json に watch 会場の依頼を書き込む（既存は上書き）。

    fetch_pending.yml がこのファイルを読んで pending_tasks に変換する。
    """
    from pathlib import Path as _Path
    data_dir = BOAT_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    path = data_dir / "fetch_requests.json"
    requested_at = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:00")
    requests = [
        {"jcd": jcd, "date": date_str, "requested_at": requested_at}
        for jcd in watch_jcds
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"requests": requests}, f, ensure_ascii=False, indent=2)
    print(f"[INFO] fetch_requests.json に {len(requests)}件登録: {watch_jcds}")


def run(cmd: list[str], **kwargs) -> int:
    """サブプロセス実行。終了コードを返す。"""
    print(f"[RUN] {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=BOAT_DIR, **kwargs).returncode


def process_venue(jcd: str, date_str: str) -> bool:
    """1会場の STEP 3-5。失敗時 False。"""
    try:
        races = list(range(1, 13))
        sc._run_parallel_race_jobs(
            [(r, lambda r=r: sc.scrape_racecard(jcd, date_str, r)) for r in races],
            label=f"出走表 {jcd} {date_str}",
        )
        sc._run_parallel_race_jobs(
            [(r, lambda r=r: sc.scrape_players_from_racecard(jcd, date_str, r)) for r in races],
            label=f"選手 {jcd} {date_str}",
        )
        sc._run_parallel_race_jobs(
            [(r, lambda r=r: sc.scrape_weather(jcd, date_str, r)) for r in races],
            label=f"気象 {jcd} {date_str}",
        )
        sc._run_parallel_race_jobs(
            [(r, lambda r=r: sc.scrape_comments(jcd, date_str, r)) for r in races],
            label=f"コメント {jcd} {date_str}",
        )
        rc = run(["python3", "scripts/fetch_tide.py", "--jcd", jcd, "--date", date_str])
        if rc != 0:
            print(f"[WARN] fetch_tide failed jcd={jcd} rc={rc}", file=sys.stderr)
        rc = run(["python3", "scripts/predictor.py", "--jcd", jcd, "--date", date_str, "--wp-publish"])
        if rc != 0:
            print(f"[ERROR] predictor failed jcd={jcd} rc={rc}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"[ERROR] jcd={jcd}: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="毎朝バッチ統合実行")
    parser.add_argument("--date", default=datetime.date.today().strftime("%Y%m%d"))
    parser.add_argument("--dry-run", action="store_true", help="会場選択結果のみ表示して終了")
    parser.add_argument("--skip-verify", action="store_true", help="STEP 0 (前日 verify) をスキップ")
    parser.add_argument("--jcd", help="特定会場のみ処理（STEP 1-2 スキップ）")
    parser.add_argument("--list-venues", action="store_true",
                        help="選択された会場一覧をJSONで stdout に出力して終了（GitHub Actions matrix 用）")
    parser.add_argument("--write-fetch-requests", action="store_true",
                        help="WATCH会場（福岡/大村+グレード+レディース）の依頼を fetch_requests.json に書き出して終了")
    args = parser.parse_args()

    date_str = args.date

    if args.list_venues:
        with contextlib.redirect_stdout(sys.stderr):
            active = fetch_active_venues(date_str)
            selected = select_venues(active)
        print(json.dumps(selected))
        return 0

    if args.write_fetch_requests:
        active = fetch_active_venues(date_str)
        print(f"[INFO] active venues ({len(active)}): "
              + ", ".join(f"{v['jcd']}({v['grade']})" for v in active))
        watch = select_watch_venues(active)
        print(f"[INFO] watch venues ({len(watch)}): {watch}")
        write_fetch_requests(date_str, watch)
        return 0

    if args.jcd:
        selected = [args.jcd]
        print(f"[INFO] single venue mode: {selected}")
    else:
        if not args.skip_verify:
            print("=== STEP 0: morning_verify ===")
            run(["python3", "scripts/morning_verify.py"])

        print(f"\n=== STEP 1-2: select venues for {date_str} ===")
        active = fetch_active_venues(date_str)
        print(f"[INFO] active venues ({len(active)}): "
              + ", ".join(f"{v['jcd']}({v['grade']})" for v in active))
        selected = select_venues(active)
        print(f"[INFO] selected ({len(selected)}): {selected}")

        if args.dry_run:
            return 0

    print(f"\n=== STEP 3-5: process {len(selected)} venues ===")
    failures: list[str] = []
    for jcd in selected:
        print(f"\n--- venue {jcd} ---")
        if not process_venue(jcd, date_str):
            failures.append(jcd)

    if failures:
        print(f"\n[FAIL] {len(failures)}/{len(selected)} venues failed: {failures}", file=sys.stderr)
        return 1
    print(f"\n[OK] {len(selected)} venues processed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
