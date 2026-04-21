#!/usr/bin/env python3
"""
レース当日自動実行スクリプト v1.0
──────────────────────────────────────────────────────────────
このスクリプトを1回実行するだけで、以下を自動で行います:

  [朝の準備]
  1. 気象庁から潮汐データを取得 (fetch_tide.py)
  2. 出走表を取得 (scraper.py)
  3. 選手コメントを取得 (scraper.py)
  4. 初期予測を生成・保存 (predictor.py)

  [レース直前（各レースの30分前）]
  5. 展示タイム・展示STを取得 (scraper.py)
  6. 当日オッズを取得 (scraper.py)
  7. 予測を展示データ込みで更新・保存

実行例:
  # 今日の福岡 全レース（10:00〜18:00 に自動で動く）
  python3 scripts/run_race_day.py --jcd 22

  # 特定日・特定レースから
  python3 scripts/run_race_day.py --jcd 22 --date 20260315 --from-race 5

  # 朝の準備だけ（展示ループはしない）
  python3 scripts/run_race_day.py --jcd 22 --setup-only
──────────────────────────────────────────────────────────────
"""

import subprocess
import datetime
import time
import json
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SCRIPTS  = BASE_DIR / "scripts"

# デフォルトレース開始時刻（分単位、0時からの経過分）
DEFAULT_RACE_START_TIMES = {
    1:  10*60,      # 10:00
    2:  10*60+45,   # 10:45
    3:  11*60+30,   # 11:30
    4:  12*60+15,   # 12:15
    5:  13*60,      # 13:00
    6:  13*60+45,   # 13:45
    7:  14*60+30,   # 14:30
    8:  15*60+15,   # 15:15
    9:  16*60,      # 16:00
    10: 16*60+45,   # 16:45
    11: 17*60+30,   # 17:30
    12: 18*60+15,   # 18:15
}

EXHIBITION_LEAD_MIN = 20   # 展示データはレース開始の何分前に取得するか
CHECK_INTERVAL_SEC  = 60   # メインループの確認間隔（秒）


def run(cmd: list, desc: str):
    """コマンドを実行してエラー時はログを表示"""
    print(f"\n[RUN] {desc}")
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        print(f"[WARN] exit={result.returncode}")
        if result.stderr:
            print(result.stderr.rstrip()[:300])
    return result.returncode == 0


def now_min():
    """現在時刻を「0時からの経過分」で返す"""
    now = datetime.datetime.now()
    return now.hour * 60 + now.minute


def setup_morning(jcd: str, date: str):
    """朝の準備: 潮汐・出走表・コメント・初期予測"""
    print(f"\n{'='*60}")
    print(f"  🌅 朝の準備開始  {jcd} {date}")
    print(f"{'='*60}")

    # 1. 潮汐データ取得
    run([
        "python3", SCRIPTS/"fetch_tide.py",
        "--jcd", jcd, "--date", date
    ], "潮汐データ取得（気象庁）")

    # 2. 全レース出走表取得
    for race_no in range(1, 13):
        run([
            "python3", SCRIPTS/"scraper.py",
            "--mode", "racecard",
            "--jcd", jcd, "--date", date, "--race", str(race_no)
        ], f"出走表取得 R{race_no}")
        time.sleep(1.5)

    # 3. 選手コメント取得（対応会場のみ）
    run([
        "python3", SCRIPTS/"scraper.py",
        "--mode", "comments",
        "--jcd", jcd, "--date", date
    ], "選手コメント取得")

    # 4. 初期予測生成（展示なし）
    run([
        "python3", SCRIPTS/"predictor.py",
        "--jcd", jcd, "--date", date
    ], "初期予測生成")

    print(f"\n  ✅ 朝の準備完了。展示データ取得ループを開始します。")


def fetch_exhibition_and_predict(jcd: str, date: str, race_no: int):
    """
    1レース分の展示取得 + 全レース予測ファイル再生成。

    ※ predictor.py を「全レース」で実行することで、出力ファイル(output/xxx.txt)が
    常に最新の展示データを含む完全な状態に更新される。
    展示取得済みのレースはそのデータを使用し、未取得レースは中立値(0.5)を維持。
    """
    print(f"\n{'─'*50}")
    print(f"  🏁 R{race_no} 展示データ取得 ({datetime.datetime.now().strftime('%H:%M:%S')})")
    print(f"{'─'*50}")

    # 展示タイム取得
    run([
        "python3", SCRIPTS/"scraper.py",
        "--mode", "exhibition",
        "--jcd", jcd, "--date", date, "--race", str(race_no)
    ], f"展示データ取得 R{race_no}")

    # オッズ取得
    run([
        "python3", SCRIPTS/"scraper.py",
        "--mode", "odds",
        "--jcd", jcd, "--date", date, "--race", str(race_no)
    ], f"オッズ取得 R{race_no}")

    # 予測ファイルを全レース分で再生成
    # → output/{venue}_{date}.txt が常に12レース全体の最新状態になる
    run([
        "python3", SCRIPTS/"predictor.py",
        "--jcd", jcd, "--date", date
        # --race 指定なし = 全レース再生成
    ], f"出力ファイル全体更新 (R{race_no}展示データ反映)")


def run_exhibition_loop(jcd: str, date: str, from_race: int = 1):
    """
    レース直前に展示データを自動取得するループ。
    各レースの `EXHIBITION_LEAD_MIN` 分前に実行する。
    """
    print(f"\n  ⏱  展示取得ループ開始 (R{from_race}〜R12, 各レース{EXHIBITION_LEAD_MIN}分前に自動取得)")

    fetched = set()  # 取得済みレース番号

    while True:
        cur_min = now_min()

        for race_no in range(from_race, 13):
            if race_no in fetched:
                continue
            race_start = DEFAULT_RACE_START_TIMES.get(race_no, 0)
            fetch_at   = race_start - EXHIBITION_LEAD_MIN

            if cur_min >= fetch_at and cur_min < race_start + 15:
                fetch_exhibition_and_predict(jcd, date, race_no)
                fetched.add(race_no)
                break  # 1周につき1レースだけ処理

        # 全レース完了したら終了
        if len(fetched) >= (13 - from_race):
            print(f"\n  ✅ 全レースの展示取得完了。ループ終了。")
            break

        # 当日分が全部終わった場合（最終レース開始+60分後）
        last_start = DEFAULT_RACE_START_TIMES.get(12, 18*60+15)
        if cur_min > last_start + 60:
            print(f"\n  ✅ 当日レース終了。ループ終了。")
            break

        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="レース当日自動実行スクリプト")
    parser.add_argument("--jcd",        default="22",
                        help="会場コード (デフォルト: 22=福岡)")
    parser.add_argument("--date",       default=datetime.date.today().strftime("%Y%m%d"),
                        help="開催日 YYYYMMDD (デフォルト: 今日)")
    parser.add_argument("--from-race",  dest="from_race", type=int, default=1,
                        help="展示ループ開始レース番号 (デフォルト: 1)")
    parser.add_argument("--setup-only", action="store_true",
                        help="朝の準備だけ実行し、展示ループはしない")
    args = parser.parse_args()

    print(f"🚤 ボートレース当日自動実行  {args.jcd}  {args.date}")

    setup_morning(args.jcd, args.date)

    if not args.setup_only:
        run_exhibition_loop(args.jcd, args.date, from_race=args.from_race)
