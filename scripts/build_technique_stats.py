#!/usr/bin/env python3
"""選手別の決まり手傾向と、決まり手→1コース艇の着順テーブルを作る（展開予想の土台）。

## なぜ

「合計ポイントの高い順に3連単を組む」だと、**同じ着順予想でも中身が違う**ことを
表現できない。3コースが勝つとして、まくりで勝つのか まくり差しで勝つのかで
1コースの艇がどこに残るかが決定的に変わる:

    3コース勝ち  まくり     → 1コースが2着 23.4%
    3コース勝ち  まくり差し  → 1コースが2着 63.5%   (+40pt)

そしてこの「まくり型か まくり差し型か」は**選手の個人特性として実在する**。
時系列で前半→後半に割った検証（外コース1着 19,425件）:

    MIN_N= 8  選手499人  r=+0.519  後半まくり率 下位1/3=0.361 上位1/3=0.614
    MIN_N=10  選手326人  r=+0.585  後半まくり率 下位1/3=0.352 上位1/3=0.633

2コースも同じ構造を持つ（差し型か まくり型か）。効果はより大きい:

    2コース勝ち  差し   → 1コースが2着 61.7%
    2コース勝ち  まくり → 1コースが2着 11.2%  / 4着以下 72.0%

ただし選手特性としての安定性は外コースより弱い（r=+0.35）。

## 縮約

生の実測値をそのまま使うと**ベースラインより悪くなる**（K=0 の held-out Brier
0.25554 < 常に全体平均 0.24997）。試行回数の少ない選手のノイズを拾うため。
K は held-out Brier の最小値で決めた:

    外コース(まくり型)  K=12  Brier 0.23837 (base 0.24997)
    2コース(差し型)     K=20  Brier 0.21306 (base 0.21663)

どちらも最適値の周りは平坦なので、多少ズレても壊れない。

## 出力

  data/stats/racer_technique.json

## 入力

boat.db ではなく data/results_csv/ と data/techniques/ を直接読む。
**boat.db は gitignore なので Actions の runner には存在しない**。
分析用の派生物に本番を依存させない。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_DIR = BASE_DIR / "data" / "results_csv"
TECH_DIR = BASE_DIR / "data" / "techniques"
OUT_PATH = BASE_DIR / "data" / "stats" / "racer_technique.json"

VENUE_CODE_MAP = {
    "桐生": "01", "戸田": "02", "江戸川": "03", "平和島": "04", "多摩川": "05",
    "浜名湖": "06", "蒲郡": "07", "常滑": "08", "津": "09", "三国": "10",
    "びわこ": "11", "住之江": "12", "尼崎": "13", "鳴門": "14", "丸亀": "15",
    "児島": "16", "宮島": "17", "徳山": "18", "下関": "19", "若松": "20",
    "芦屋": "21", "福岡": "22", "唐津": "23", "大村": "24",
}

# 縮約係数。held-out Brier で決めた（docstring 参照）。
K_OUTER = 12.0   # 外コース(3-6)の「まくり型度」
K_C2 = 20.0      # 2コースの「差し型度」

# これ未満のサンプルしか無い選手は、縮約してもほぼ全体平均になるので載せない。
# ファイルを小さく保つためだけの足切りで、精度上の意味は無い。
MIN_KEEP = 3


def _load_techniques() -> dict:
    """{(date, jcd, race_no): technique}"""
    out: dict[tuple[str, str, int], str] = {}
    for p in sorted(TECH_DIR.glob("????????.json")):
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] {p.name}: {e}")
            continue
        # 日付はファイル名。中身は {"22": {"1": {"technique": "まくり", "code": 3}}}
        date_str = p.stem
        for jcd, races in data.items():
            if not isinstance(races, dict):
                continue
            for race_no, info in races.items():
                tech = (info or {}).get("technique") if isinstance(info, dict) else None
                if tech:
                    try:
                        out[(date_str, jcd, int(race_no))] = tech
                    except ValueError:
                        pass
    return out


def _iter_results():
    for p in sorted(CSV_DIR.glob("????????.csv")):
        try:
            with open(p, encoding="utf-8-sig") as f:
                yield from csv.DictReader(f)
        except Exception as e:
            print(f"[WARN] {p.name}: {e}")


def build() -> dict:
    tech_map = _load_techniques()
    print(f"決まり手: {len(tech_map):,}レース")

    # 勝者の (コース, 決まり手, 選手) と、同レースの1コース艇の着順を集める
    win = {}     # key -> (course, reg_no)
    c1_rank = {}  # key -> rank文字列
    second_course = {}  # key -> 2着艇の進入コース
    for row in _iter_results():
        jcd = VENUE_CODE_MAP.get(row.get("venue_name", ""))
        if not jcd:
            continue
        try:
            key = (row["date"], jcd, int(row["race_no"]))
            course = int(row["course_enter"])
        except (KeyError, ValueError, TypeError):
            continue
        if key not in tech_map:
            continue
        if row.get("rank") == "1":
            win[key] = (course, row.get("reg_no", ""))
        if course == 1:
            c1_rank[key] = row.get("rank", "")
        if row.get("rank") == "2":
            second_course[key] = course

    print(f"結合できたレース: {len(win):,}")

    # ── 1) 決まり手 → 1コース艇の着順 ────────────────────────────
    payload_cnt = defaultdict(lambda: {"n": 0, "c1_2nd": 0, "c1_3rd": 0})
    for key, (course, _reg) in win.items():
        if course < 2:
            continue
        tech = tech_map[key]
        rank = c1_rank.get(key, "")
        if not rank.isdigit():   # F/L/K など。1コースが走っていないので除く
            continue
        d = payload_cnt[f"{course}|{tech}"]
        d["n"] += 1
        if rank == "2":
            d["c1_2nd"] += 1
        elif rank == "3":
            d["c1_3rd"] += 1

    # コース別の周辺分布（決まり手を問わない）。展開モデルはこれを基準にして、
    # 「その選手の決まり手傾向が平均からどれだけズレているか」ぶんだけ動かす。
    # こうすると平均的な選手では既存の挙動と一致し、副作用が出ない。
    marg_cnt = defaultdict(lambda: {"n": 0, "c1_2nd": 0, "c1_3rd": 0})
    for k, d in payload_cnt.items():
        course = k.split("|")[0]
        m = marg_cnt[course]
        for f in ("n", "c1_2nd", "c1_3rd"):
            m[f] += d[f]
    marginal = {
        c: {"n": d["n"],
            "c1_2nd": round(d["c1_2nd"] / d["n"], 4),
            "c1_3rd": round(d["c1_3rd"] / d["n"], 4)}
        for c, d in marg_cnt.items() if d["n"] >= 300
    }

    payload = {}
    for k, d in payload_cnt.items():
        if d["n"] < 150:   # これ未満は会場差・年度差に埋もれる
            continue
        payload[k] = {
            "n": d["n"],
            "c1_2nd": round(d["c1_2nd"] / d["n"], 4),
            "c1_3rd": round(d["c1_3rd"] / d["n"], 4),
        }

    # ── 1b) 決まり手ごとの【2着コースの完全分布】────────────────
    # 1コース艇の位置だけを動かして残りを比例配分する方式では、
    # 「4コースがまくったとき2着=5が34.4%に跳ねる」構造を表現できない。
    # まくりは外へ大きく張るので勝った艇のすぐ外が付いてくる
    # （3まくり→4,5 / 4まくり→5,6 / 5まくり→6）。まくり差しは内を通すので
    # 1コースが残る。いわゆるスジ舟券のセオリーで、実測とも一致する。
    sec_cnt = defaultdict(lambda: defaultdict(int))
    sec_marg = defaultdict(lambda: defaultdict(int))
    for key, (course, _reg) in win.items():
        if course < 2:
            continue
        sec = second_course.get(key)
        if not sec:
            continue
        tech = tech_map[key]
        sec_cnt[f"{course}|{tech}"][str(sec)] += 1
        sec_marg[str(course)][str(sec)] += 1

    def _norm(d: dict, floor: int) -> dict | None:
        n = sum(d.values())
        if n < floor:
            return None
        out = {k: round(v / n, 4) for k, v in sorted(d.items())}
        out["n"] = n
        return out

    second_dist = {k: v for k, v in ((k, _norm(d, 300)) for k, d in sec_cnt.items()) if v}
    second_marginal = {k: v for k, v in ((k, _norm(d, 500)) for k, d in sec_marg.items()) if v}

    # ── 2) 選手別の決まり手傾向 ──────────────────────────────
    outer = defaultdict(lambda: [0, 0])   # reg -> [まくり数, 総数]
    c2 = defaultdict(lambda: [0, 0])      # reg -> [差し数, 総数]
    for key, (course, reg) in win.items():
        if not reg:
            continue
        tech = tech_map[key]
        if 3 <= course <= 6 and tech in ("まくり", "まくり差し"):
            outer[reg][1] += 1
            if tech == "まくり":
                outer[reg][0] += 1
        elif course == 2 and tech in ("差し", "まくり"):
            c2[reg][1] += 1
            if tech == "差し":
                c2[reg][0] += 1

    base_outer = (sum(v[0] for v in outer.values()) / sum(v[1] for v in outer.values())
                  if outer else 0.5)
    base_c2 = (sum(v[0] for v in c2.values()) / sum(v[1] for v in c2.values())
               if c2 else 0.675)

    racers = {}
    for reg in set(outer) | set(c2):
        e = {}
        h, n = outer.get(reg, [0, 0])
        if n >= MIN_KEEP:
            e["outer_n"] = n
            e["makuri_rate"] = round((K_OUTER * base_outer + h) / (K_OUTER + n), 4)
        h2, n2 = c2.get(reg, [0, 0])
        if n2 >= MIN_KEEP:
            e["c2_n"] = n2
            e["sashi_rate"] = round((K_C2 * base_c2 + h2) / (K_C2 + n2), 4)
        if e:
            racers[reg] = e

    return {
        "meta": {
            "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "races": len(win),
            "base_makuri_outer": round(base_outer, 4),
            "base_sashi_c2": round(base_c2, 4),
            "K_outer": K_OUTER,
            "K_c2": K_C2,
        },
        "marginal": marginal,
        "second_dist": second_dist,
        "second_marginal": second_marginal,
        "payload": payload,
        "racers": racers,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="ファイルに書き出す")
    args = ap.parse_args()

    data = build()
    m = data["meta"]
    print(f"\n全体まくり率(外コース)={m['base_makuri_outer']:.4f} "
          f"全体差し率(2コース)={m['base_sashi_c2']:.4f}")
    print(f"選手: {len(data['racers']):,}人  決まり手別テーブル: {len(data['payload'])}件\n")
    print(f"{'勝ちコース':<22}{'n':>7}{'1が2着':>9}{'1が3着':>9}  ← 周辺分布(基準)")
    for c in sorted(data["marginal"]):
        v = data["marginal"][c]
        print(f"{c+'コース':<22}{v['n']:>7,}{v['c1_2nd']*100:>8.1f}%{v['c1_3rd']*100:>8.1f}%")
    print()
    print(f"{'勝ちコース|決まり手':<22}{'n':>7}{'1が2着':>9}{'1が3着':>9}")
    for k in sorted(data["payload"], key=lambda x: (int(x.split('|')[0]), x)):
        v = data["payload"][k]
        print(f"{k:<22}{v['n']:>7,}{v['c1_2nd']*100:>8.1f}%{v['c1_3rd']*100:>8.1f}%")

    print(f"\n2着コース分布: 決まり手別 {len(data['second_dist'])}件 / "
          f"周辺 {len(data['second_marginal'])}件")
    for k in sorted(data["second_dist"], key=lambda x: (int(x.split('|')[0]), x)):
        v = data["second_dist"][k]
        cells = "".join(f"{v.get(str(c), 0)*100:>7.1f}%" for c in range(1, 7))
        print(f"  {k:<16}{v['n']:>7,}{cells}")

    if args.write:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n書き出し: {OUT_PATH.relative_to(BASE_DIR)} "
              f"({OUT_PATH.stat().st_size/1024:.0f}KB)")
    else:
        print("\n(--write を付けると書き出す)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
