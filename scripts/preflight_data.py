#!/usr/bin/env python3
"""予想の挙動を決めるデータが揃っているかを点検する。

## なぜ要るか

この repo では「データファイルが無いと補正が黙って中立に落ちる」事故が
繰り返し起きている:

  2026-08-10  data/venues/          消失 → 会場・季節・潮汐の補正が全死。1週間気づかず
  2026-09-05  data/tournament_grades.json   git に一度も入らず → グレード補正が全死
  2026-09-05  data/stats/*_combo_freq.json  未生成 → 会場別 win_freq ブレンド(v5.13)が全死
  2026-09-05  data/venues/stats/w1_winrate.json 未生成 → 1号艇沈みリスクの基準値が定数固定

いずれも `if path.exists(): ... else: 中立` という書き方で、**動いているように
見えたまま補正だけが消える**。テストも通るし例外も出ないので、出力を毎日見ていても
気づけない。

## 何を見るか

**存在するかだけでは足りない。git に載っているかを見る。**
Actions の runner は毎回まっさらな checkout なので、ローカルにしか無いファイルは
本番では存在しないのと同じ。tournament_grades.json はまさにこれで、
.gitignore の `data/*` に飲まれて一度も本番に届いていなかった。

使い方:
    python3 scripts/preflight_data.py            # 人が読む形式
    python3 scripts/preflight_data.py --strict   # 欠けていたら exit 1（CI用）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

REQUIRED = "required"    # 欠けると予想の挙動が変わる
OPTIONAL = "optional"    # 日々取得するもの。欠けていても正常なことがある

# (パス, 重要度, これが無いと何が起きるか, 作り直し方)
MANIFEST: list[tuple[str, str, str, str]] = [
    ("config.json", REQUIRED,
     "会場名辞書が空になる", "リポジトリに同梱。git から復元する"),
    ("data/venues/venue_characteristics.json", REQUIRED,
     "calc_venue_course_mod() が即 return し、会場・季節・潮汐の補正が丸ごと無効",
     "python3 scripts/build_venue_characteristics.py"),
    ("data/venues/official_course_stats.json", REQUIRED,
     "季節×コースの公式実測補正が効かず、手動推定値にフォールバックする",
     "scripts/scrape_stadium_data.py"),
    ("data/venues/stats/top1_followers.json", REQUIRED,
     "v5.23 の「1着枠別 2-3着連動」テーブルが空になる",
     "python3 scripts/build_stats.py"),
    ("data/players/master.json", REQUIRED,
     "選手マスタ（級別・性別）が引けない", "python3 scripts/build_player_master.py"),
    ("data/players/female_players.json", REQUIRED,
     "女子選手判定ができず、レディース戦の扱いが崩れる",
     "python3 scripts/build_player_master.py"),
    ("data/tournament_grades.json", REQUIRED,
     "get_tournament_grade_mods() が全グレードで course_mod=[1.0]*6 を返し、"
     "SG/G1 のイン有利もレディースのイン弱体も効かない",
     "python3 scripts/calibrate_tournament_grades.py --write"),
    ("data/venues/stats/w1_winrate.json", REQUIRED,
     "1号艇の沈みリスク推定の基準値が定数 0.578 に固定され、会場差が消える",
     "python3 scripts/build_w1_winrate.py --write"),
    ("data/stats/_all_combo_freq.json", REQUIRED,
     "load_combo_stats() が全会場で None を返し、_get_venue_win_freq_mod() の "
     "会場別 win_freq ブレンド(v5.13 1-C)が丸ごと無効になる",
     "python3 scripts/analyze_combo_freq.py"),
    ("data/results_csv", REQUIRED,
     "統計ビルダーの入力が無く、選手・モーター統計を作り直せない",
     "python3 scripts/fetch_results.py"),
    # 日次取得ぶん（当日ぶんが無いのは正常。ディレクトリの有無だけ見る）
    ("data/racecards", OPTIONAL, "出走表。無ければその日の予想が出せない",
     "python3 scripts/scraper.py / backfill_racecards.py"),
    ("data/players", OPTIONAL, "選手別統計", "python3 scripts/build_stats.py"),
    ("data/motors", OPTIONAL, "モーター別統計", "python3 scripts/build_stats.py"),
    ("data/odds_archive", OPTIONAL, "オッズ履歴（分析用）",
     ".github/workflows/archive_odds.yml"),
    ("data/raw", OPTIONAL,
     "福岡オリジナル展示（一周/まわり足/直線）。results_csv の該当7列の元データ",
     "自動: fetch_pending.yml / 過去分: scripts/backfill_fukuoka_tenji.py"),
]


def tracked_in_git(rel: str) -> bool:
    """git に載っているか。Actions の runner は checkout しか持たないので、
    ローカルにあっても git に無ければ本番では存在しないのと同じ。"""
    r = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                       cwd=BASE_DIR, capture_output=True)
    if r.returncode == 0:
        return True
    # ディレクトリの場合は配下に1つでも追跡ファイルがあればよい
    r = subprocess.run(["git", "ls-files", rel], cwd=BASE_DIR,
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="required が欠けていたら exit 1")
    ap.add_argument("--quiet", action="store_true", help="問題のある項目だけ出す")
    args = ap.parse_args()

    problems: list[tuple[str, str, str, str]] = []
    print("=" * 74)
    print("  予想データの点検（存在 / git追跡）")
    print("=" * 74)
    for rel, level, impact, howto in MANIFEST:
        p = BASE_DIR / rel
        exists = p.exists()
        in_git = tracked_in_git(rel)
        ok = exists and in_git
        if not ok and level == REQUIRED:
            problems.append((rel, "欠落" if not exists else "gitに無い", impact, howto))
        if args.quiet and ok:
            continue
        mark = "✅" if ok else ("❌" if level == REQUIRED else "⚠️ ")
        why = ""
        if not exists:
            why = "  ← 存在しない"
        elif not in_git:
            why = "  ← ローカルのみ。Actions では存在しないのと同じ"
        print(f"  {mark} [{level:<8}] {rel}{why}")

    if problems:
        print("\n" + "=" * 74)
        print(f"  ⚠️  補正が黙って無効になっている項目が {len(problems)} 件")
        print("=" * 74)
        for rel, state, impact, howto in problems:
            print(f"\n  ● {rel}  ({state})")
            print(f"    影響: {impact}")
            print(f"    復旧: {howto}")
        if args.strict:
            return 1
    else:
        print("\n  問題なし。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
