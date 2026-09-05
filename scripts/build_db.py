#!/usr/bin/env python3
"""日別 results_csv から分析用の SQLite を生成する。

## なぜ

`results_all.csv`（66MB）は日別CSVの単なる連結＝派生物なのに git に載っており、

  - GitHub の 50MB 警告を出しながら毎回まるごと書き換わり、.git を肥大させていた
  - **12,096行ぶん古くなっていた**（20260823以降の13日が欠落）。派生物が
    ソースに追随していないことを誰も検知していなかった

派生物は「毎回作り直す」ほうが、古くなりようがない。

## 何をソースにするか

**日別CSV（data/results_csv/YYYYMMDD.csv）が唯一のソース。** これは git に
載せ続ける。Actions の runner は毎回まっさらなので、git に無いデータは本番で
存在しないのと同じ、というのがこの repo の設計上の制約。
SQLite はバイナリで差分が読めず、verify / predict / fetch_pending の3つの
ワークフローが同時に commit すると衝突が壊滅的になるため、**ソースにはしない**。

DB は「分析を速くするための派生物」に徹する。git には載せない。

使い方:
    python3 scripts/build_db.py                  # data/boat.db を作り直す
    python3 scripts/build_db.py --check          # ソースとの行数一致だけ見る
"""
from __future__ import annotations

import argparse
import csv
import glob
import sqlite3
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_DIR = BASE_DIR / "data" / "results_csv"
DB = BASE_DIR / "data" / "boat.db"


def day_files() -> list[Path]:
    return [Path(p) for p in sorted(glob.glob(str(CSV_DIR / "2*.csv")))
            if "results_all" not in p]


def source_rows() -> int:
    n = 0
    for p in day_files():
        with open(p, encoding="utf-8-sig") as f:
            n += sum(1 for _ in csv.DictReader(f))
    return n


def build() -> int:
    files = day_files()
    if not files:
        print("日別CSVが無い")
        return 1
    with open(files[0], encoding="utf-8-sig") as f:
        cols = csv.DictReader(f).fieldnames
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    quoted = ", ".join(f'"{c}" TEXT' for c in cols)
    con.execute(f"CREATE TABLE results ({quoted})")
    ins = f'INSERT INTO results VALUES ({",".join("?" * len(cols))})'
    t0 = time.time()
    total = 0
    for p in files:
        with open(p, encoding="utf-8-sig") as f:
            batch = [[r.get(c, "") for c in cols] for r in csv.DictReader(f)]
        con.executemany(ins, batch)
        total += len(batch)
    # 決まり手（Open API 由来・2026-01-01以降のみ）。results_csv とは出所が
    # 違うので別テーブルに置き、(date, jcd, race_no) で結合する。
    import json as _json
    tdir = BASE_DIR / "data" / "techniques"
    if tdir.exists():
        con.execute("CREATE TABLE techniques (date TEXT, jcd TEXT, race_no TEXT, "
                    "technique TEXT, code INTEGER)")
        rows = []
        for tp in sorted(tdir.glob("2*.json")):
            doc = _json.loads(tp.read_text(encoding="utf-8"))
            for jcd, races in doc.items():
                for rno, v in races.items():
                    rows.append((tp.stem, jcd, rno, v.get("technique"), v.get("code")))
        con.executemany("INSERT INTO techniques VALUES (?,?,?,?,?)", rows)
        con.execute("CREATE INDEX i_tech ON techniques(date, jcd, race_no)")
        print(f"  techniques: {len(rows):,}行")

    # よく使う絞り込みに索引を張る
    for idx in ("CREATE INDEX i_date ON results(date)",
                "CREATE INDEX i_venue ON results(venue_name)",
                "CREATE INDEX i_race ON results(date, venue_name, race_no)",
                "CREATE INDEX i_reg ON results(reg_no)",
                "CREATE INDEX i_rank ON results(rank)"):
        con.execute(idx)
    con.commit()
    con.close()
    print(f"{DB} を生成: {total:,}行 / {len(files)}日 / "
          f"{DB.stat().st_size/1024/1024:.1f}MB / {time.time()-t0:.1f}秒")
    return 0


def check() -> int:
    if not DB.exists():
        print(f"DBが無い: {DB} → python3 scripts/build_db.py")
        return 1
    src = source_rows()
    con = sqlite3.connect(DB)
    got = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    con.close()
    ok = src == got
    print(f"日別CSV {src:,}行 / DB {got:,}行 → {'一致' if ok else '不一致（作り直しが要る）'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
