#!/usr/bin/env python3
"""福岡オリジナル展示（一周/まわり足/直線）を過去に遡って取得する。

## なぜ要るか

公開データは全部オッズに織り込まれている（会場特性・レース番号・種別のどれも、
的中率は動かせても回収率の優位には繋がっていない）。福岡公式にしか無い
一周・まわり足・直線タイムは公式の標準展示とは別物で参照者も少なく、
**広く使われていないこのデータだけが残された情報優位**になりうる。

収集自体は fetch_pending.yml が毎日走らせて成功していたが、data/raw/ が
gitignore に飲まれて commit されず、別 runner の verify では存在しなかった。
その永続化は 2026-09-05 に直したので、以降は自動で溜まる。
本スクリプトは**それ以前の分**を埋める。

## 作法

- 相手は boatrace-fukuoka.com（第三者のサーバー）。既定は保守的に 2.0秒間隔
- 取得済みはスキップするので中断・再開できる
- `--until HH:MM` で夜間ウィンドウを自前で打ち切る
  （macOS に GNU の timeout が無く、外部コマンドに頼ると黙って死ぬ）
- 連続失敗が続いたら中断する（サーバー側の問題を叩き続けない）

使い方:
    python3 scripts/backfill_fukuoka_tenji.py --dry-run
    python3 scripts/backfill_fukuoka_tenji.py --limit 0 --sleep 2.0 --until 07:00
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import signal
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))
import scraper as sc  # noqa: E402

RAW_DIR = BASE_DIR / "data" / "raw"
DEFAULT_LIMIT = 50          # 既定は控えめ。全件は --limit 0 を明示したときだけ
DEFAULT_SLEEP = 2.0
# 開催日でもオリジナル展示が公開されない日がある（1日=12連続失敗になる）。
# 3日ぶん連続で空なら、さすがにサーバー側かURL仕様の変化を疑って止める。
DEFAULT_MAX_FAILURES = 36
# このサービスで実際にデータが載り始めた日。二分探索で確認（20250508=無 / 20250608=有）。
# これより前を叩いても必ず空が返るので、既定の開始日にする。
DATA_START = "20250608"

_interrupted = False


def _on_sigint(signum, frame):
    global _interrupted
    if _interrupted:
        sys.exit(130)
    _interrupted = True
    print("\n[INFO] 中断要求。現在のリクエスト完了後に停止する（もう一度で即時終了）",
          flush=True)


def fukuoka_days() -> list[str]:
    """results_csv から福岡の開催日を拾う。"""
    days = set()
    for p in sorted(glob.glob(str(BASE_DIR / "data/results_csv/2*.csv"))):
        if "results_all" in p:
            continue
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["venue_name"].strip() == "福岡":
                    days.add(r["date"])
                    break
    return sorted(days)


def is_done(date: str, race_no: int) -> bool:
    p = RAW_DIR / date / f"22_R{race_no:02d}_original_exhibition.json"
    return p.exists() and p.stat().st_size > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", default=DATA_START,
                    help=f"開始日 YYYYMMDD（既定 {DATA_START}＝データが載り始めた日）")
    ap.add_argument("--to", dest="date_to", default="")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="0で無制限")
    ap.add_argument("--sleep", type=float, default=DEFAULT_SLEEP)
    ap.add_argument("--until", default="", help="この時刻(HH:MM)で打ち切る")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-failures", type=int, default=DEFAULT_MAX_FAILURES)
    args = ap.parse_args()

    days = fukuoka_days()
    if args.date_from:
        days = [d for d in days if d >= args.date_from]
    if args.date_to:
        days = [d for d in days if d <= args.date_to]

    pending = [(d, r) for d in days for r in range(1, 13) if not is_done(d, r)]
    done = len(days) * 12 - len(pending)
    print(f"福岡の開催日 {len(days)}日 / 全 {len(days)*12:,}レース")
    print(f"  取得済み（スキップ）: {done:,}")
    print(f"  これから取得        : {len(pending):,}")
    if args.limit:
        pending = pending[:args.limit]
        print(f"  今回の上限          : {args.limit}")
    if not pending:
        print("すべて取得済み")
        return 0
    est = len(pending) * (args.sleep + 0.8)
    print(f"  見積り              : 約{est/60:.0f}分（{args.sleep}秒間隔）")
    if args.dry_run:
        print(f"  最初: {pending[0]} / 最後: {pending[-1]}")
        return 0

    until = None
    if args.until:
        hh, mm = args.until.split(":")
        until = datetime.time(int(hh), int(mm))

    signal.signal(signal.SIGINT, _on_sigint)
    ok = fail = 0
    consecutive = 0
    started = time.time()
    for i, (d, r) in enumerate(pending, 1):
        if _interrupted:
            print("[INFO] 中断した。再実行すれば続きから走る")
            break
        if until is not None and datetime.datetime.now().time() >= until:
            print(f"[INFO] 停止時刻 {until.strftime('%H:%M')} に達したので終了する")
            break
        if i > 1:
            time.sleep(args.sleep)
        try:
            res = sc.scrape_fukuoka_original_exhibition(d, r)
        except Exception as e:  # noqa: BLE001 1件の失敗で全体を止めない
            print(f"[ERROR] {d} R{r}: {e}")
            res = None
        if res:
            ok += 1
            consecutive = 0
        else:
            fail += 1
            consecutive += 1
            if consecutive >= args.max_failures:
                print(f"[ABORT] 連続{args.max_failures}件失敗。"
                      "サーバー側の問題の可能性が高いので中断する")
                break
        if i % 60 == 0:
            per = (time.time() - started) / i
            print(f"[PROGRESS] {i}/{len(pending)} 成功{ok} 失敗{fail} "
                  f"平均{per:.1f}s/件 残り約{(len(pending)-i)*per/3600:.1f}h", flush=True)

    print(f"\n完了: 成功 {ok} / 失敗 {fail} / 経過 {(time.time()-started)/60:.1f}分")
    return 0


if __name__ == "__main__":
    sys.exit(main())
