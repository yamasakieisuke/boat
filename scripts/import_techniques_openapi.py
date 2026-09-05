#!/usr/bin/env python3
"""決まり手（逃げ/まくり/差し/まくり差し/抜き/恵まれ）を Open API から取り込む。

## なぜ

「3コースが展示で優位ならまくりの可能性が上がる」「展示が良くても平均STが
遅い選手は外からまくれない」といった仮説は、**決まり手が無いと検証できない**。
LZH の結果帳票にも公式サイトにも決まり手は入っておらず、これまで持っていなかった。

Open API の result.technique_number_source に入っている。実測4日624レースで
欠損ゼロ、分布は 逃げ51.3% / まくり14.9% / 差し13.6% / まくり差し13.5% /
抜き5.9% / 恵まれ0.8%。

## 出力

  data/techniques/{YYYYMMDD}.json
  {"20260904": {"22": {"1": {"technique": "まくり", "code": 3}, ...}}}

results_csv には混ぜない。あちらは LZH 帳票由来で、出所の違うデータを
同じファイルに入れると「どこから来た値か」が追えなくなる。
分析時に (date, jcd, race_no) で結合する。

## 制約

現役の api/v1 は 2026-01-01 以降のみだが、**Deprecated の results/v2 は 2022年から**
遡れる。決まり手は選手別の傾向を出すのに数年ぶん要るので、この差は決定的。
非公式の有志プロジェクトなので、値の正しさは保証されない。
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "techniques"
# 現役の api/v1 は 2026-01-01 以降しか無いが、**Deprecated 扱いの results/v2 は
# 2022年から遡れる**。README の記述だけを見て「2026年以降のみ」と判断したのは誤りで、
# 実際に叩いて確かめるべきだった。決まり手は選手別の傾向を出すのに4年ぶん要るので、
# この差は決定的。
API_V1 = "https://boatraceopenapi.github.io/api/v1/{y}/{d}.json"
API_V2 = "https://boatraceopenapi.github.io/results/v2/{y}/{d}.json"
UA = {"User-Agent": "boat-import/1.0 (personal research; contact: ask11nl@gmail.com)"}
V1_START = datetime.date(2026, 1, 1)
# results/v2 は決まり手を数値コードで持つ。対応は api/v1 の
# technique_number / technique_number_source を突き合わせて確認済み。
TECHNIQUE = {1: "逃げ", 2: "差し", 3: "まくり", 4: "まくり差し", 5: "抜き", 6: "恵まれ"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    d = datetime.datetime.strptime(args.date_from, "%Y%m%d").date()
    d1 = datetime.datetime.strptime(args.date_to, "%Y%m%d").date()
    print(f"[INFO] {V1_START} 以降は api/v1、それ以前は results/v2（2022年まで遡れる）")

    wrote = skipped = empty = 0
    while d <= d1:
        ds = d.strftime("%Y%m%d")
        out = OUT_DIR / f"{ds}.json"
        if out.exists() and not args.overwrite:
            skipped += 1
            d += datetime.timedelta(days=1)
            continue
        url = (API_V1 if d >= V1_START else API_V2).format(y=ds[:4], d=ds)
        try:
            r = requests.get(url, timeout=40, headers=UA)
        except Exception as e:
            print(f"  {ds}: 取得失敗 {e}")
            d += datetime.timedelta(days=1)
            continue
        if r.status_code != 200:
            empty += 1
            d += datetime.timedelta(days=1)
            time.sleep(args.sleep)
            continue
        j = r.json()
        doc: dict = {}
        if d >= V1_START:
            for jcd_raw, st in ((j.get("programs") or {}).get("stadiums") or {}).items():
                jcd = f"{int(jcd_raw):02d}"
                for rno_raw, race in (st.get("races") or {}).items():
                    res = race.get("result") or {}
                    t = res.get("technique_number_source")
                    if not t:
                        continue
                    doc.setdefault(jcd, {})[str(int(rno_raw))] = {
                        "technique": t, "code": res.get("technique_number")}
        else:
            # results/v2 は1レース1要素のフラットな配列で、決まり手は数値コード
            for race in (j.get("results") or []):
                code = race.get("race_technique_number")
                if not code:
                    continue
                jcd = f"{int(race['race_stadium_number']):02d}"
                doc.setdefault(jcd, {})[str(int(race["race_number"]))] = {
                    "technique": TECHNIQUE.get(code, ""), "code": code}
        if doc:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            wrote += 1
            n = sum(len(v) for v in doc.values())
            print(f"  {ds}: {len(doc)}会場 {n}レース")
        else:
            empty += 1
        d += datetime.timedelta(days=1)
        time.sleep(args.sleep)

    print(f"\n完了: 保存 {wrote}日 / 既存スキップ {skipped}日 / データなし {empty}日")
    return 0


if __name__ == "__main__":
    sys.exit(main())
