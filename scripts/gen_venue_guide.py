#!/usr/bin/env python3
"""
会場特性ガイド生成スクリプト  v1.0
──────────────────────────────────────────────────────────────
data/venues/venue_characteristics.json を読み込み、
人間が目視確認しやすいテキストを output/data/venue_guide.txt に出力する。

使い方:
  python3 scripts/gen_venue_guide.py             # 全24場
  python3 scripts/gen_venue_guide.py --jcd 22    # 福岡のみ
──────────────────────────────────────────────────────────────
"""

import json
import datetime
import argparse
from pathlib import Path

BASE_DIR        = Path(__file__).parent.parent
DATA_DIR        = BASE_DIR / "data"
OUTPUT_DIR      = BASE_DIR / "output"
DATA_OUTPUT_DIR = OUTPUT_DIR / "data"
VENUE_JSON      = DATA_DIR / "venues" / "venue_characteristics.json"

SEASON_JP = {
    "spring": "春(3〜5月)",
    "summer": "夏(6〜8月)",
    "autumn": "秋(9〜11月)",
    "winter": "冬(12〜2月)",
}

TIDE_JP = {
    "high_tide":    "満潮",
    "low_tide":     "干潮",
    "rising_tide":  "上げ潮",
    "falling_tide": "下げ潮",
}


def _bar(values: list, width: int = 12) -> str:
    """枠別補正係数を簡易バーで可視化（0.80〜1.20 → 0〜12文字）"""
    parts = []
    for v in values:
        # 1.00が中央、0.80=0個、1.20=12個
        n = max(0, min(width, int((v - 0.80) / 0.40 * width)))
        parts.append(f"[{'█'*n}{' '*(width-n)}] {v:.2f}")
    return "  ".join(parts)


def _course_table(course_mod: list, label: str = "") -> str:
    """枠1〜6の補正係数を横一行テーブルで出力"""
    header = "  枠  " + "  ".join(f"[{i+1}枠]" for i in range(6))
    vals   = "  補正 " + "  ".join(f"{v:+.2f}".replace("+", " ") for v in
                                   [c - 1.0 for c in course_mod])
    prefix = f"  ({label}) " if label else "  "
    return f"{prefix}枠補正: " + "  ".join(
        f"{i+1}枠={course_mod[i]:.2f}" for i in range(6)
    )


def format_venue(jcd: str, data: dict) -> str:
    """1会場分のテキストを生成して返す"""
    lines = []
    name    = data.get("name", jcd)
    water   = data.get("water_type", "?")
    tidal   = "潮汐あり" if data.get("tidal") else "潮汐なし"
    base1w  = data.get("base_1course_win", 0)
    notes   = data.get("notes", "")

    lines.append(f"{'━'*70}")
    lines.append(f"  ■ {name}({jcd})  {water}　{tidal}  1コース基礎勝率: {base1w*100:.0f}%")
    lines.append(f"{'━'*70}")
    lines.append(f"  概要: {notes}")
    lines.append("")

    # ── 季節別 ────────────────────────────────────────────────
    lines.append("  【季節別 枠補正】")
    for sk, slab in SEASON_JP.items():
        s = data.get("seasonal", {}).get(sk)
        if not s:
            continue
        cm   = s.get("course_mod", [1.0]*6)
        note = s.get("note", "")
        lines.append(f"  {slab:12s}: " +
                     "  ".join(f"{i+1}={cm[i]:.2f}" for i in range(6)) +
                     f"  ← {note}")
    lines.append("")

    # ── 風 ─────────────────────────────────────────────────────
    wind = data.get("wind")
    if wind:
        thr = wind.get("headwind_threshold_ms", "-")
        hcm = wind.get("headwind_course_mod", [])
        tcm = wind.get("tailwind_course_mod", [])
        lines.append(f"  【風影響】  向かい風閾値: {thr} m/s")
        if hcm:
            lines.append("  向かい風: " +
                         "  ".join(f"{i+1}={hcm[i]:.2f}" for i in range(len(hcm))))
        if tcm:
            lines.append("  追い風  : " +
                         "  ".join(f"{i+1}={tcm[i]:.2f}" for i in range(len(tcm))))
        lines.append("")

    # ── 潮汐条件 ────────────────────────────────────────────────
    tidal_cond = data.get("tidal_conditions")
    if tidal_cond:
        lines.append("  【潮汐別 枠補正】")
        for tk, tlab in TIDE_JP.items():
            tc = tidal_cond.get(tk)
            if not tc:
                continue
            cm   = tc.get("course_mod", [])
            note = tc.get("note", "")
            lines.append(f"  {tlab:6s}: " +
                         "  ".join(f"{i+1}={cm[i]:.2f}" for i in range(len(cm))) +
                         f"  ← {note}")
        lines.append("")

    # ── レース帯別 ───────────────────────────────────────────────
    rnt = data.get("race_no_tendency")
    if rnt:
        lines.append("  【時間帯別 傾向】")
        for band in ["early", "middle", "late"]:
            b = rnt.get(band)
            if not b:
                continue
            races = b.get("races", [])
            note  = b.get("note", "")
            cm    = b.get("course_mod", [])
            rstr  = f"{races[0]}〜{races[-1]}R" if races else "?"
            lines.append(f"  {rstr:8s}: {note}")
            if cm:
                lines.append("           枠補正: " +
                             "  ".join(f"{i+1}={cm[i]:.2f}" for i in range(len(cm))))
        lines.append("")

    return "\n".join(lines)


def generate_guide(jcd_filter: str | None = None) -> None:
    if not VENUE_JSON.exists():
        print(f"[ERROR] {VENUE_JSON} が見つかりません")
        return

    with open(VENUE_JSON, encoding="utf-8") as f:
        all_data = json.load(f)

    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    out_path = DATA_OUTPUT_DIR / "venue_guide.txt"
    today    = datetime.date.today().strftime("%Y-%m-%d")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write(f"  ボートレース　全場特性ガイド\n")
        f.write(f"  生成日: {today}\n")
        f.write("=" * 70 + "\n\n")

        count = 0
        for jcd in sorted(k for k in all_data if k != "_comment"):
            if jcd_filter and jcd != jcd_filter:
                continue
            venue = all_data[jcd]
            f.write(format_venue(jcd, venue))
            f.write("\n")
            count += 1

    print(f"  🏟  会場特性ガイド生成完了: {out_path}  （{count} 会場）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="会場特性ガイド生成")
    parser.add_argument("--jcd", default=None,
                        help="出力する会場コード（省略時は全24場）")
    args = parser.parse_args()
    generate_guide(args.jcd)
