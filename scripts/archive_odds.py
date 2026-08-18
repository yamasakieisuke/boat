#!/usr/bin/env python3
"""その日の全レースの3連単オッズを1ファイルにまとめて保存する。

## なぜ必要か

2026-08-18 までの分析で「公開データで観測できることは全部オッズに織り込まれている」
ことが繰り返し確認された（会場特性: 1コース1着率と配当の相関 -0.78 / 回収率との相関
+0.02、頭の入れ替え: 1号艇頭77.8% vs 2号艇頭78.0%）。

つまり回収率を動かすには「市場がどう値付けしたか」を持っていないと始まらない。
ところが賭け時点のオッズは749Rぶんしか残っておらず、市場の歪みを探す土台がない。

## なぜ夜1回なのか

オッズページは当日〜数日しか遡れない（実測: 前日は取得可、7日前は0通り）。
一方でレース発走後のオッズは確定値なので、**全レース終了後にまとめて取れば
タイミング制御が不要**になる。発走は最も遅い会場でも20:50頃なので21:30に実行する。

## 保存形式

data/odds_archive/{date}.json.gz に1日分をまとめる。1レース約666B（最小化+gzip）、
1日200レースで約130KB、年間46MB。レースごとにファイルを作ると git が肥大するため
日単位でまとめる。
"""
from __future__ import annotations

import sys
import gzip
import json
import time
import argparse
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
OUT_DIR = BASE_DIR / "data" / "odds_archive"
sys.path.insert(0, str(Path(__file__).parent))


def load_day(date_str: str) -> dict:
    path = OUT_DIR / f"{date_str}.json.gz"
    if not path.exists():
        return {}
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_day(date_str: str, data: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{date_str}.json.gz"
    # mtime=0 で内容が同じなら gz のバイト列も同じになる（無意味な差分を出さない）
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(path, "wb"), mtime=0) as gz:
        gz.write(json.dumps(data, ensure_ascii=False,
                            separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="対象日 YYYYMMDD（既定: 今日 JST）")
    ap.add_argument("--sleep", type=float, default=1.5, help="1リクエストごとの追加待機秒")
    ap.add_argument("--jcd", default="", help="会場を絞る（カンマ区切り）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    date_str = args.date or datetime.datetime.now().strftime("%Y%m%d")

    import contextlib
    import run_morning as rm
    import scraper as sc

    with contextlib.redirect_stdout(sys.stderr):
        active = rm.fetch_active_venues(date_str)
    jcds = [v["jcd"] for v in active]
    if args.jcd:
        want = {x.strip() for x in args.jcd.split(",") if x.strip()}
        jcds = [j for j in jcds if j in want]

    data = load_day(date_str)
    todo = [(j, r) for j in jcds for r in range(1, 13) if f"{j}_{r}" not in data]
    print(f"{date_str}: 開催{len(jcds)}会場 / 取得済み{len(data)}レース / これから{len(todo)}レース")
    if args.dry_run:
        return 0
    if not todo:
        print("取得対象なし")
        return 0

    ok = miss = 0
    for i, (jcd, rno) in enumerate(todo, 1):
        try:
            with contextlib.redirect_stdout(sys.stderr):
                o = sc.scrape_odds(jcd, date_str, rno)
        except Exception as e:
            print(f"  [ERR] {jcd} R{rno}: {e}")
            o = None
        odds = (o or {}).get("odds_3t") or {}
        if odds:
            # 値は float。キーは "123" 形式の3桁
            data[f"{jcd}_{rno}"] = odds
            ok += 1
        else:
            miss += 1
        if i % 20 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] 取得{ok} / 空{miss}")
            save_day(date_str, data)   # 途中で落ちても失わない
        time.sleep(args.sleep)

    path = save_day(date_str, data)
    size = path.stat().st_size
    print(f"保存: {path}  {len(data)}レース  {size/1024:.0f}KB")
    if ok == 0:
        print("::warning::オッズを1件も取得できなかった（ページ構造の変更を疑う）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
