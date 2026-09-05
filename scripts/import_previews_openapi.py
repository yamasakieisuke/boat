#!/usr/bin/env python3
"""スタート展示（展示ST・展示進入コース・展示タイム）を Open API から取り込む。

## なぜ

壁（内側艇のSTが外からのまくりを止める）に使うSTとして、
「通算平均ST」「今節ST」「展示ST」のどれが効くかを比べたい。
通算と今節は結果CSVから作れるが、**展示STはどこにも持っていなかった**。

実測（通算 vs 今節、116,794件）では通算平均が主で、今節は同方向だが約1/3の強さ:

    3コース 1着率   内側の今節ST→  速     中   やや遅    遅
      内側の通算ST 速(〜.150)     9.2%  8.4%  10.6%  11.0%
      内側の通算ST 遅(.166〜)    14.3% 14.8%  14.9%  17.0%
      （縦=通算は強く単調 / 横=今節はほぼ平坦）

展示STは本番直前の状態を映すので、今節より効く可能性がある。

## 何が入っているか

`racer_start_timing` は**符号付き**（例 -0.04 = 展示でフライング相当に早い）。
`racer_course_number` は**展示の進入コース**で、本番の進入予想に直結する。
枠なり前提で course=waku としている現行の弱点を埋められる。

## 出力

  data/previews/{YYYYMMDD}.json
  {"02": {"1": {"1": {"c": 1, "st": 0.01, "ex": 6.74}, ...}}}
       会場   R    艇番       進入  展示ST  展示タイム

生のレスポンスは1日200KBあり、全期間だと100MB超になる。
使う3項目だけに絞って1日30-50KBに落としてある。

## 制約

非公式の有志プロジェクト。値の正しさは保証されない。
results/v2 と同じく2022年から遡れる（README の記述を鵜呑みにせず実際に叩いて確認）。
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
OUT_DIR = BASE_DIR / "data" / "previews"
API = "https://boatraceopenapi.github.io/previews/v2/{y}/{d}.json"
UA = {"User-Agent": "boat-import/1.0 (personal research; contact: ask11nl@gmail.com)"}


def slim(payload: dict) -> dict:
    out: dict = {}
    for p in payload.get("previews") or []:
        try:
            jcd = f"{int(p['race_stadium_number']):02d}"
            rno = str(int(p["race_number"]))
        except (KeyError, TypeError, ValueError):
            continue
        boats = {}
        for b in p.get("boats") or []:
            try:
                bn = str(int(b["racer_boat_number"]))
            except (KeyError, TypeError, ValueError):
                continue
            e = {}
            c = b.get("racer_course_number")
            st = b.get("racer_start_timing")
            ex = b.get("racer_exhibition_time")
            if isinstance(c, (int, float)):
                e["c"] = int(c)
            if isinstance(st, (int, float)):
                e["st"] = round(float(st), 3)
            if isinstance(ex, (int, float)):
                e["ex"] = round(float(ex), 2)
            if e:
                boats[bn] = e
        if boats:
            out.setdefault(jcd, {})[rno] = boats
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to", dest="date_to", required=True)
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    d = datetime.datetime.strptime(args.date_from, "%Y%m%d").date()
    end = datetime.datetime.strptime(args.date_to, "%Y%m%d").date()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ok = skip = miss = 0
    while d <= end:
        ds = d.strftime("%Y%m%d")
        out = OUT_DIR / f"{ds}.json"
        if out.exists() and not args.overwrite:
            skip += 1
            d += datetime.timedelta(days=1)
            continue
        try:
            r = requests.get(API.format(y=d.year, d=ds), headers=UA, timeout=30)
            if r.status_code == 404:
                miss += 1          # 非開催日
            else:
                r.raise_for_status()
                data = slim(r.json())
                if data:
                    out.write_text(json.dumps(data, ensure_ascii=False,
                                              separators=(",", ":")), encoding="utf-8")
                    ok += 1
                else:
                    miss += 1
        except Exception as e:
            print(f"[WARN] {ds}: {e}", file=sys.stderr)
        time.sleep(args.sleep)
        d += datetime.timedelta(days=1)

    print(f"取得 {ok}日 / 既存スキップ {skip}日 / データ無し {miss}日")
    if ok:
        files = list(OUT_DIR.glob("*.json"))
        tot = sum(p.stat().st_size for p in files)
        print(f"合計 {len(files)}ファイル {tot/1024/1024:.1f}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
