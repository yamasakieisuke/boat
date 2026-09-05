#!/usr/bin/env python3
from __future__ import annotations
"""
ボートレース 予想エンジン v5.5
──────────────────────────────────────────────────────────────────
変更点 (v5.4→v5.5):
  [1] 公式ピットレポート統合（全会場R7-12）
      - scrape_pitreport() で beforeinfo ページから選手コメントを取得
      - pitreport_data を comment_data より優先してスコア計算・HTML表示に使用
  [2] 会場固有データ（大村・福岡）
      - scrape_engine_report() : エンジン通信簿（1-6評価 → engine_bonus ±0.012）
      - scrape_player_review() : 選手短評（シリーズ単位の短評 fallback）
      - VENUE_SITE_CONFIG を scraper.py に追加
      - scraper.py --mode day で対応会場は自動取得
  [3] HTML出力改善
      - スコア表に「ｴﾝｼﾞﾝ」列追加（+/-値を色付き表示）
      - コメント欄に出典ラベルをインライン表示（pitreport/会場公式/短評を識別）
      - player_review を fallback 表示（コメント未取得R1-6でも短評あれば表示）
  [4] 進入コース空欄対応
      - レース終了後の beforeinfo は進入コース欄が空になる公式仕様を明示（"—" 表示）
──────────────────────────────────────────────────────────────────
変更点 (v5.3→v5.4):
  [1] 公式会場統計データ統合 (get_official_seasonal_course_mod)
      - scripts/scrape_stadium_data.py で全24場取得した
        data/venues/official_course_stats.json を参照
      - boatrace.jp 公式の季節別コース1着率を全国平均で割り
        venue_course_mod として calc_venue_course_mod() に優先適用
      - フォールバック: 手動設定の venue_characteristics.json 推定値
  [2] 全国平均コース1着率定数 (_NATIONAL_AVG_COURSE_WIN) 追加
      - 春[55.9,17.6,9.2,7.0,5.4,4.6] / 夏 / 秋 / 冬 の4季分
──────────────────────────────────────────────────────────────────
変更点 (v5.2→v5.3):
  [1] 大会グレード別コース補正 (TOURNAMENT_GRADE_COURSE_MODS) 追加
      - data/tournament_grades.json を静的データとして読み込み
      - SG/G1/G2/G3/一般/レディース 別に course_advantage を補正
      - racecard JSON の tournament_grade フィールド使用
  [2] 全員女性レース検出 (is_all_female_race)
      - tournament_grade が未設定でも predictor 内で自動検出
      - "レディース" グレード補正を適用
  [3] output/data/tournament_guide.md 自動出力
      - 予測ファイル生成時に大会グレード解説 md も更新
  [4] 出力 HTML にグレードバッジ表示
──────────────────────────────────────────────────────────────────
変更点 (v5.1→v5.2):
  [A] 出目統計ブレンド対応（analyze_combo_freq.py）
  [B] ボート2連率スコア追加 (boat_2rate)
  [C] 今節成績スコア追加 (series_score)
  [D] 進入コース補正 (actual_entry_course)
  [E] _RACE_TYPE_FINALIST バグ修正 (SG|G1|G2|G3 を除去)
──────────────────────────────────────────────────────────────────
変更点 (v5.0→v5.1):
  [A2] 現地での見やすさ改善
      - 買い目を出力の先頭に移動（詳細スコアより前に表示）
      - 全レース早見表を出力ファイル冒頭に追加
      - 信頼度インジケーターを % 表示に変更
      - ⚡荒れ注意フラグ（1位-2位スコア差 < 0.015 の場合）
──────────────────────────────────────────────────────────────────
変更点 (v4.1→v5.0):
  [1] 女性レーサー係数 (female_factor) 追加
      - data/players/female_players.json または player_stats["gender"] で判定
      - 風速・波高に応じてペナルティ（強風時 -0.012 相当）
      - 出力に 🚺 マーカー表示
  [2] 1枠過剰支配の是正
      - course_advantage 係数: 0.22 → 0.15
      - global_win_rate: 0.13 → 0.15、local_win_rate: 0.13 → 0.15
      - st_score: 0.14 → 0.16、female_factor: 新設 0.04
      - grade_bonus: 0.07 → 0.05、comment_score: 0.05 → 0.04
  [3] 買い目を 3連単のみ（本命2-3点 + 穴1点）に絞る
──────────────────────────────────────────────────────────────────
変更点 (v4→v4.1):
  - comment_score : 会場公式サイトの選手コメント（足の状態）をスコア化
  - exhibition_score 0.12→0.09、hist_waku_score 0.08→0.06 に調整
  - コメント履歴を data/player_comments/{reg_no}.json に蓄積
──────────────────────────────────────────────────────────────────
変更点 (v3→v4):
  - hist_global_win_rate / hist_local_win_rate : 実績勝率を利用
  - hist_avg_st                                : 実績平均STを利用
  - hist_motor_stats（motors/*.json）          : 当地モーター実績を参照
  - hist_waku_score                            : 当地・当枠の実績1着率を新指標として追加
  - _print_result に枠別着順割合テーブルを追加
──────────────────────────────────────────────────────────────────
"""

import json
import os
import re
import datetime
from pathlib import Path

# 出目頻度統計（analyze_combo_freq.py）
try:
    from analyze_combo_freq import (
        load_combo_stats as _raw_load_combo_stats,
        get_cond_2nd_prob,
        get_cond_3rd_prob,
        get_best_2nd,
        get_best_3rd,
        _race_type_to_stage,
        _race_no_to_period,
        _month_to_season,
    )
    _COMBO_STATS_AVAILABLE = True
except ImportError:
    _COMBO_STATS_AVAILABLE = False
    def _raw_load_combo_stats(jcd): return None
    def get_cond_2nd_prob(stats, f, s): return 0.0
    def get_cond_3rd_prob(stats, f, s, t): return 0.0
    def get_best_2nd(stats, f): return ("2", 0.2)
    def get_best_3rd(stats, f, s): return ("3", 0.25)
    def _race_type_to_stage(rt): return "一般"
    def _race_no_to_period(rn):
        if rn <= 4: return "early"
        if rn <= 8: return "middle"
        return "late"
    def _month_to_season(m):
        try: mm = int(str(m)[-2:])
        except: return "winter"
        if 3 <= mm <= 5: return "spring"
        if 6 <= mm <= 8: return "summer"
        if 9 <= mm <= 11: return "autumn"
        return "winter"

# combo_stats は会場ごとに1ファイルなので実行時にキャッシュ
_COMBO_STATS_CACHE: dict[str, dict] = {}


_COMBO_STATS_WARNED = False


def load_combo_stats(jcd: str) -> dict | None:
    """会場別の出目頻度統計。

    ⚠️ data/stats/*_combo_freq.json が無いと全会場で None を返し、
       _get_venue_win_freq_mod() が [1.0]*6 に落ちる＝**会場別 win_freq の
       25%ブレンド(v5.13 1-C)が丸ごと無効**になる。
       2026-09-05 時点で data/stats/ 自体が存在しなかった。
       作り直しは `python3 scripts/analyze_combo_freq.py`。
    """
    global _COMBO_STATS_WARNED
    if jcd in _COMBO_STATS_CACHE:
        return _COMBO_STATS_CACHE[jcd]
    stats = _raw_load_combo_stats(jcd) if _COMBO_STATS_AVAILABLE else None
    if stats is None and not _COMBO_STATS_WARNED:
        _COMBO_STATS_WARNED = True
        print(f"[WARN] 会場別 combo_freq が無い（jcd={jcd} で確認）。"
              f"会場別 win_freq のブレンドが効かない。"
              f"作り直し: python3 scripts/analyze_combo_freq.py")
    _COMBO_STATS_CACHE[jcd] = stats
    return stats


def _collect_axis_top_combos(combo_stats: dict, date_str: str, race_no: int,
                              race_name: str) -> list[tuple[str, float, str]]:
    """
    当該レースの (月 / 季節 / レース帯 / 種別) に該当する各軸統計から
    top_combos をマージして返す。重み付きで並べ替え、上位を返す。

    戻り値: [(combo, weighted_freq, source), ...]

    使い方: overall の top_combos と合わせて本命① に強制組み込みする候補に使う。
    """
    if not combo_stats:
        return []

    month  = (date_str or "")[:6]
    season = _month_to_season(month)
    period = _race_no_to_period(race_no)
    stage  = _race_type_to_stage(race_name)

    # 各軸から取得。存在すれば重みを決める（軸別の信頼度）。
    axes = [
        ("by_month",  month,  0.35),
        ("by_stage",  stage,  0.30),
        ("by_period", period, 0.20),
        ("by_season", season, 0.15),
    ]

    merged: dict[str, tuple[float, list[str]]] = {}
    for axis_key, bucket_key, weight in axes:
        axis = (combo_stats.get(axis_key) or {}).get(bucket_key)
        if not axis:
            continue
        tc = axis.get("top_combos") or []
        for entry in tc:
            combo = entry.get("combo", "")
            freq  = float(entry.get("freq", 0) or 0)
            if not combo or freq <= 0:
                continue
            cur = merged.get(combo, (0.0, []))
            merged[combo] = (cur[0] + freq * weight, cur[1] + [f"{axis_key[3:]}={bucket_key}({freq*100:.1f}%)"])

    # 重みの高い順に並べる
    sorted_combos = sorted(merged.items(), key=lambda kv: kv[1][0], reverse=True)
    return [(combo, wf, "/".join(srcs[:2])) for combo, (wf, srcs) in sorted_combos]


def _collect_axis_ev_combos(combo_stats: dict, date_str: str, race_no: int,
                             race_name: str,
                             min_count: int = 10, min_ev: float = 1.2) -> list[tuple[str, float, float, str]]:
    """
    v5.15 段階3: 期待値ベースの top combos を各軸からマージして返す。
    過去実測の「頻度×平均払戻」で EV≥min_ev かつ count≥min_count のものだけを拾う。

    戻り値: [(combo, ev, avg_pay, source), ...]  EV 降順
    """
    if not combo_stats:
        return []

    month  = (date_str or "")[:6]
    season = _month_to_season(month)
    period = _race_no_to_period(race_no)
    stage  = _race_type_to_stage(race_name)

    axes = [
        ("by_month",  month),
        ("by_stage",  stage),
        ("by_period", period),
        ("by_season", season),
    ]

    # overall EV も候補に入れる
    candidates: dict[str, tuple[float, float, list[str]]] = {}

    def _consume(ev_list, src_label):
        for entry in ev_list or []:
            combo = entry.get("combo", "")
            ev = float(entry.get("ev", 0) or 0)
            count = int(entry.get("count", 0) or 0)
            avg_pay = float(entry.get("avg_pay", 0) or 0)
            if count < min_count or ev < min_ev or not combo:
                continue
            cur = candidates.get(combo)
            # 同じ combo が複数軸で出てきたら「最大 EV」を採用
            if cur is None or ev > cur[0]:
                srcs = (cur[2] if cur else []) + [f"{src_label}(EV{ev:.2f})"]
                candidates[combo] = (ev, avg_pay, srcs)
            else:
                cur[2].append(f"{src_label}(EV{ev:.2f})")

    _consume(combo_stats.get("ev_top_combos"), "overall")
    for axis_key, bucket_key in axes:
        axis = (combo_stats.get(axis_key) or {}).get(bucket_key)
        if not axis:
            continue
        _consume(axis.get("ev_top_combos"), f"{axis_key[3:]}={bucket_key}")

    sorted_combos = sorted(candidates.items(), key=lambda kv: kv[1][0], reverse=True)
    return [(combo, ev, avg_pay, "/".join(srcs[:2])) for combo, (ev, avg_pay, srcs) in sorted_combos]


_NATIONAL_WIN_FREQ_CACHE: list[float] | None = None
# ハードコードの旧値。実測(79,867R)と大きくズレていたので既定では使わない。
#   枠1 0.559→0.545 / 枠2 0.176→0.136 / 枠3 0.092→0.128
#   枠4 0.070→0.101 / 枠5 0.054→0.060 / 枠6 0.046→0.031
# これを分母に使うと、会場の特性と無関係に**全会場で枠2を0.77倍に潰し、
# 枠3-4を1.4倍に持ち上げる**系統的な歪みが入る。出典不明の定数を分母にしないこと。
_NATIONAL_WIN_FREQ_FALLBACK = [0.545, 0.136, 0.128, 0.101, 0.060, 0.031]


def _national_win_freq() -> list[float]:
    """全国の枠別1着率。data/stats/_all_combo_freq.json（会場別と同じ生成物）から取る。

    分子(会場別)と分母(全国)を同じデータ源・同じ期間から取ることで、
    定義や集計期間の食い違いによる系統誤差が入らないようにする。
    """
    global _NATIONAL_WIN_FREQ_CACHE
    if _NATIONAL_WIN_FREQ_CACHE is None:
        path = DATA_DIR / "stats" / "_all_combo_freq.json"
        vals = None
        try:
            wf = json.loads(path.read_text(encoding="utf-8")).get("win_freq") or {}
            vals = [float(wf.get(str(i + 1), 0) or 0) for i in range(6)]
            if not all(v > 0 for v in vals):
                vals = None
        except Exception:
            vals = None
        if vals is None:
            print(f"[WARN] 全国の枠別1着率が読めない: {path} → 既定値で代用")
            vals = list(_NATIONAL_WIN_FREQ_FALLBACK)
        _NATIONAL_WIN_FREQ_CACHE = vals
    return _NATIONAL_WIN_FREQ_CACHE


def _get_venue_win_freq_mod(jcd: str) -> list[float]:
    """
    会場別 combo_freq の win_freq（各枠の実測1着率）を全国平均比に変換して返す。
    course_advantage へのブレンド用補正係数 [1枠..6枠]。データなしなら [1.0]*6。

    例: 福岡(22) 1枠56.6% vs 全国平均約56% → 約1.01、6枠2.7% vs 4.6% → 約0.59
    """
    stats = load_combo_stats(jcd)
    if not stats or "win_freq" not in stats:
        return [1.0] * 6
    wf = stats["win_freq"]
    national = _national_win_freq()
    races = int(stats.get("total_races", 0) or 0)

    # 観測数に応じて中立(1.0)へ縮める。
    # 外枠ほど1着が少なく、比が暴れる。期間を前後半に割って測ると
    #   枠1 r=0.903(最大差0.07) → 枠6 r=0.480(最大差0.52)
    # と、枠6は会場あたり約93勝しかなくほぼノイズになる。
    # 縮小率 w = 勝ち数/(勝ち数+SHRINK_K)。枠1は w≈0.95 でほぼ素通し、
    # 枠6は w≈0.48 で半分ほど中立に寄る。
    SHRINK_K = 100.0
    mods = []
    for i in range(6):
        v = float(wf.get(str(i + 1), 0) or 0)
        na = national[i]
        if v <= 0 or na <= 0:
            mods.append(1.0)
            continue
        wins = v * races
        w = wins / (wins + SHRINK_K) if races else 0.0
        mods.append(round(1.0 + (v / na - 1.0) * w, 4))
    return mods

BASE_DIR                  = Path(__file__).parent.parent
DATA_DIR                  = BASE_DIR / "data"
VENUE_FILE                = DATA_DIR / "venues" / "venue_characteristics.json"
TOURNAMENT_GRADES_FILE    = DATA_DIR / "tournament_grades.json"
OFFICIAL_COURSE_STATS_FILE= DATA_DIR / "venues" / "official_course_stats.json"
CONFIG_FILE               = BASE_DIR / "config.json"

# 会場名辞書（config.json から読む。失敗時は空）
def _load_venue_names():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f).get("venues", {})
    except Exception:
        return {}
VENUE_NAMES = _load_venue_names()

# ── 公式コース統計（v5.4）────────────────────────────────────────
# scrape_stadium_data.py で取得した boatrace.jp 公式の会場別・季節別コース1着率
# 全国平均との比率を venue_course_mod として calc_venue_course_mod() に適用する
_OFFICIAL_STATS_DATA: dict = {}

# 全国平均（24会場の中央値、scrape_stadium_data.py 取得ベース）
_NATIONAL_AVG_COURSE_WIN: dict[str, list[float]] = {
    "spring": [55.9, 17.6, 9.2, 7.0, 5.4, 4.6],
    "summer": [53.9, 17.4, 9.5, 7.4, 6.4, 5.0],
    "autumn": [55.5, 17.5, 9.0, 6.9, 6.0, 4.8],
    "winter": [56.5, 16.9, 9.0, 7.2, 5.7, 4.5],
}


def _load_official_course_stats():
    """official_course_stats.json を読み込んで _OFFICIAL_STATS_DATA に格納"""
    global _OFFICIAL_STATS_DATA
    try:
        with open(OFFICIAL_COURSE_STATS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        _OFFICIAL_STATS_DATA = raw.get("venues", {})
    except Exception:
        _OFFICIAL_STATS_DATA = {}

_load_official_course_stats()


def get_official_seasonal_course_mod(jcd: str, season: str) -> list[float]:
    """
    官公式データ（boatrace.jp/data/stadium）から
    当会場・当季節の「全国平均比 コース補正係数」を返す。

    計算式:
      mod[i] = venue_win_pct[i] / national_avg_win_pct[i]

    データなし / 精度不足の場合は [1.0]*6 を返す。

    例: 福岡(22)春 → [60.2/55.9, 13.0/17.6, ...] ≒ [1.077, 0.739, ...]
    """
    venue_data = _OFFICIAL_STATS_DATA.get(jcd, {})
    seasonal   = venue_data.get("seasonal", {})
    s_data     = seasonal.get(season, {})
    pct        = s_data.get("course_win_pct", [])

    if len(pct) != 6:
        return [1.0] * 6

    national_avg = _NATIONAL_AVG_COURSE_WIN.get(season, [55.9, 17.6, 9.2, 7.0, 5.4, 4.6])
    mods = []
    for i in range(6):
        na = national_avg[i]
        if na > 0 and pct[i] > 0:
            mods.append(round(pct[i] / na, 4))
        else:
            mods.append(1.0)
    return mods


# ── 大会グレード別コース補正 (v5.3) ─────────────────────────────
def _load_tournament_grades():
    """data/tournament_grades.json から大会グレード別補正テーブルを読み込む。

    ⚠️ このファイルが無いと get_tournament_grade_mods() は全グレードに対して
       course_mod=[1.0]*6 を返し、**大会グレード補正が丸ごと無効になる**。
       2026-09-05 時点でファイルは存在せず、git にも一度も入っていなかった
       （.gitignore の `data/*` に飲まれていた）。SG/G1 のイン有利増幅も
       レディースのイン弱体も、コード上は存在するのに一度も効いていない。

       同じ事故が `data/venues/`（2026-08-10）でも起きている。**予想の挙動を
       決めるデータは必ず git に載せ、欠けたら黙らずに警告すること。**
    """
    if not TOURNAMENT_GRADES_FILE.exists():
        print(f"[WARN] 大会グレード補正テーブルが無い: {TOURNAMENT_GRADES_FILE}\n"
              f"       全グレードが中立(course_mod=[1.0]*6)で動く。"
              f"再作成は scripts/calibrate_tournament_grades.py")
        return {}
    try:
        with open(TOURNAMENT_GRADES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] 大会グレード補正テーブルを読めない: {e} → 中立で動く")
        return {}

_TOURNAMENT_GRADE_DATA = _load_tournament_grades()

def get_tournament_grade_mods(tournament_grade: str) -> dict:
    """
    大会グレードに対応するコース補正情報を返す。
    Returns:
      {"course_mod": [1.0]*6, "volatility": 1.0, "note": ""}
    """
    grades = _TOURNAMENT_GRADE_DATA.get("grades", {})
    g = grades.get(tournament_grade)
    if g:
        return {
            "course_mod": g.get("course_mod", [1.0]*6),
            "volatility":  g.get("volatility", 1.0),
            "note":        g.get("note", ""),
            "display":     g.get("display", tournament_grade),
        }
    # ladies_tournaments 引き当て
    lt = _TOURNAMENT_GRADE_DATA.get("ladies_tournaments", {}).get(tournament_grade)
    if lt:
        return {
            "course_mod": lt.get("course_mod", [1.0]*6),
            "volatility":  lt.get("volatility", 1.15),
            "note":        lt.get("note", ""),
            "display":     lt.get("display", tournament_grade),
        }
    # フォールバック: 一般
    fallback = grades.get("一般", {})
    return {
        "course_mod": fallback.get("course_mod", [1.0]*6),
        "volatility":  fallback.get("volatility", 1.0),
        "note":        fallback.get("note", ""),
        "display":     "一般",
    }


def is_all_female_race(racers: list) -> bool:
    """
    全選手が女性かどうかを判定する（全員女性 R の検出）。
    混合戦の通常節でも全員女性になることがある。

    判定優先順:
      1. player_stats["gender"] == "F"/"女" で判定
      2. FEMALE_REG_NOS セット（female_players.json）
    racers: score_racer_with_comment を呼ぶ前の racecard["racers"] リスト
            または scored リスト（player_stats キーを含む）
    """
    if not racers:
        return False
    for r in racers:
        reg_no = str(r.get("reg_no", ""))
        # scored リスト経由（player_stats あり）
        ps = r.get("player_stats", {})
        gender = ps.get("gender", "")
        if gender in ("F", "女", "female"):
            continue
        # female_players.json 経由
        if reg_no and reg_no in FEMALE_REG_NOS:
            continue
        # どちらにも該当しない → 男性とみなして False
        if reg_no:   # reg_no が空の場合は判定保留（データ不足）
            return False
    return True


# ── 重み（合計=1.00） ────────────────────────────────────────────
# ── バージョン管理（v5.20〜、予測ロジック変更時に繰り上げ）──
# WEIGHTS 変更 / 主要ロジック変更 / 買い目生成方式変更 等で繰り上げ
# 軽微な表示変更や運用ロジックはバージョンを変えない
PREDICTOR_VERSION = "v5.28"

WEIGHTS = {
    # v5.20 (2026-04-18): 541R breakdown寄与度分析に基づき再配分
    # 効いている指標を強化 / 効かない指標を縮小、合計1.00維持
    # ─ 実績系 ─────────────────────────────────────────────────────
    "global_win_rate":    0.16,   # 寄与+9.0% ↑0.14→0.16 (v5.19)
    "local_win_rate":     0.12,   # 寄与-1.0% ↓0.15→0.12 (v5.19)
    "motor_2rate":        0.08,   # 寄与+0.7% ↓0.11→0.08 (v5.19)
    "boat_2rate":         0.02,   # 寄与-3.5% ↓0.04→0.02 (v5.19)
    # ─ コース・級別 ───────────────────────────────────────────────
    "course_advantage":   0.20,   # 寄与+8.5%(絶対差最大) ↑0.15→0.20 (v5.19)
    "grade_bonus":        0.05,   # 寄与+5.4% ↑0.04→0.05 (v5.19)
    # ─ スタート ───────────────────────────────────────────────────
    "st_score":           0.15,   # 寄与+2.3% ↓0.16→0.15 (v5.19)
    "exhibition_score":   0.06,   # 寄与+1.2% ↓0.07→0.06 (v5.19)
    # ─ 今節調子 ───────────────────────────────────────────────────
    "series_score":       0.02,   # 寄与-0.6%(D案傾向) ↓0.04→0.02 (v5.19)
    "hist_waku_score":    0.09,   # 寄与+14.7% ↑0.04→0.09 (v5.19)
    "comment_score":      0.03,   # 寄与-0.3% 据え置き
    # ─ その他 ─────────────────────────────────────────────────────
    "female_factor":      0.02,   # 本命選定時点でフィルタされるため分散ゼロ ↓0.03→0.02 (v5.19)
}
# 合計 = 0.16+0.12+0.08+0.02+0.20+0.05+0.15+0.06+0.02+0.09+0.03+0.02 = 1.00

# ── 大会種別補正（v5.1 B実装） ──────────────────────────────────
# データ分析結果:
#   優勝戦・準優勝戦: 1枠1着率11.95%  3連単平均払戻¥14,000  → 本命寄り
#   一般戦          : 1枠1着率 中間   3連単平均払戻¥18,300  → 標準
#   予選・その他    : 1枠1着率 7.22%  3連単平均払戻¥19,700  → 荒れやすい
# v5.27 (2026-08-23): 77,852レースの実測から較正し直した。
# 再現手順: python3 scripts/calibrate_race_type_bonus.py
#
# 較正の考え方（手で置いた値との違い）:
#  1. **レース番号の効果を割り戻す**。種別と番号は強く相関する（準優/優勝戦は
#     必ず終盤、進入固定は序盤）。割り戻さないと「終盤だから内が強い」分まで
#     種別の手柄にしてしまい、種別パラメータが番号の代理変数になる。
#     割り戻すことで、この係数は純粋に「番組の組み方」だけを表すようになり、
#     レース番号の効果と独立に扱えるようになる。
#     ⚠️ レース番号の効果自体は現状どこにも入っていない。
#        venue_characteristics.json の race_no_tendency は全会場 1.0 で無効化されて
#        いる（実測値は診断用の _measured_race_no_tendency にのみ格納）。
#        無効化の理由が「RACE_TYPE_BONUS["finalist"] と二重計上になるから」
#        だったので、切り分けが済んだ今は有効化を検討できる状態になった。
#  2. **加重平均を変えない**。type_bonus は course_advantage 全体にかかる係数で
#     勝率とは次元が違う。WEIGHTS["course_advantage"] は変更前の平均 0.9061 を
#     含んだ状態で調整されているはずなので、平均を固定して相対の傾きだけ直す。
#
#  区分          n       1着率   素の比  番号調整後   新     旧
#  qualifier  33,208   45.3%   0.830   0.868    0.788  0.87
#  general    17,133   54.7%   1.002   1.062    0.964  1.00
#  kikaku     10,733   62.5%   1.147   1.192    1.081   なし
#  senbatsu   10,137   65.8%   1.206   1.003    0.910   なし
#  finalist    4,406   70.4%   1.291   1.078    0.977  1.12
#  fixed_entry 2,235   70.4%   1.291   1.352    1.226  1.20
#
# ⚠️ 最大の発見: **準優勝戦・優勝戦が内枠有利に見えるのは、ほぼ全部が
#    「終盤レースは内が強い」という番号効果**だった。素の全体比 1.291 が
#    番号を揃えると 1.078 まで落ちる。種別として上乗せする理由はほとんど無い。
#    逆に、番号では説明できないのが 進入固定(1.352) と 企画レース(1.192)。
#    企画レースは番組が意図的に1号艇を強くしている枠で、R1-4 に限っても
#    予選 0.765 に対し 1.154 と大きく開く。
#
# 区分の効果は前後半で割っても ±0.01 しかぶれない（fixed_entry のみ ±0.033）。
RACE_TYPE_BONUS = {
    "fixed_entry": 1.226,  # 進入固定      : 前づけが無くインが最も強い
    "kikaku":      1.081,  # 会場独自の企画レース: 番組が1号艇を強く組む枠
    "general":     0.964,  # 一般・特賞
    "finalist":    0.977,  # 優勝戦・準優勝戦: 番号効果を除くとほぼ中立
    "senbatsu":    0.910,  # 特選・選抜・ドリーム: 同上（終盤に偏るだけ）
    "qualifier":   0.788,  # 予選          : 実測で最も荒れる（1着率45.3%）
    "unknown":     0.906,  # レース名が取れないとき＝情報なし（全体平均）
}
# v5.25 (2026-08-16): 「進入固定」を最優先で分類する。
# 進入固定戦は前づけが起きないぶんインが最も強く、修復後の results_csv 実測で
#   進入固定 n=2,047 → 1号艇1着 71.2%
#   それ以外 n=69,733 → 1号艇1着 54.7%
# と +16.5pt の差がある。ところが race_name が「予選 進入固定」「一般 進入固定」の
# 形をとるため _RACE_TYPE_QUALIFIER にマッチし、**最も堅いレースに荒れ補正0.87倍を
# 逆向きに当てていた**。判定順を変えるだけで直る。
_RACE_TYPE_FIXED_ENTRY = re.compile(r"進入固定")
# 大会種別キーワードマッチ（race_name = 節内の個別レース種別名 から分類）
# ※ SG/G1/G2/G3 は「大会グレード」であり個別レース種別ではないため除外 [BUG FIX v5.2]
# v5.27 (2026-08-23): 分類を6区分に細分化。
# 旧 qualifier は `予選|一般|…` を1つにまとめており、実測で 予選 42.8% と
# 予選特選 67.7% という 25pt 差の別物を同じ 0.87倍 で扱っていた。
_RACE_TYPE_FINALIST  = re.compile(r"(優勝戦|準優勝戦)")
_RACE_TYPE_SENBATSU  = re.compile(r"(特選|選抜|ドリーム|トライアル|マスターズ|シリーズ)")
_RACE_TYPE_QUALIFIER = re.compile(r"(予選|敗者復活|B級|選考|補充|組合せ|順位決定)")
_RACE_TYPE_GENERAL   = re.compile(r"(一般|特賞)")


def calc_race_style_bonus(waku: int, player_stats: dict) -> float:
    """
    先行/まくり傾向スコアを返す（course_advantage への乗算補正用）。

    考え方:
      外枠（4-6）でも1着を取れる選手（まくり型）は、外枠でも course_advantage を引き下げない
      内枠専用（先行型）の選手は、外枠に置かれるとさらに不利になる

    戻り値: 0.85〜1.15 の乗数
      1.0  = 平均的（補正なし）
      >1.0 = 外枠適性あり（まくり型）
      <1.0 = 外枠不適（先行型が外枠にいる場合）
    """
    waku_stats = player_stats.get("hist_global_waku_stats", {})

    # 内枠（1-3）の平均1着率
    inner_rates = []
    for w in ["1", "2", "3"]:
        ws = waku_stats.get(w)
        if ws and ws.get("races", 0) >= 5:
            inner_rates.append(ws.get("1st_pct", 0.0))

    # 外枠（4-6）の平均1着率
    outer_rates = []
    for w in ["4", "5", "6"]:
        ws = waku_stats.get(w)
        if ws and ws.get("races", 0) >= 5:
            outer_rates.append(ws.get("1st_pct", 0.0))

    if not inner_rates and not outer_rates:
        return 1.0   # データ不足 → 補正なし

    avg_inner = sum(inner_rates) / len(inner_rates) if inner_rates else 0.0
    avg_outer = sum(outer_rates) / len(outer_rates) if outer_rates else 0.0
    total     = avg_inner + avg_outer
    if total == 0:
        return 1.0

    # 外枠比率（0=完全先行型, 1=完全外枠型）
    outer_ratio = avg_outer / total

    if waku >= 4:
        # 外枠に配置: まくり型（outer_ratio高い）ならボーナス、先行型ならペナルティ
        # outer_ratio=0.5 → 補正なし。0.0 → ×0.88、1.0 → ×1.12
        bonus = 0.88 + outer_ratio * 0.24   # [0.88, 1.12]
    else:
        # 内枠に配置: 先行型（inner dominance高い）なら微ボーナス
        inner_ratio = 1.0 - outer_ratio
        bonus = 1.0 + inner_ratio * 0.08    # [1.00, 1.08]

    return round(bonus, 4)


def classify_race_type(race_no: int, race_name: str = "") -> str:
    """
    レース名からレース種別を分類する。
    戻り値: "fixed_entry" | "finalist" | "senbatsu" | "kikaku"
            | "general" | "qualifier" | "unknown"

    判定順が意味を持つ:
      - 「進入固定」は最優先。"予選 進入固定" のように併記されるため、
        後段に回すと qualifier に吸われる
      - 「特選/選抜」は「予選」より先。"予選特選" は実測 67.7% で
        "予選" 42.8% とは別物

    ⚠️ race_no は使わない（v5.27 で廃止）。
    以前は race_name が無いとき 12R→finalist / 11R→general / それ以外→qualifier と
    番号で「種別」を推定していた。これをやめた理由:
      - 12R が優勝戦なのは節の最終日だけで、実測では 12R のうち優勝戦・準優勝戦は
        29.3% しかない。7割は外している
      - 番号の効果と種別の効果は別物なので、種別の係数で番号を代理させると
        どちらも正しく較正できない
    実測でも、番号帯を揃えると準優勝戦・優勝戦の「種別としての」上乗せは
    ほぼ消える（素の全体比 1.291 → 番号調整後 1.078）。
    名前が取れないときは "unknown"（＝情報なし・全体平均）に倒す。
    なお scraper 側の抽出漏れ（24.9%が空）は v5.27 で直したので、
    実運用で unknown に落ちるのは休催・ページ異常時くらいのはず。
    """
    name = (race_name or "").strip()
    if not name:
        return "unknown"
    if _RACE_TYPE_FIXED_ENTRY.search(name):
        return "fixed_entry"
    if _RACE_TYPE_FINALIST.search(name):
        return "finalist"
    if _RACE_TYPE_SENBATSU.search(name):
        return "senbatsu"
    if _RACE_TYPE_QUALIFIER.search(name):
        return "qualifier"
    if _RACE_TYPE_GENERAL.search(name):
        return "general"
    # どのキーワードにも当たらない＝会場独自の企画レース名
    # （ウインウイン / ランチタイム / サンライズ / エイトビート 等）。
    # 番組が意図的に1号艇を強くする枠で、番号調整後も 1.19倍と最も効く区分のひとつ。
    return "kikaku"


# ── 女性選手リスト ────────────────────────────────────────────────
FEMALE_PLAYERS_FILE = DATA_DIR / "players" / "female_players.json"
MASTER_FILE        = DATA_DIR / "players" / "master.json"

def _load_female_reg_nos() -> set:
    """
    女性選手の登録番号セットを返す。
    優先: data/players/master.json["players"] の gender=="F"
    フォールバック: data/players/female_players.json["reg_nos"]
    """
    # master.json が存在すればそちらを正源とする
    master = load_json(MASTER_FILE)
    if master and "players" in master:
        return {rn for rn, info in master["players"].items() if info.get("gender") == "F"}
    # フォールバック
    d = load_json(FEMALE_PLAYERS_FILE)
    if d:
        return set(str(r) for r in d.get("reg_nos", []))
    return set()

def _load_player_name(reg_no: str) -> str | None:
    """
    master.json から選手の漢字氏名を返す。なければ None。
    """
    master = load_json(MASTER_FILE)
    if master and "players" in master:
        info = master["players"].get(str(reg_no))
        if info:
            return info.get("name_kanji")
    return None

FEMALE_REG_NOS: set = set()  # load_json 定義後に populate（後述）

# ── コメントキーワード辞書（delta値: 正=良い足 / 負=悪い足） ───
# ※ スコアは全マッチの合計。重複しやすい短いキーは意図的に弱めに設定。
# ※ 「合ってい」は誤ネガ（体感は合っている等）を防ぐため削除済み。
COMMENT_KEYWORDS = {
    # ── 強ポジティブ (+0.15〜+0.20) ────────────────────────────────────
    "最高":              0.20, "完璧":          0.20, "抜群":           0.20,
    "一番良":            0.20, "ピカイチ":      0.20,
    "良くなっ":          0.18, "上向き":        0.18,
    "合ってき":          0.18, "いい感じ":      0.18, "良い感じ":       0.18,
    "よさそう":          0.08, "良さそう":      0.08,
    "まとまっ":          0.15, "余裕がある":    0.15,
    "上々":              0.14,
    # ── ポジティブ（足・エンジン系, +0.08〜+0.14） ─────────────────────
    "足がいい":          0.15, "足はいい":      0.15, "足は良":        0.14,
    "出足がいい":        0.14, "出足はいい":    0.14, "出足は良":      0.14,
    "回り足がいい":      0.14, "まわり足は良":  0.14,
    "ターン回りがいい":  0.14, "ターン回りは良": 0.14,
    "レース足はいい":    0.14, "押し感":        0.12,
    "押していた":        0.12, "前に押して":    0.12,
    "伸びがいい":        0.14, "伸びはいい":    0.14,  # 新追加
    "伸びが良":          0.12, "伸びは良":      0.12,
    "伸びが上向":        0.16,
    "伸びはある":        0.10, "足はある":      0.10,  # 新追加
    "直線はいい":        0.10, "出足もある":    0.10,  # 新追加
    "エンジンはいい":    0.10, "バランスも取れて": 0.14,
    "出足からのつながりがいい": 0.12,
    "スリットから出":    0.12,                         # 新追加: 好発進表現
    "出ていく":          0.10, "申し分ない":    0.16,
    "問題ない":          0.10, "しっかりしている": 0.10,
    "普通に":            0.04, "乗り心地がいい": 0.06, "しのげている": 0.06,
    "ケツを振るのはなくなった": 0.08, "ケツも振らなかった": 0.08,
    "バランスが取れて":  0.14, "バランス取れて": 0.14,
    "乗りやすさがある":  0.10, "ゾーンが広い":  0.12,
    "力強さはある":      0.12,
    # ── 中程度ポジティブ (+0.06〜+0.10) ────────────────────────────────
    "悪くない":          0.10, "悪くは":        0.10,
    "まずまず":          0.10, "そこそこ":      0.08,
    "普通はある":        0.06, "いける":        0.10,  # 新追加
    "そんなに悪く":      0.08,                         # 新追加: そんなに悪くない
    "良かった":          0.10,
    # ── 軽いネガティブ (-0.06〜-0.12) ─────────────────────────────────
    "少し悪":           -0.10, "少し弱":       -0.10, "少し足り":      -0.10,
    "少し甘い":         -0.08, "出足が少し甘い": -0.08, "出足は少し甘い": -0.08,
    "不安":             -0.08, "気になる":     -0.06, "△":             -0.08,
    "回り過ぎ":         -0.10,                         # 新追加
    "乗りづらい":       -0.10, "乗りづらく":   -0.10, "乗りづらさ":   -0.10,
    "ケツを振る":       -0.08, "ケツ振る":     -0.08, "ケツを振って": -0.08,
    "ケツは振る":       -0.08,
    "回っていない":     -0.10, "回っていなく": -0.10, "ずれる":       -0.05, "ずれている":   -0.05,
    "乗り心地はいつもとは違う": -0.06,
    "重い":             -0.12, "重たい":       -0.12,  # 新追加
    "難しい":           -0.08, "直線が安定しない": -0.08,
    # ── 強ネガティブ (-0.12〜-0.20) ────────────────────────────────────
    "全く合":           -0.20, "全く良":       -0.20, "全部の足":      -0.18,
    "合っていない":     -0.18, "なかなか合わ": -0.15,  # 新追加
    "良くない":         -0.15, "足が弱":       -0.15, "足が悪":        -0.15,
    "弱い":             -0.12, "悪い":         -0.12,
    "ダメ":             -0.15, "おかしい":     -0.15, "劣勢":          -0.12,
    "進まない":         -0.12, "伸びない":     -0.12, "回らない":      -0.12,
    "下がっていた":     -0.14, "下がっていました": -0.14,
    "出ていない":       -0.15, "十分ではない": -0.12,
    "パンチがない":     -0.12, "気になるが":   -0.06,
    "ペラ調整を失敗":   -0.15, "相手には下がる": -0.10,
    "合っていなかった": -0.15, "すごく悪かった": -0.14,
    "直らない":         -0.12, "治らない":     -0.12,
    "反省点":           -0.10, "反省":         -0.08, "突破できなかった": -0.12,
    "伴っていない":     -0.06,
    "差がある":         -0.06, "不完全燃焼":   -0.06,
    "下がることはない":  0.06,
    "厳し":             -0.15,                         # 新追加: 厳しい・厳しかった両方にマッチ
    "売り切れ":         -0.15,                         # 新追加
    "スカっ":           -0.12, "スカった":     -0.12,  # 新追加
    "スカッ":           -0.12,                         # 新追加（全角）
    "良くなら":         -0.12,                         # 新追加: 良くならない
    "出遅れ":           -0.12,                         # 新追加
    "辛い":             -0.10, "辛かっ":       -0.10,  # 新追加
    "つらい":           -0.10,
}

COMMENT_KEYWORD_ITEMS = sorted(
    COMMENT_KEYWORDS.items(),
    key=lambda item: (-len(item[0]), -abs(item[1]), item[0]),
)

GRADE_SCORE       = {"A1": 1.0, "A2": 0.75, "B1": 0.5, "B2": 0.25}
COURSE_BASE_SCORE = {1: 1.00, 2: 0.55, 3: 0.45, 4: 0.40, 5: 0.30, 6: 0.25}


# ── ユーティリティ ───────────────────────────────────────────────
def safe_float(val, default=0.0):
    try:
        return float(str(val).replace("%","").replace("秒","").strip())
    except:
        return default


def match_comment_keywords(text: str) -> list[dict]:
    """
    コメント本文からキーワード一致を抽出する。
    長い語を優先し、重なった短語は採用しない。
    例: 「少し弱い」では「少し弱」を採用し、「弱い」は重複評価しない。
    """
    if not text:
        return []

    candidates = []
    for kw, delta in COMMENT_KEYWORD_ITEMS:
        start = text.find(kw)
        while start != -1:
            end = start + len(kw)
            candidates.append({
                "keyword": kw,
                "delta": round(delta, 2),
                "start": start,
                "end": end,
                "length": len(kw),
            })
            start = text.find(kw, start + 1)

    candidates.sort(key=lambda item: (-item["length"], item["start"], -abs(item["delta"])))

    occupied = [False] * len(text)
    selected = []
    for item in candidates:
        if any(occupied[i] for i in range(item["start"], item["end"])):
            continue
        for i in range(item["start"], item["end"]):
            occupied[i] = True
        selected.append(item)

    selected.sort(key=lambda item: item["start"])
    return selected


def score_comment_text(text: str) -> tuple[float, list[dict]]:
    """コメント本文をスコア化して、採用キーワード一覧も返す。"""
    score = 0.5
    matched_keywords = match_comment_keywords(text)
    for item in matched_keywords:
        score += item["delta"]
    return round(max(0.0, min(1.0, score)), 4), matched_keywords

def load_json(path):
    p = Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None

def load_racecard(jcd, date, race_no):
    path = DATA_DIR / "racecards" / date / f"{jcd}_R{race_no:02d}.json"
    d = load_json(path)
    if not d:
        print(f"[WARN] 出走表が見つかりません: {path}")
    return d

def load_player_stats(reg_no):
    return load_json(DATA_DIR / "players" / f"{reg_no}.json") or {}

def load_motor_stats(jcd, motor_no):
    return load_json(DATA_DIR / "motors" / f"{jcd}_{motor_no}.json") or {}

def load_exhibition(jcd, date, race_no):
    data = load_json(DATA_DIR / "raw" / date / f"{jcd}_R{race_no:02d}_exhibition.json")
    if not data:
        return None

    rows = []
    for row in data.get("exhibition", []) or []:
        ex_time = row.get("exhibition_time", "")
        try:
            float(str(ex_time).strip())
        except (TypeError, ValueError):
            straight_time = row.get("straight_time", "")
            try:
                float(str(straight_time).strip())
                ex_time = straight_time
            except (TypeError, ValueError):
                ex_time = ""
        rows.append({
            "waku": row.get("waku"),
            "exhibition_time": ex_time,
            "tilt": row.get("tilt", ""),
            "entry_course": row.get("entry_course", ""),
            "start_timing": row.get("start_timing", row.get("exhibition_st", "")),
            "handicap_dist": row.get("handicap_dist", ""),
            "prev_rank": row.get("prev_rank", ""),
        })
    data["exhibition"] = rows
    return data

def load_weather(jcd, date, race_no):
    return load_json(DATA_DIR / "weather" / date / f"{jcd}_R{race_no:02d}.json")

def load_comments(jcd, date, race_no):
    return load_json(DATA_DIR / "comments" / date / f"{jcd}_R{race_no:02d}.json")

def load_pitreport(jcd, date, race_no):
    """公式ピットレポート（全会場・R7-12）を読み込む"""
    return load_json(DATA_DIR / "player_comments" / date / f"{jcd}_R{race_no:02d}_pitreport.json")

def load_engine_report(jcd, date):
    """会場公式サイトのエンジン通信簿（大村 etc.）を読み込む"""
    return load_json(DATA_DIR / "motors" / date / f"{jcd}_engine_report.json")

def load_player_review(jcd, date):
    """会場公式サイトの選手短評を読み込む"""
    return load_json(DATA_DIR / "player_comments" / date / f"{jcd}_player_review.json")

def load_tide(jcd, date):
    """気象庁から取得した潮汐データ（fetch_tide.py で生成）を読み込む"""
    return load_json(DATA_DIR / "tides" / date / f"{jcd}_tide.json")

def load_odds(jcd, date, race_no):
    """3連単オッズを読み込む"""
    return load_json(DATA_DIR / "odds" / date / f"{jcd}_R{race_no:02d}.json")

def load_player_comments_history(reg_no):
    """選手のコメント履歴 (data/player_comments/{reg_no}.json) を読み込む"""
    return load_json(DATA_DIR / "player_comments" / f"{reg_no}.json") or []

def _init_female_players():
    global FEMALE_REG_NOS
    d = load_json(FEMALE_PLAYERS_FILE)
    FEMALE_REG_NOS = set(str(r) for r in d.get("reg_nos", [])) if d else set()

_init_female_players()  # load_json 定義直後に実行


def load_venue_data(jcd):
    data = load_json(VENUE_FILE)
    if not data:
        return None
    return data.get(jcd) or data.get("_default")

def get_season(date_str):
    month = int(date_str[4:6])
    if month in [3,4,5]:   return "spring"
    if month in [6,7,8]:   return "summer"
    if month in [9,10,11]: return "autumn"
    return "winter"

def get_race_period(race_no):
    if race_no <= 4:  return "early"
    if race_no <= 8:  return "middle"
    return "late"

def get_wind_direction(weather):
    if not weather: return ""
    return weather.get("風向","") or weather.get("wind_dir","")

def get_wind_speed(weather):
    if not weather: return 0.0
    return safe_float(weather.get("風速",0) or weather.get("wind_speed",0))

def get_wind_summary(weather, venue=None) -> str | None:
    """
    風況を一言で返す（出力ファイルへの表示用）。
    例: "北3m — 向かい風（1コース注意・アウト有利）"
        "南5m — 追い風（まくり注意・インが逃げやすい）"
        "東2m — 横風（影響小）"
        "0m — 無風"
    データなし → None
    """
    if not weather:
        return None
    speed     = get_wind_speed(weather)
    direction = get_wind_direction(weather)
    if not direction and speed == 0.0:
        return None

    wind_cfg  = (venue or {}).get("wind", {})
    threshold = wind_cfg.get("headwind_threshold_ms", 4)
    spd_str   = f"{direction}{int(speed)}m" if direction else f"{int(speed)}m"

    if speed < 1:
        return f"{spd_str} — 無風（影響なし）"
    elif speed < threshold:
        return f"{spd_str} — 微風（影響小）"

    # 強風：向き判定
    headwind = any(d in direction for d in ["北","北東","北西","N","NE","NW"])
    tailwind = any(d in direction for d in ["南","南東","南西","S","SE","SW"])
    if headwind:
        return f"{spd_str} ⚡向かい風 — 1コース注意・アウト有利"
    elif tailwind:
        return f"{spd_str} ⚡追い風 — まくり注意・インが逃げやすい"
    else:
        return f"{spd_str} — 横風（スタート乱れやすい）"

def get_tide_status(weather, tide_data=None, race_no=None):
    """
    潮汐ステータスを返す。
    優先順位: ①気象庁潮汐データ(tide_data) > ②weather(展示スクレイプ時の実測値)
    """
    # ① 気象庁データが利用可能な場合
    if tide_data and race_no is not None:
        rt = tide_data.get("race_tides", {}).get(str(race_no), {})
        status = rt.get("status")
        if status:
            return status

    # ② 展示スクレイプ時の気象情報にフォールバック
    if not weather:
        return None
    tide = weather.get("潮汐") or weather.get("tide") or ""
    mapping = {
        "満潮":"high_tide","干潮":"low_tide",
        "上げ":"rising_tide","下げ":"falling_tide",
    }
    for k,v in mapping.items():
        if k in tide: return v
    return None

def get_tide_info(tide_data, race_no):
    """レース番号に対応する潮汐情報を返す（表示用）"""
    if not tide_data or not race_no:
        return {}
    return tide_data.get("race_tides", {}).get(str(race_no), {})


# ── 進入コース取得ヘルパー（v5.2）────────────────────────────────
def get_actual_entry_course(waku: int, exhibition_data) -> int:
    """
    展示データから当該枠番の実際の進入コースを返す。
    データなし・取得不可の場合は waku をそのまま返す。
    """
    if not exhibition_data:
        return waku
    for e in exhibition_data.get("exhibition", []):
        if int(e.get("waku", 0)) == waku:
            ec = e.get("entry_course")
            if ec is not None:
                try:
                    return int(ec)
                except (ValueError, TypeError):
                    pass
    return waku


# ── 会場特性コース補正 ────────────────────────────────────────────
def calc_venue_course_mod(waku, jcd, race_no, date_str, weather, venue, tide_data=None):
    idx  = waku - 1
    base = COURSE_BASE_SCORE.get(waku, 0.2)
    if not venue:
        return base

    season = get_season(date_str)

    # ── 季節補正: 公式データ優先、なければ venue_characteristics の推定値 ──
    official_mods = get_official_seasonal_course_mod(jcd, season)
    if any(m != 1.0 for m in official_mods):
        # 公式実測データあり → 全国平均比で補正
        base *= official_mods[idx]
    else:
        # フォールバック: 手動設定の推定値
        s_mods = venue.get("seasonal",{}).get(season,{}).get("course_mod",[1.0]*6)
        base  *= s_mods[idx] if idx < len(s_mods) else 1.0

    period   = get_race_period(race_no)
    p_mods   = venue.get("race_no_tendency",{}).get(period,{}).get("course_mod",[1.0]*6)
    base    *= p_mods[idx] if idx < len(p_mods) else 1.0

    if venue.get("tidal") and venue.get("tidal_conditions"):
        tide = get_tide_status(weather, tide_data=tide_data, race_no=race_no)
        if tide:
            t_mods = venue["tidal_conditions"].get(tide,{}).get("course_mod",[1.0]*6)
            base  *= t_mods[idx] if idx < len(t_mods) else 1.0

    wind_speed = get_wind_speed(weather)
    wind_dir   = get_wind_direction(weather)
    wind_cfg   = venue.get("wind",{})
    threshold  = wind_cfg.get("headwind_threshold_ms", 4)
    if wind_speed >= threshold:
        headwind = any(d in wind_dir for d in ["北","北東","北西","N","NE","NW"])
        tailwind = any(d in wind_dir for d in ["南","南東","南西","S","SE","SW"])
        if headwind:
            hw_mods = wind_cfg.get("headwind_course_mod",[1.0]*6)
            base   *= hw_mods[idx] if idx < len(hw_mods) else 1.0
        elif tailwind:
            tw_mods = wind_cfg.get("tailwind_course_mod",[1.0]*6)
            base   *= tw_mods[idx] if idx < len(tw_mods) else 1.0

    # ── v5.13 (1-C): 会場実測 win_freq を 25% の重みでブレンド ─────────
    # 公式季節補正が主で、会場固有の長期実測は弱め補正（外乱を避けるため）
    win_freq_mods = _get_venue_win_freq_mod(jcd)
    if win_freq_mods[idx] != 1.0:
        blend = 0.25
        base *= (1.0 - blend) + blend * win_freq_mods[idx]

    return round(base, 5)


# ── STスコア ─────────────────────────────────────────────────────
def calc_st_score(racer, player_stats):
    # 実績 > 出走表の avg_st > デフォルト の優先順で取得
    hist_st  = player_stats.get("hist_avg_st",{})
    avg_st   = (
        hist_st.get("avg_st")                       # build_stats で集計した実績ST
        or racer.get("avg_st")                      # 出走表に記載のST
        or player_stats.get("st_平均ST")            # プロフィールページのST
        or 0.18
    )
    avg_st = safe_float(avg_st, 0.18)

    if avg_st <= 0.10:   st_score = 1.0
    elif avg_st >= 0.25: st_score = 0.0
    else:                st_score = 1.0 - (avg_st - 0.10) / 0.15

    penalties = player_stats.get("penalties", [])
    f_count   = sum(int(safe_float(p.get("F数",0))) for p in penalties[:2])
    l_count   = sum(int(safe_float(p.get("L数",0))) for p in penalties[:2])
    penalty   = min(f_count * 0.15 + f_count * max(f_count-1,0) * 0.10 + l_count * 0.05, 0.50)
    return round(max(st_score - penalty, 0.0), 4)


# ── 展示スコア ───────────────────────────────────────────────────
def calc_exhibition_score(waku, exhibition_data, player_stats=None, jcd: str = ""):
    """
    展示タイム（直線スピード）の相対スコア。最速=1.0、最遅=0.0

    優先順位:
      1) 当日展示が取れている場合: 全6艇の相対ランキング
      2) 取れていない場合: player_stats["hist_exhibition"]["recent_deviation"] を form 指標として使用
         - recent_deviation < -0.05 (会場平均より速い) → 高スコア
         - recent_deviation > +0.05 (会場平均より遅い) → 低スコア
    """
    if exhibition_data:
        times = {}
        for e in exhibition_data.get("exhibition", []):
            w = int(safe_float(e.get("waku", 0)))
            t = safe_float(e.get("exhibition_time", 0))
            if w > 0 and t > 0:
                times[w] = t
        if times and waku in times:
            mn, mx = min(times.values()), max(times.values())
            if mx - mn >= 0.01:
                return round(1.0 - (times[waku] - mn) / (mx - mn), 4)

    # フォールバック: 直近偏差から form 指標
    if player_stats:
        hist_ex = player_stats.get("hist_exhibition") or {}
        dev = hist_ex.get("recent_deviation")
        if dev is not None:
            # -0.05 → 1.0, 0 → 0.5, +0.05 → 0.0 にマップ
            score = 0.5 - dev * 10.0
            return round(max(0.0, min(1.0, score)), 4)
    return 0.5

def calc_exhibition_st_score(waku, exhibition_data):
    """スタート展示のSTスコア。start_timing フィールドを優先使用（旧 exhibition_st は廃止）"""
    if not exhibition_data: return 0.5
    for e in exhibition_data.get("exhibition", []):
        if int(safe_float(e.get("waku",0))) == waku:
            # 新フィールド: start_timing（例: ".11" → 0.11秒）
            st_raw = e.get("start_timing", "")
            if st_raw:
                # ".11" 形式や "0.11" 形式に対応
                st_str = st_raw.lstrip(".")
                est = safe_float("0." + st_str if not st_raw.startswith("0") and "." in st_raw else st_raw)
            else:
                est = 0.18  # 中立デフォルト
            if est <= 0.10: return 1.0
            if est >= 0.25: return 0.0
            return round(1.0 - (est - 0.10) / 0.15, 4)
    return 0.5

def calc_tilt_score(waku, exhibition_data):
    """
    チルト角度スコア（係数は exhibition_score 内で使用）
    チルト -0.5 = スピード重視 → ストレート有利
    チルト +1.0 = ターン重視 → まくり型に有利
    内枠ではマイナスチルト有利、外枠ではプラスチルト有利の傾向あり
    → シンプルにマイナスチルト ≒ エンジン好調サイン として扱う
    """
    if not exhibition_data: return 0.5
    tilts = {}
    for e in exhibition_data.get("exhibition", []):
        w = int(safe_float(e.get("waku", 0)))
        t = safe_float(e.get("tilt", 999))
        if w > 0 and t != 999:
            tilts[w] = t
    if not tilts or waku not in tilts: return 0.5
    # チルトが低い（マイナス側）ほどスコア高い（スピード重視セッティング）
    mn, mx = min(tilts.values()), max(tilts.values())
    if mx - mn < 0.1: return 0.5
    return round(1.0 - (tilts[waku] - mn) / (mx - mn), 4)


# ── 女性レーサー係数（v5.0 NEW） ─────────────────────────────────
def is_female(reg_no: str, player_stats: dict) -> bool:
    """
    女性レーサーかどうかを判定する。
    優先順: ① player_stats["gender"] == "F" / "女"
            ② FEMALE_REG_NOS セット（data/players/female_players.json）
    """
    gender = player_stats.get("gender", "")
    if gender in ("F", "女", "female"):
        return True
    return str(reg_no) in FEMALE_REG_NOS


def calc_female_factor(reg_no: str, player_stats: dict, weather) -> float:
    """
    女性レーサーの混合戦補正スコアを返す（0.0〜1.0、中立=0.50）。

    男性レーサー → 0.50（ニュートラル）
    女性レーサー → 条件に応じた値:
      - 強風 (>=4m/s) または高波 (>=15cm):  0.20  → 貢献 -0.012（最大ペナルティ）
      - 中程度 (風2〜4m/s または波10〜14cm): 0.35  → 貢献 -0.006
      - 穏やか (風<2m/s かつ波<10cm):        0.50  → 変化なし

    ※ 女性の実力はすでに勝率・STスコアに反映されている。
      本係数は「男性との体力差が顕在化しやすい荒天時」の追加補正のみを担う。
    """
    if not is_female(reg_no, player_stats):
        return 0.50  # 男性: ニュートラル

    wind  = get_wind_speed(weather) if weather else 0.0
    wave  = safe_float((weather or {}).get("波高", (weather or {}).get("wave_cm", 0)), 0.0)

    if wind >= 4.0 or wave >= 15.0:
        return 0.20   # 強風・高波 → ペナルティ大
    elif wind >= 2.0 or wave >= 10.0:
        return 0.35   # 中程度 → 軽微なペナルティ
    else:
        return 0.50   # 穏やか → ニュートラル（女性の精密さが活きる）


# ── 当地・当枠の実績1着率スコア（NEW） ───────────────────────────
def calc_hist_waku_score(waku, player_stats):
    """
    当地でその枠に入ったときの1着率を 0〜1 に正規化して返す
    データなし → 0.5（中立値）
    """
    local_ws = player_stats.get("hist_local_waku_stats", {})
    wdata    = local_ws.get(str(waku))
    if not wdata or wdata.get("races", 0) < 3:
        # データ不足時は全国を参照
        global_ws = player_stats.get("hist_global_waku_stats", {})
        wdata     = global_ws.get(str(waku))
    if not wdata or wdata.get("races", 0) < 3:
        return 0.5  # データ不足はニュートラル
    win_pct = wdata.get("1st_pct", 0.0)  # 0〜100
    # 全体平均を 16.7%（1/6） として正規化
    normalized = min(win_pct / 33.3, 1.0)  # 33.3%で上限1.0
    return round(normalized, 4)


# ── コメント履歴トレンド補正（v4.2） ────────────────────────────
def calc_comment_history_bonus(reg_no: str, current_score: float) -> float:
    """
    過去コメント履歴から「継続的な良調子/悪調子」を検出して補正を加える。
    直近3件以上のコメントが一方向に揃っている場合のみ適用。
    返値: 補正delta （例: +0.05 or -0.05）
    """
    history = load_player_comments_history(reg_no)
    if len(history) < 3:
        return 0.0

    # 直近3件のコメントをスコア化
    recent = sorted(history, key=lambda x: (x.get("date",""), x.get("race_no",0)), reverse=True)[:3]
    recent_scores = []
    for rec in recent:
        text = rec.get("comment", "")
        s, _ = score_comment_text(text)
        recent_scores.append(s)

    if not recent_scores:
        return 0.0

    avg_hist = sum(recent_scores) / len(recent_scores)
    # 3件とも0.55以上 → 継続的な好調 → +0.05
    if all(s >= 0.55 for s in recent_scores) and current_score >= 0.55:
        return 0.05
    # 3件とも0.45以下 → 継続的な不調 → -0.05
    if all(s <= 0.45 for s in recent_scores) and current_score <= 0.45:
        return -0.05
    # 前回悪く今日良い → 反発 +0.03
    if recent_scores[0] <= 0.45 and current_score >= 0.60:
        return 0.03
    return 0.0


def _parse_motor_eval_points(comment_data: dict, waku: int) -> float | None:
    """
    comment_data から motor_eval_text を読み、「N点」形式のモーター評価を
    スコアボーナス（-0.30 〜 +0.25）に変換して返す。
    大村（1-7点制）: 7→+0.25 / 6→+0.15 / 5→+0.05 / 4→0.0 / 3→-0.10 / 2→-0.20 / 1→-0.30
    データなしなら None。
    """
    if not comment_data:
        return None
    wdata = comment_data.get("comments", {}).get(str(waku)) or \
            comment_data.get("comments", {}).get(waku)
    if not wdata:
        return None
    motor_text = wdata.get("motor_eval_text", "")
    if not motor_text:
        return None
    m = re.search(r"(\d)点", motor_text)
    if not m:
        return None
    pts = int(m.group(1))
    # 大村は1-7点制、唐津など他会場も同様の場合は合わせて使える
    bonus_map = {7: 0.25, 6: 0.15, 5: 0.05, 4: 0.0, 3: -0.10, 2: -0.20, 1: -0.30}
    return bonus_map.get(pts, 0.0)


def explain_comment_score(waku: int, comment_data: dict, pitreport_data: dict = None,
                          player_review: dict = None, reg_no: str = "") -> dict:
    """
    コメントスコアの内訳を返す。
    戻り値: {
      text, source, base_score, matched_keywords, raw_score, final_label,
      motor_eval_bonus (optional)
    }
    """
    text, source = get_comment_text_with_review(
        waku, comment_data, pitreport_data=pitreport_data,
        player_review=player_review, reg_no=reg_no
    )
    if not text:
        # テキストがなくてもモーター評価点だけで判定できる場合がある
        motor_bonus = _parse_motor_eval_points(comment_data, waku)
        if motor_bonus is not None:
            score = 0.5 + motor_bonus
            label = "▲" if score > 0.55 else ("▼" if score < 0.45 else "―")
            return {
                "text": "",
                "source": "モーター評価（番記者）",
                "base_score": 0.5,
                "matched_keywords": [f"モーター評価{motor_bonus:+.2f}"],
                "raw_score": round(max(0.0, min(1.0, score)), 4),
                "final_label": label,
                "motor_eval_bonus": motor_bonus,
            }
        return {
            "text": "",
            "source": "",
            "base_score": 0.5,
            "matched_keywords": [],
            "raw_score": 0.5,
            "final_label": "―",
        }

    score, matched_keywords = score_comment_text(text)

    # v5.16: モーター評価点ボーナスを加算（大村・唐津等、番記者による機力診断）
    motor_bonus = _parse_motor_eval_points(comment_data, waku)
    if motor_bonus is not None:
        score = max(0.0, min(1.0, score + motor_bonus))
        matched_keywords.append(f"モーター評価{motor_bonus:+.2f}")

    if score > 0.55:
        label = "▲"
    elif score < 0.45:
        label = "▼"
    else:
        label = "―"

    result = {
        "text": text,
        "source": source,
        "base_score": 0.5,
        "matched_keywords": matched_keywords,
        "raw_score": round(score, 4),
        "final_label": label,
    }
    if motor_bonus is not None:
        result["motor_eval_bonus"] = motor_bonus
    return result


# ── 選手コメントスコア（v4.1 NEW） ──────────────────────────────
def calc_comment_score(waku: int, comment_data: dict, pitreport_data: dict = None,
                       player_review: dict = None, reg_no: str = "") -> float:
    """
    選手コメントを足の状態スコアに変換。
    優先順:
      1. pitreport_data（公式ピットレポート・全会場R7-12対応）
      2. comment_data（会場公式サイト・福岡等）
      3. player_review（会場公式選手短評・シリーズ単位。大村・福岡等）
    コメント未取得の場合は中立値 0.5 を返す。

    スコア範囲: 0.0（最悪）〜 1.0（最良）、中立=0.5
    """
    detail = explain_comment_score(
        waku, comment_data, pitreport_data=pitreport_data,
        player_review=player_review, reg_no=reg_no
    )
    return detail["raw_score"]


def get_comment_text(waku: int, comment_data: dict, pitreport_data: dict = None) -> str:
    """出力用：当日コメントのテキストを返す。
    pitreport_data が優先（全会場・R7-12対応）、なければ comment_data を使用。"""
    # pitreport を優先
    if pitreport_data:
        pr_comments = pitreport_data.get("comments", {})
        pr = pr_comments.get(waku) or pr_comments.get(str(waku))
        if pr and pr.get("comment"):
            return pr["comment"]
    if not comment_data:
        pass
    else:
        waku_data = comment_data.get("comments", {}).get(str(waku)) or \
                    comment_data.get("comments", {}).get(waku)
        if waku_data:
            t = waku_data.get("comment_today", "") or waku_data.get("comment_prev", "")
            if t:
                return t
    return ""


def get_comment_text_with_review(waku: int, comment_data: dict,
                                 pitreport_data: dict = None,
                                 player_review: dict = None,
                                 reg_no: str = "") -> tuple[str, str]:
    """コメントテキストと出典ラベルを返す (text, source_label)"""
    if pitreport_data:
        pr = (pitreport_data.get("comments", {}).get(waku) or
              pitreport_data.get("comments", {}).get(str(waku)))
        if pr and pr.get("comment"):
            prev = pr.get("prev_result", "")
            return pr["comment"], f"公式ピットレポート{f'（前走:{prev}）' if prev else ''}"
    if comment_data:
        wdata = (comment_data.get("comments", {}).get(str(waku)) or
                 comment_data.get("comments", {}).get(waku))
        if wdata:
            t = wdata.get("comment_today", "") or wdata.get("comment_prev", "")
            if t:
                return t, "会場公式サイト"
    if player_review and reg_no:
        rv = player_review.get("reviews", {}).get(reg_no)
        if rv and rv.get("review"):
            return rv["review"], "会場公式サイト（短評）"
    return "", ""


def get_pitreport_source(waku: int, pitreport_data: dict, comment_data: dict) -> str:
    """コメントの出典を返す（HTML表示用）"""
    if pitreport_data:
        pr = pitreport_data.get("comments", {}).get(waku) or \
             pitreport_data.get("comments", {}).get(str(waku))
        if pr and pr.get("comment"):
            prev = pr.get("prev_result", "")
            return f"公式ピットレポート{f'（前走:{prev}）' if prev else ''}"
    if comment_data:
        wdata = comment_data.get("comments", {}).get(str(waku))
        if wdata and (wdata.get("comment_today") or wdata.get("comment_prev")):
            return "会場公式サイト"
    return ""


# ── 勝率：実績と当季のブレンド ──────────────────────────────────
def blend_win_rate(racecard_val, hist_val, hist_weight=0.6):
    """
    hist_val が有効なら実績60%＋当季40% でブレンド
    hist_val がなければ当季のみ
    """
    cur = safe_float(racecard_val, 0.0)
    if hist_val is not None and hist_val > 0:
        return hist_weight * (hist_val / 100.0) + (1 - hist_weight) * (cur / 100.0)
    return cur / 100.0


# ── モーター2連率：実績と当季ブレンド ──────────────────────────
def blend_motor_rate(racecard_val, motor_stats, hist_weight=0.5):
    cur  = safe_float(racecard_val, 0.0) / 100.0
    hist = motor_stats.get("top2_rate", None)
    if hist is not None and motor_stats.get("races",0) >= 5:
        return hist_weight * (hist / 100.0) + (1 - hist_weight) * cur
    return cur


def build_raw_metrics(racer, player_stats, motor_stats, exhibition_data, comment_data=None,
                      pitreport_data=None, player_review=None):
    """出力・ログ用に、生データと採用値をまとめる。"""
    waku = int(safe_float(racer.get("waku", 0)))
    global_hist = player_stats.get("hist_global_win_rate")
    local_hist = player_stats.get("hist_local_win_rate")
    motor_hist = motor_stats.get("top2_rate")
    global_blend = blend_win_rate(racer.get("global_win", 0), global_hist)
    local_blend = blend_win_rate(racer.get("local_win", 0), local_hist)
    motor_blend = blend_motor_rate(racer.get("motor_2rate", 0), motor_stats)
    actual_course = get_actual_entry_course(waku, exhibition_data) if waku else None

    ex_row = {}
    if exhibition_data:
        for e in exhibition_data.get("exhibition", []):
            if int(safe_float(e.get("waku", 0))) == waku:
                ex_row = e
                break

    comment_detail = explain_comment_score(
        waku, comment_data, pitreport_data=pitreport_data,
        player_review=player_review, reg_no=racer.get("reg_no", "")
    )
    comment_text = comment_detail.get("text", "")
    comment_source = comment_detail.get("source", "")
    comment_raw = comment_detail.get("raw_score", 0.5)
    comment_hist_bonus = (
        calc_comment_history_bonus(racer.get("reg_no", ""), comment_raw)
        if racer.get("reg_no", "") else 0.0
    )
    st_info = player_stats.get("hist_avg_st", {}) if isinstance(player_stats.get("hist_avg_st"), dict) else {}

    return {
        "global_win": {
            "season_pct": safe_float(racer.get("global_win", 0), 0.0),
            "hist_pct": safe_float(global_hist, 0.0) if global_hist is not None else None,
            "adopted_pct": round(global_blend * 100.0, 2),
        },
        "local_win": {
            "season_pct": safe_float(racer.get("local_win", 0), 0.0),
            "hist_pct": safe_float(local_hist, 0.0) if local_hist is not None else None,
            "adopted_pct": round(local_blend * 100.0, 2),
        },
        "motor_2rate": {
            "season_pct": safe_float(racer.get("motor_2rate", 0), 0.0),
            "hist_pct": safe_float(motor_hist, 0.0) if motor_hist is not None else None,
            "hist_races": int(motor_stats.get("races", 0) or 0),
            "adopted_pct": round(motor_blend * 100.0, 2),
        },
        "boat_2rate": {
            "season_pct": safe_float(racer.get("boat_2rate", 0), 0.0),
        },
        "st": {
            "racecard_avg": safe_float(racer.get("avg_st", 0), 0.0),
            "hist_avg": safe_float(st_info.get("avg_st", 0), 0.0) if st_info else None,
            "f_count": int(racer.get("f_count", 0) or 0),
            "l_count": int(racer.get("l_count", 0) or 0),
        },
        "series": {
            "ranks": racer.get("series_ranks", []),
            "races": racer.get("series_races", []),   # v5.19 #3: コース補正用 [{"course":N,"rank":M},...]
        },
        "exhibition": {
            "time": ex_row.get("exhibition_time", ""),
            "start_timing": ex_row.get("start_timing", ""),
            "tilt": ex_row.get("tilt", ""),
            "entry_course": ex_row.get("entry_course", ""),
            "actual_course": actual_course,
            "prev_rank": ex_row.get("prev_rank", ""),
        },
        "comment": {
            "source": comment_source,
            "text": comment_text,
            "base_score": round(comment_detail.get("base_score", 0.5), 4),
            "matched_keywords": comment_detail.get("matched_keywords", []),
            "raw_score": round(comment_raw, 4),
            "history_bonus": round(comment_hist_bonus, 4),
            "final_label": comment_detail.get("final_label", "―"),
        },
    }


# ── 総合スコア ───────────────────────────────────────────────────
def score_racer(racer, waku, jcd, race_no, date_str,
                player_stats, motor_stats, exhibition_data, weather, venue,
                tide_data=None, race_name: str = "", tournament_grade: str = "一般"):
    b = {}

    # 全国勝率
    b["global_win_rate"] = round(
        blend_win_rate(racer.get("global_win",0),
                       player_stats.get("hist_global_win_rate")) * WEIGHTS["global_win_rate"], 5)

    # 当地勝率
    b["local_win_rate"]  = round(
        blend_win_rate(racer.get("local_win",0),
                       player_stats.get("hist_local_win_rate")) * WEIGHTS["local_win_rate"], 5)

    # モーター2連率
    b["motor_2rate"]     = round(
        blend_motor_rate(racer.get("motor_2rate",0), motor_stats) * WEIGHTS["motor_2rate"], 5)

    # ボート2連率（v5.2）
    # racecard の boat_2rate (%) → 0〜1 に正規化（全国平均 ≈ 35% を基準）
    boat_2r = safe_float(racer.get("boat_2rate", 0), 0.0) / 100.0
    b["boat_2rate"]      = round(boat_2r * WEIGHTS["boat_2rate"], 5)

    # コース補正（v5.2: 実際の進入コースで計算）
    # 展示データがあれば entry_course を優先（前づけ・抵抗を反映）
    actual_course = get_actual_entry_course(waku, exhibition_data)
    course_score  = calc_venue_course_mod(
        actual_course, jcd, race_no, date_str, weather, venue, tide_data=tide_data)
    # 枠番と進入コースが異なる場合: 深い侵入リスクのペナルティ/恩恵を微調整
    # 前づけ(内寄り): actual_course < waku → 有利なコース取りだが深侵入リスク (-3%)
    # 抵抗・外押し : actual_course > waku → コース不利 (-5%)
    if actual_course != waku:
        if actual_course < waku:   # 前づけ（内側に移動）
            course_score *= 0.97   # 深侵入リスク小さいペナルティ
        else:                      # 外に押し出された
            course_score *= 0.95   # コース不利ペナルティ

    # ── 大会グレード補正 (v5.3) ──────────────────────────────────
    # SG/G1: 1コース有利増幅 / レディース: 1コース弱体・外コース強化
    tg_mods   = get_tournament_grade_mods(tournament_grade)
    tg_cm     = tg_mods["course_mod"]    # length-6 list
    tg_idx    = actual_course - 1        # 0-index
    tg_factor = tg_cm[tg_idx] if 0 <= tg_idx < len(tg_cm) else 1.0
    course_score *= tg_factor

    race_category        = classify_race_type(race_no, race_name)
    type_bonus           = RACE_TYPE_BONUS.get(race_category, 1.0)
    style_bonus          = calc_race_style_bonus(waku, player_stats)
    b["course_advantage"]= round(course_score * WEIGHTS["course_advantage"] * type_bonus * style_bonus, 5)
    # 進入コースが枠番と異なる場合のみ記録（表示用・スコアに影響しない補助情報）
    if actual_course != waku:
        b["_entry_course_note"] = actual_course   # "_"プレフィックス = sum()計算対象外

    # 級別
    grade                = racer.get("grade","B1").strip()
    b["grade_bonus"]     = round(GRADE_SCORE.get(grade,0.25) * WEIGHTS["grade_bonus"], 5)

    # ST
    b["st_score"]        = round(calc_st_score(racer, player_stats) * WEIGHTS["st_score"], 5)

    # 展示スコア（展示タイム60% + ST30% + チルト10%）
    # v5.21: live exhibition がない場合は player_stats["hist_exhibition"] にフォールバック
    ex_score             = (calc_exhibition_score(waku, exhibition_data, player_stats, jcd) * 0.6
                          + calc_exhibition_st_score(waku, exhibition_data) * 0.3
                          + calc_tilt_score(waku, exhibition_data)          * 0.1)
    b["exhibition_score"]= round(ex_score * WEIGHTS["exhibition_score"], 5)

    # 当地・当枠の実績1着率
    b["hist_waku_score"] = round(
        calc_hist_waku_score(waku, player_stats) * WEIGHTS["hist_waku_score"], 5)

    return {"total": round(sum(v for k, v in b.items() if not k.startswith("_")), 5), "breakdown": b}


def score_racer_with_comment(racer, waku, jcd, race_no, date_str,
                              player_stats, motor_stats,
                              exhibition_data, weather, venue, comment_data,
                              tide_data=None, race_name: str = "",
                              tournament_grade: str = "一般",
                              pitreport_data: dict = None,
                              engine_report: dict = None,
                              player_review: dict = None):
    """score_racer + comment_score(+履歴補正) + female_factor + engine_report を含む完全版スコアリング"""
    result = score_racer(racer, waku, jcd, race_no, date_str,
                         player_stats, motor_stats, exhibition_data, weather, venue,
                         tide_data=tide_data, race_name=race_name,
                         tournament_grade=tournament_grade)
    b = result["breakdown"]
    reg_no   = racer.get("reg_no", "")
    motor_no = str(racer.get("motor_no", ""))

    # コメントスコア（pitreport 優先・履歴補正込み）
    # 選手短評も fallback として使用（シリーズ単位コメント）
    raw_cs = calc_comment_score(waku, comment_data, pitreport_data=pitreport_data,
                                player_review=player_review, reg_no=reg_no)
    hist_bonus = calc_comment_history_bonus(reg_no, raw_cs) if reg_no else 0.0
    b["comment_score"] = round(
        max(0.0, min(1.0, raw_cs + hist_bonus)) * WEIGHTS["comment_score"], 5)

    # エンジン通信簿ボーナス（大村等・会場スタッフ評価1-6点）
    # eval 6=最良, 5=良, 4=普通, 3=やや不良, 2=不良, 1=最不良 → 基準4点で±補正
    # 影響範囲: ±motor_2rate の最大 15% 程度（大きすぎず現実的な範囲）
    if engine_report and motor_no:
        motor_info = engine_report.get("motors", {}).get(motor_no)
        if motor_info:
            ev = motor_info.get("eval", 4)  # 1-6点
            # eval 4=中立(0補正), 6=+0.01, 3=-0.005, 1=-0.015 程度
            engine_bonus = (ev - 4) * 0.004   # +0.008 / +0.004 / 0 / -0.004 / -0.008 / -0.012
            b["engine_bonus"] = round(engine_bonus, 5)

    # 女性レーサー係数（v5.0）
    ff = calc_female_factor(reg_no, player_stats, weather)
    b["female_factor"] = round(ff * WEIGHTS["female_factor"], 5)

    # 今節成績スコア（v5.19 #3 改良: コース補正着順）
    # series_races: [{"course":N,"rank":M},...] → コース別期待着順とのデルタで評価
    # 1号艇1着=期待通り / 6号艇1着=大健闘 / 1号艇6着=大不調
    # フォールバック: series_ranks のみ利用可なら旧ロジック
    series_races = racer.get("series_races", [])
    series_ranks = racer.get("series_ranks", [])
    if series_races:
        n = len(series_races)
        # コース別期待着順（全国統計の目安）
        expected = {1: 1.85, 2: 3.0, 3: 3.3, 4: 3.5, 5: 4.2, 6: 4.5}
        # performance = 期待着順 - 実着順（プラス=期待超え, マイナス=期待以下）
        perfs = [expected.get(s["course"], 3.5) - s["rank"] for s in series_races]
        avg_perf = sum(perfs) / n
        # 現実的な範囲 -3.0 〜 +3.0 を [0,1] に正規化
        series_raw = max(0.0, min(1.0, (avg_perf + 3.0) / 6.0))
        trust = min(1.0, n / 7.0)
        series_val = 0.5 * (1.0 - trust) + series_raw * trust
    elif series_ranks:
        # 旧racecard（series_races未取得）へのフォールバック
        n       = len(series_ranks)
        avg_rk  = sum(series_ranks) / n
        top2_rt = sum(1 for r in series_ranks if r <= 2) / n
        rank_score  = (6.0 - avg_rk) / 5.0
        series_raw  = rank_score * 0.7 + top2_rt * 0.3
        trust = min(1.0, n / 7.0)
        series_val  = 0.5 * (1.0 - trust) + series_raw * trust
    else:
        series_val  = 0.5   # 初日（実績なし）→ 中立
    b["series_score"] = round(series_val * WEIGHTS["series_score"], 5)

    return {"total": round(sum(v for k, v in b.items() if not k.startswith("_")), 5), "breakdown": b}


# ── 予想メイン ───────────────────────────────────────────────────
def predict(jcd: str, date: str, race_no: int, verbose: bool = True,
            tide_data=None, save_log: bool = True, _return_context: bool = False):
    try:
        from scraper import _maybe_bootstrap_venue_site_flow
        _maybe_bootstrap_venue_site_flow(jcd, trigger="predict")
    except Exception:
        pass

    racecard     = load_racecard(jcd, date, race_no)
    if not racecard:
        return ([], {}) if _return_context else []
    exhibition   = load_exhibition(jcd, date, race_no)
    weather      = load_weather(jcd, date, race_no)
    # 展示データに気象情報が含まれていれば weather のフォールバックとして使用
    # （scrape_exhibition() が weather も一緒に保存するため）
    if not weather and exhibition and exhibition.get("weather"):
        weather = exhibition["weather"]
    venue        = load_venue_data(jcd)
    comment_data   = load_comments(jcd, date, race_no)
    pitreport_data = load_pitreport(jcd, date, race_no)  # 公式ピットレポート（全会場R7-12）
    odds_data      = load_odds(jcd, date, race_no)
    engine_report  = load_engine_report(jcd, date)       # 会場公式エンジン通信簿（大村等）
    player_review  = load_player_review(jcd, date)       # 会場公式選手短評（大村・福岡等）

    race_name         = racecard.get("race_name", "")
    tournament_grade  = racecard.get("tournament_grade", "一般")
    race_category     = classify_race_type(race_no, race_name)

    # ── 全員女性レース検出: scraper で未検出の場合でも predictor 内で補正 ──
    # tournament_grade が既に "レディース" なら再チェック不要
    if tournament_grade == "一般":
        racers_tmp = racecard.get("racers", [])
        # player_stats を先読みしてチェック
        _ps_list = []
        for _r in racers_tmp:
            _rn = _r.get("reg_no","")
            _ps = load_player_stats(_rn) if _rn else {}
            _ps_list.append({"reg_no": _rn, "player_stats": _ps})
        if _ps_list and is_all_female_race(_ps_list):
            tournament_grade = "レディース"
            print(f"[INFO] 全員女性レースを検出 → グレード補正: レディース ({jcd} {date} {race_no}R)")

    scored = []
    _player_stats_cache: dict[str, dict] = {}

    for racer in racecard["racers"]:
        waku         = int(safe_float(racer.get("waku",0)))
        if waku == 0: continue
        reg_no       = racer.get("reg_no","")
        if reg_no in _player_stats_cache:
            player_stats = _player_stats_cache[reg_no]
        else:
            player_stats = load_player_stats(reg_no) if reg_no else {}
            _player_stats_cache[reg_no] = player_stats
        motor_no     = str(racer.get("motor_no",""))
        motor_stats  = load_motor_stats(jcd, motor_no) if motor_no else {}
        result       = score_racer_with_comment(
                           racer, waku, jcd, race_no, date,
                           player_stats, motor_stats,
                           exhibition, weather, venue, comment_data,
                           tide_data=tide_data, race_name=race_name,
                           tournament_grade=tournament_grade,
                           pitreport_data=pitreport_data,
                           engine_report=engine_report,
                           player_review=player_review)
        scored.append({
            "waku":           waku,
            "name":           racer.get("name","---"),
            "grade":          racer.get("grade",""),
            "motor_no":       motor_no,
            "reg_no":         reg_no,
            "racer":          racer,
            "score":          result["total"],
            "breakdown":      result["breakdown"],
            "player_stats":   player_stats,
            "motor_stats":    motor_stats,
            "comment_data":   comment_data,
            "pitreport_data": pitreport_data,
            "engine_report":  engine_report,
            "player_review":  player_review,
            "raw_metrics":    build_raw_metrics(
                                 racer, player_stats, motor_stats, exhibition,
                                 comment_data=comment_data, pitreport_data=pitreport_data,
                                 player_review=player_review),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    combo_stats = load_combo_stats(jcd) if _COMBO_STATS_AVAILABLE else None
    bets = _suggest_3rentan(scored, weather, combo_stats=combo_stats, exhibition_data=exhibition,
                            date_str=date, race_no=race_no, race_name=race_name, jcd=jcd)
    # v5.22: 1号艇の沈みリスク推定
    w1_estimate = estimate_w1_winrate(scored, jcd)
    confidence_pct, is_rough, _ = _calc_confidence(scored, sink_risk=w1_estimate.get("sink_risk"))
    # v5.19: セオリーパターン発動記録（verify 用）
    triggered_patterns = _detect_race_patterns(scored, exhibition, weather)
    applied_patterns = _extract_applied_patterns(bets)
    if verbose:
        _print_result(jcd, date, race_no, scored, venue, exhibition, weather,
                      tide_data=tide_data, odds_data=odds_data, combo_stats=combo_stats,
                      tournament_grade=tournament_grade)
    if save_log:
        _save_prediction_log(jcd, date, race_no, scored, tide_data,
                             bets=bets, confidence=_format_confidence(confidence_pct), is_rough=is_rough,
                             odds_data=odds_data, exhibition_data=exhibition, weather=weather,
                             triggered_patterns=triggered_patterns, applied_patterns=applied_patterns,
                             w1_estimate=w1_estimate)

    if _return_context:
        ctx = {
            "weather":          weather,
            "exhibition":       exhibition,
            "venue":            venue,
            "odds_data":        odds_data,
            "race_name":        race_name,
            "race_category":    race_category,
            "tournament_grade": tournament_grade,  # v5.3
        }
        return scored, ctx
    return scored


# ── セオリーパターン適用抽出（v5.19, #1 verify 追跡用） ─────────────
_PATTERN_REASON_MAP = {
    "2差しセオリー":   "2差し",
    "3カドまくり":     "3カド",
    "4カドまくり差し": "4カドまくり",
    "外差しセオリー":  "外差し",
}


def _extract_applied_patterns(bets) -> list[str]:
    """
    bets の reason 文字列からセオリーパターンが実際に適用されたかを逆引きする。
    triggered_patterns は conf 値だが、applied は bets に影響したもののみを返す。
    """
    applied: list[str] = []
    if not bets:
        return applied
    for item in bets:
        reason = ""
        if isinstance(item, dict):
            reason = item.get("reason", "") or ""
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            reason = item[2] or ""
        for needle, name in _PATTERN_REASON_MAP.items():
            if needle in reason and name not in applied:
                applied.append(name)
    return applied


# ── 予測ログ保存 ─────────────────────────────────────────────────
def _save_prediction_log(jcd, date, race_no, scored, tide_data, bets=None,
                         confidence: str = "", is_rough: bool = False,
                         odds_data=None, exhibition_data=None, weather=None,
                         triggered_patterns=None, applied_patterns=None,
                         w1_estimate=None):
    """
    予測結果を JSON で保存（後で実績と照合するため）
    保存先: data/logs/{date}/{jcd}_R{race_no:02d}_pred.json
    """
    # v5.16: 2セクション構成 (本命/その他) を同時に保存
    honmei_list, others_list = _normalize_bets(bets or [])

    # v5.20: 予算別買い目ログ保存（4段階予算×strategy別配分）
    # v5.24: 配分案の母集合は「公開する買い目」に揃える
    plan_bets = selected_bets(bets or [])
    budget_plans = []
    if odds_data and odds_data.get("odds_3t") and plan_bets:
        for amount in (500, 1000, 2000, 3000):
            plan = _build_budget_plan(plan_bets, scored, odds_data, budget=amount, unit=100)
            if plan:
                budget_plans.append(plan)

    # v5.18: スタート展示順をログに保存（WP連携用）
    course_order = []
    if exhibition_data and isinstance(exhibition_data, dict):
        course_order = exhibition_data.get("course_order", [])

    log = {
        "jcd":        jcd,
        "date":       date,
        "race_no":    race_no,
        "version":    PREDICTOR_VERSION,  # v5.20〜: バージョン別的中率追跡用
        "predicted_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "confidence": confidence.strip(),
        "is_rough": is_rough,
        "bets": [
            {"label": label.strip(), "combo": combo, "reason": reason}
            for label, combo, reason in (bets or [])
        ],
        # v5.16 新構造: 本命 / その他
        "honmei":    honmei_list,
        "others":    others_list,
        "predictions": [
            {
                "rank":   i + 1,
                "waku":   r["waku"],
                "name":   r["name"],
                "grade":  r["grade"],
                "reg_no": r.get("reg_no", ""),
                "motor_no": r.get("motor_no", ""),
                "score":  r["score"],
                "breakdown": r.get("breakdown", {}),
                "raw_metrics": r.get("raw_metrics", {}),
                "waku_stats": {
                    "local": (
                        (r.get("player_stats", {}) or {})
                        .get("hist_local_waku_stats", {})
                        .get(str(r["waku"]), {})
                    ),
                    "global": (
                        (r.get("player_stats", {}) or {})
                        .get("hist_global_waku_stats", {})
                        .get(str(r["waku"]), {})
                    ),
                },
            }
            for i, r in enumerate(scored)
        ],
        "tide_status": (
            tide_data.get("race_tides",{}).get(str(race_no),{}).get("label_jp","")
            if tide_data else ""
        ),
        # v5.18: WP連携用追加フィールド
        "budget_plans": budget_plans,
        "course_order": course_order,
        # v5.19: セオリーパターン発動記録（#1 verify 追跡用）
        "triggered_patterns": triggered_patterns or {},
        "applied_patterns":   applied_patterns or [],
        # v5.22: 1号艇沈みリスク推定（estimated 1着率 / sink_risk / 補正係数）
        "w1_estimate":        w1_estimate or {},
        # v5.24: 展示/オッズが反映済みかのフラグ（verify で層別するため）
        "has_exhibition":     bool(exhibition_data),
        "has_odds":           bool(odds_data and odds_data.get("odds_3t")),
        # v5.24: is_rough の判定材料を残す。
        # is_rough は (gap12 <= 0.015) or (sink_risk >= 0.55) で決まるが、これまで
        # 判定結果しか記録しておらず、閾値を動かしたときの影響を事後に評価できなかった。
        # gap を残しておけば「閾値をXにしていたら」を実データで検証できる。
        "score_gap12": (round(scored[0]["score"] - scored[1]["score"], 5)
                        if len(scored) >= 2 else None),
        "score_gap13": (round(scored[0]["score"] - scored[2]["score"], 5)
                        if len(scored) >= 3 else None),
    }
    log_dir = DATA_DIR / "logs" / date
    log_dir.mkdir(parents=True, exist_ok=True)
    out = log_dir / f"{jcd}_R{race_no:02d}_pred.json"

    # ── v5.24: 展示/オッズ更新“前”の買い目を保存する ──────────────
    # このファイルは同一レースで朝の予測→展示/オッズ反映と2回以上書かれるが、
    # 従来は毎回まるごと上書きしていたため、更新前の買い目が残らず
    # 「更新が予想を良くしたのか悪くしたのか」を検証できなかった。
    # 実測では更新後のレースの方が回収率が16pt低く、切り分けが必要になっている。
    prev = None
    if out.exists():
        try:
            with open(out, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = None
    if prev:
        if prev.get("pre_update"):
            # 3回目以降の書き込み。最初のスナップショットを維持する
            log["pre_update"] = prev["pre_update"]
        elif not (prev.get("has_exhibition") or prev.get("has_odds")) and \
                (log["has_exhibition"] or log["has_odds"]):
            log["pre_update"] = {
                "predicted_at": prev.get("predicted_at", ""),
                "version":      prev.get("version", ""),
                "confidence":   prev.get("confidence", ""),
                "is_rough":     prev.get("is_rough", False),
                "bets":         prev.get("bets", []),
                "honmei":       prev.get("honmei", []),
                "others":       prev.get("others", []),
                # 頭の比較用に予測順の枠だけ持つ（全breakdownは重いので持たない）
                "pred_waku":    [p.get("waku") for p in prev.get("predictions", [])],
            }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ── セオリーパターン検出（v5.13, 1-E） ─────────────────────────────
def _avg_st_from_scored(row: dict) -> float:
    """scored の1要素から avg_st を取り出す（hist > racecard > default 0.18）"""
    ps = row.get("player_stats", {}) or {}
    hist = ps.get("hist_avg_st") or {}
    if isinstance(hist, dict):
        v = hist.get("avg_st")
        if v:
            try: return float(v)
            except: pass
    racer = row.get("racer", {}) or {}
    v = racer.get("avg_st")
    if v:
        try: return float(v)
        except: pass
    return 0.18


def _exhibition_st_for(waku: int, exhibition_data) -> float | None:
    """展示の start_timing を秒値で返す。取得できなければ None"""
    if not exhibition_data:
        return None
    for e in exhibition_data.get("exhibition", []) or []:
        try:
            if int(float(e.get("waku", 0) or 0)) != waku:
                continue
        except Exception:
            continue
        st_raw = str(e.get("start_timing", "") or "").strip()
        if not st_raw:
            return None
        try:
            st_str = st_raw.lstrip(".")
            if "." in st_str and not st_raw.startswith("0"):
                return float("0." + st_str)
            return float(st_raw)
        except Exception:
            return None
    return None


def _detect_race_patterns(scored: list, exhibition_data, weather) -> dict:
    """
    動的な決まり手セオリーを検出して confidence (0.0〜1.0) を返す。

    返値例:
      {
        "2差し":  0.65,   # 2号艇差し → 3が続き 1が沈むパターン
        "3カド":  0.00,
        "4カドまくり": 0.00,
        "外差し": 0.40,
      }
    """
    patterns = {"2差し": 0.0, "3カド": 0.0, "4カドまくり": 0.0, "外差し": 0.0}
    if len(scored) < 4:
        return patterns

    by_waku = {int(r["waku"]): r for r in scored}
    rank_of = {int(r["waku"]): i + 1 for i, r in enumerate(scored)}  # 1=1位

    def st(waku):
        r = by_waku.get(waku)
        return _avg_st_from_scored(r) if r else 0.18

    def grade(waku):
        r = by_waku.get(waku)
        return (r.get("grade", "") if r else "") or ""

    def score(waku):
        r = by_waku.get(waku)
        return float(r.get("score", 0) or 0) if r else 0.0

    st1 = st(1); st2 = st(2); st3 = st(3); st4 = st(4); st5 = st(5); st6 = st(6)

    # ── パターン1: 2差し（2号艇ST速・score上位・3枠も上位） ───────
    if 2 in by_waku and 3 in by_waku:
        conf = 0.0
        # 2号艇のSTが1号艇と同等以上
        if st2 <= st1 + 0.01:
            conf += 0.30
        if st2 <= st1 - 0.01:
            conf += 0.10  # さらに速ければ追加
        # 2号艇が score top3 以内
        if rank_of.get(2, 99) <= 3:
            conf += 0.20
        # 3号艇も上位にいる（差しに続きやすい条件）
        if rank_of.get(3, 99) <= 4:
            conf += 0.15
        # A1/A2 の差し屋候補
        if grade(2) in ("A1", "A2"):
            conf += 0.10
        # 展示STで追加確証
        ex2 = _exhibition_st_for(2, exhibition_data)
        ex1 = _exhibition_st_for(1, exhibition_data)
        if ex2 is not None and ex1 is not None:
            if ex2 <= ex1 + 0.005:
                conf += 0.20
        # 2枠のscoreが1枠とほぼ互角
        if score(2) >= score(1) - 0.03:
            conf += 0.10
        patterns["2差し"] = round(min(conf, 1.0), 3)

    # ── パターン2: 3カドまくり（3号艇ST速・4枠弱い → 3が実質カド） ──
    if 3 in by_waku and 4 in by_waku:
        conf = 0.0
        if st3 <= st1 + 0.005:
            conf += 0.25
        if rank_of.get(3, 99) <= 3:
            conf += 0.20
        # 4号艇が弱い＝3号艇が実質カド位置
        if rank_of.get(4, 99) >= 5:
            conf += 0.20
        if grade(3) == "A1":
            conf += 0.15
        ex3 = _exhibition_st_for(3, exhibition_data)
        if ex3 is not None and ex3 <= 0.14:
            conf += 0.15
        patterns["3カド"] = round(min(conf, 1.0), 3)

    # ── パターン3: 4カドまくり差し（4号艇A1+ST速+勝率高い） ────────
    if 4 in by_waku:
        conf = 0.0
        r4 = by_waku[4]
        racer4 = r4.get("racer", {}) or {}
        global_win = float(racer4.get("global_win", 0) or 0)
        if st4 <= 0.14:
            conf += 0.25
        if global_win >= 6.0:
            conf += 0.25
        elif global_win >= 5.0:
            conf += 0.12
        if rank_of.get(4, 99) <= 3:
            conf += 0.20
        if grade(4) == "A1":
            conf += 0.15
        ex4 = _exhibition_st_for(4, exhibition_data)
        if ex4 is not None and ex4 <= 0.13:
            conf += 0.15
        patterns["4カドまくり"] = round(min(conf, 1.0), 3)

    # ── パターン4: 外差し（1残し・5/6枠ST速・風あり） ──────────────
    if 1 in by_waku and (5 in by_waku or 6 in by_waku):
        conf = 0.0
        if rank_of.get(1, 99) == 1:
            conf += 0.15
        wind = get_wind_speed(weather) if weather else 0.0
        if wind >= 3.0:
            conf += 0.15
        # 5枠 or 6枠がST速い
        fast_outer = min(st5, st6)
        if fast_outer <= 0.14:
            conf += 0.30
        elif fast_outer <= 0.16:
            conf += 0.15
        ex5 = _exhibition_st_for(5, exhibition_data)
        ex6 = _exhibition_st_for(6, exhibition_data)
        best_ex = min(x for x in (ex5, ex6) if x is not None) if any(x is not None for x in (ex5, ex6)) else None
        if best_ex is not None and best_ex <= 0.13:
            conf += 0.20
        patterns["外差し"] = round(min(conf, 1.0), 3)

    return patterns


# ── 3連単買い目生成（v7.0） ──────────────────────────────────────
def _suggest_3rentan(scored: list, weather=None,
                     combo_stats: dict | None = None,
                     exhibition_data=None,
                     date_str: str = "", race_no: int = 0,
                     race_name: str = "",
                     jcd: str = "") -> list[tuple[str, str, str]]:
    """
    3連単の買い目を生成して返す。
    戻り値: [(ラベル, "X-Y-Z", 理由), ...]

    内部ではフォーメーションを作り、最終出力だけ3連単へ展開する。
      本命①: 1着本線固定の主力フォーメーションから最上位を採用
      本命②: 順序不確実性 or 1着崩れ警戒の別フォーメーションから採用
      穴   : 真の1着崩れ型 / 1着残し相手崩れ型のフォーメーション
      出目④: 3着抜け・2着替わりを埋める保険フォーメーション
    """
    if len(scored) < 4:
        return []

    p  = [r["waku"] for r in scored]   # p[0]=1位枠 ... p[5]=6位枠
    sc = [r["score"] for r in scored]
    confidence_pct, is_rough, _ = _calc_confidence(scored)
    gap_12 = sc[0] - sc[1]
    gap_23 = sc[1] - sc[2]

    bets: list[tuple[str, str, str]] = []
    existing_combos: set[str] = set()   # 重複チェック用
    score_map = {r["waku"]: r["score"] for r in scored}

    def _add_bet(label: str, combo: str, reason: str):
        if combo not in existing_combos:
            bets.append((label, combo, reason))
            existing_combos.add(combo)

    def _cond2(first_waku: int, second_waku: int) -> float:
        return get_cond_2nd_prob(combo_stats, str(first_waku), str(second_waku)) if combo_stats else 0.0

    def _cond3(first_waku: int, second_waku: int, third_waku: int) -> float:
        return get_cond_3rd_prob(combo_stats, str(first_waku), str(second_waku), str(third_waku)) if combo_stats else 0.0

    def _rank_second_candidates(first_waku: int, excluded: set[int] | None = None) -> list[tuple[int, float, float]]:
        excluded = excluded or set()
        ranked: list[tuple[int, float, float]] = []
        for waku in p[:5]:
            if waku == first_waku or waku in excluded:
                continue
            score_val = score_map.get(waku, 0.0)
            cond2 = _cond2(first_waku, waku)
            # v5.13 (1-B): cond_2nd の重みを 0.18 → 0.35 に倍増
            mixed = score_val + cond2 * 0.35
            ranked.append((waku, mixed, cond2))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def _rank_third_candidates(first_waku: int, second_waku: int,
                               excluded: set[int] | None = None) -> list[tuple[int, float, float]]:
        excluded = excluded or set()
        ranked: list[tuple[int, float, float]] = []
        for waku in p[:5]:
            if waku in {first_waku, second_waku} or waku in excluded:
                continue
            score_val = score_map.get(waku, 0.0)
            cond3 = _cond3(first_waku, second_waku, waku)
            # v5.13 (1-B): cond_3rd の重みを 0.15 → 0.28 に引き上げ
            mixed = score_val + cond3 * 0.28
            ranked.append((waku, mixed, cond3))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def _combo_model_score(first_waku: int, second_waku: int, third_waku: int) -> float:
        return (
            score_map.get(first_waku, 0.0) * 1.25
            + score_map.get(second_waku, 0.0) * 0.85
            + score_map.get(third_waku, 0.0) * 0.65
            # v5.13 (1-B): 条件付き確率の重みを引き上げ
            + _cond2(first_waku, second_waku) * 0.55
            + _cond3(first_waku, second_waku, third_waku) * 0.42
        )

    def _expand_formation(firsts: list[int], seconds: list[int], thirds: list[int],
                          reason: str, max_count: int = 4,
                          excluded_combos: set[str] | None = None) -> list[tuple[str, float, str]]:
        excluded_combos = excluded_combos or set()
        ranked: list[tuple[str, float, str]] = []
        seen: set[str] = set()
        for first_waku in firsts:
            for second_waku in seconds:
                if second_waku == first_waku:
                    continue
                for third_waku in thirds:
                    if third_waku in {first_waku, second_waku}:
                        continue
                    combo = f"{first_waku}-{second_waku}-{third_waku}"
                    if combo in seen or combo in excluded_combos:
                        continue
                    seen.add(combo)
                    ranked.append((combo, _combo_model_score(first_waku, second_waku, third_waku), reason))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:max_count]

    def _add_formation(label: str, formation_rows: list[tuple[str, float, str]]) -> list[str]:
        added: list[str] = []
        for combo, _score, reason in formation_rows:
            if combo not in existing_combos:
                _add_bet(label, combo, reason)
                added.append(combo)
        return added

    seq_ranked = _rank_second_candidates(p[0])
    seq_uncertain = (
        gap_23 < 0.020
        or (len(seq_ranked) >= 2 and abs(seq_ranked[0][1] - seq_ranked[1][1]) < 0.015)
        or (len(seq_ranked) >= 2 and abs(seq_ranked[0][2] - seq_ranked[1][2]) < 0.04)
    )

    main_seconds = [w for w, _, _ in seq_ranked[:2]] or p[1:3]
    # v5.26 (2026-08-18): 3着候補から2着候補を除外しない。
    #
    # 従来は `waku not in {p[0], *main_seconds}` として2着候補を3着から外していた。
    # そのため 2着候補が {2,3} のとき（頭=1号艇では最頻のケース）本命4点は
    # 1-2-4 / 1-2-5 / 1-3-4 / 1-3-5 になり、**1-2-3 と 1-3-2 を構造的に買えなかった**。
    # ところが実測（1号艇が1着の42,044レース）では
    #   1-2-3 12.94%（1位） / 1-3-2 10.03%（2位）
    # で、この2つだけで該当レースの約23%を占める。最も当たる出目を買わない
    # 作りになっていた。
    # _expand_formation 側は combo ごとに third in {first, second} を弾くので、
    # 除外を外しても 1-2-2 のような不正な出目は生成されない。
    main_thirds_base = [waku for waku in p[:5] if waku != p[0]]
    main_thirds = main_thirds_base[:3] if main_thirds_base else [p[2], p[3]]
    main_formation_reason = "本線フォーメーション"
    if combo_stats and main_seconds:
        main_formation_reason = f"1着{p[0]}固定 / 2着候補{','.join(map(str, main_seconds))} / 3着候補{','.join(map(str, main_thirds))}"
    main_formation = _expand_formation([p[0]], main_seconds, main_thirds, main_formation_reason, max_count=4)
    picked_main_rows = _add_formation("本命①", main_formation)
    if not picked_main_rows:
        return bets

    # ── v5.13 (1-A) + v5.14 段階2: 多軸 top_combos を本命①に強制組み込み ──
    # 月 / 種別 / レース帯 / 季節 の各軸 top_combos を重み付きマージし、
    # 予想1着（p[0]）を先頭とする出目を優先採用する
    if combo_stats:
        # v5.14: 軸マージランキングを優先
        merged_ranking = _collect_axis_top_combos(combo_stats, date_str, race_no, race_name)

        # フォールバック: 軸データが無ければ overall top_combos を使う（v5.13 相当）
        if not merged_ranking:
            for entry in combo_stats.get("top_combos", []) or []:
                combo_str = entry.get("combo", "")
                freq = float(entry.get("freq", 0) or 0)
                merged_ranking.append((combo_str, freq, f"会場top({freq*100:.1f}%)"))

        added_top = 0
        for combo_str, weighted_freq, source in merged_ranking:
            if added_top >= 2:
                break
            if not combo_str:
                continue
            try:
                a, b, c = [int(x) for x in combo_str.split("-")]
            except Exception:
                continue
            # 予想1着（p[0]）が1着のパターンだけを採用
            if a != p[0]:
                continue
            if combo_str in existing_combos:
                continue
            # 軸マージ値が 0.015（=1.5%相当）未満ならスキップ
            if weighted_freq < 0.015:
                continue
            _add_bet("本命①", combo_str, f"多軸top {source}")
            added_top += 1

    main_first, main_second, main_third = [int(x) for x in picked_main_rows[0].split("-")]
    insurance_third_ranked = _rank_third_candidates(main_first, main_second, excluded={main_third})
    insurance_third = insurance_third_ranked[0][0] if insurance_third_ranked else p[3]

    # ── v5.13 (1-E): セオリーパターン検出 ──
    patterns = _detect_race_patterns(scored, exhibition_data, weather)

    # ── 本命②: セオリーパターン > 順序不確実性 > 1着崩れ警戒 ──────
    # v5.13 (1-E): セオリーが強く発動していれば最優先で本命②に反映
    pattern_applied = False
    if patterns.get("2差し", 0) >= 0.60 and 2 in p[:4] and 3 in p[:4]:
        # 2-3-X / 2-3-1 / 2-1-3 を入れる
        thirds_for_2 = [1, main_first if main_first != 1 else p[1]]
        thirds_for_2 += [w for w in p[:4] if w not in (2, 3, *thirds_for_2)]
        sashi_form = _expand_formation(
            [2], [3], thirds_for_2[:2],
            f"2差しセオリー(conf={patterns['2差し']:.2f}) 3が続き1沈む", max_count=2,
            excluded_combos=existing_combos
        )
        if _add_formation("本命②", sashi_form):
            pattern_applied = True
    elif patterns.get("3カド", 0) >= 0.60 and 3 in p[:4]:
        kado_form = _expand_formation(
            [3], [1, 2], [2, 1, 5],
            f"3カドまくり(conf={patterns['3カド']:.2f})", max_count=2,
            excluded_combos=existing_combos
        )
        if _add_formation("本命②", kado_form):
            pattern_applied = True
    elif patterns.get("4カドまくり", 0) >= 0.60 and 4 in p[:4]:
        kado4_form = _expand_formation(
            [4], [1, 2, 5], [2, 1, 5],
            f"4カドまくり差し(conf={patterns['4カドまくり']:.2f})", max_count=2,
            excluded_combos=existing_combos
        )
        if _add_formation("本命②", kado4_form):
            pattern_applied = True

    if not pattern_applied:
        if seq_uncertain:
            order_cover = _expand_formation(
                [main_first], [main_second, main_third], [main_second, main_third],
                f"2-3着不確実(差{gap_23:.3f}) 順序両取り", max_count=3,
                excluded_combos=existing_combos
            )
            _add_formation("本命②", order_cover)
        elif is_rough or gap_12 < 0.025 or confidence_pct < 70:  # v5.13 (1-D): 閾値を緩和
            alt_firsts = [p[1], p[0]]
            alt_seconds = [waku for waku in p[:4] if waku not in alt_firsts][:2] + [p[0]]
            alt_thirds = [waku for waku in p[:5] if waku not in set(alt_firsts + alt_seconds)][:3] + [p[2]]
            alt_first_form = _expand_formation(
                alt_firsts[:2], alt_seconds[:3], alt_thirds[:3],
                f"1着崩れ警戒(信頼{confidence_pct}%)", max_count=4,
                excluded_combos=existing_combos
            )
            _add_formation("本命②", alt_first_form)
        else:
            insurance_form = _expand_formation(
                [main_first], [main_second], [insurance_third, main_third],
                f"相手抜け保険 3着候補{main_third},{insurance_third}", max_count=3,
                excluded_combos=existing_combos
            )
            _add_formation("本命②", insurance_form)

    # ── v5.13 (1-E): 外差しパターン発動時は本命②に追加で1-外-内を入れる ──
    if patterns.get("外差し", 0) >= 0.55 and 1 in p[:3]:
        outer_form_candidates: list[int] = []
        for w in (5, 6):
            if w in score_map:
                outer_form_candidates.append(w)
        if outer_form_candidates:
            thirds_inner = [main_second, p[2] if len(p) > 2 else 2]
            outer_form = _expand_formation(
                [1], outer_form_candidates[:1], thirds_inner[:2],
                f"外差しセオリー(conf={patterns['外差し']:.2f})", max_count=2,
                excluded_combos=existing_combos
            )
            _add_formation("本命②", outer_form)

    # ── v5.23: 会場別 1着waku別の連動テーブルから follower bets を追加 ──
    # 「3まくり→1残し→4差し」「4まくり→5-6連発」など、会場特性の出やすい縦目を採用
    if jcd:
        # score上位3艇のうち non-1 を対象（1号艇1着シナリオは既存ロジックで網羅）
        for cand_winner in p[:3]:
            if cand_winner == 1:
                continue
            top_combos = get_top1_followers(jcd, cand_winner, min_n=8)
            if not top_combos:
                continue
            # 上位2件のうち、まだ未登場の組合せを追加
            added = 0
            for c in top_combos[:3]:
                if added >= 2:
                    break
                combo_str = c.get("combo", "")
                if not combo_str or combo_str in existing_combos:
                    continue
                pct = c.get("pct", 0)
                if pct < 0.08:  # 8% 未満の頻度は除外（ノイズ防止）
                    continue
                reason = f"会場連動(w1={cand_winner}, 頻度{pct*100:.1f}%, n={top_combos[0].get('count','?')})"
                # bets に直接追加（_add_formation 経由ではなく軽量に）
                bets.append(("対抗", combo_str, reason))
                existing_combos.add(combo_str)
                added += 1

    # ── 穴：upset_score で一発候補を選出 ─────────────────────────
    # scored[3:] = 4〜6位（スコア順）の選手を評価
    wind = get_wind_speed(weather) if weather else 0.0

    def _upset_score(r: dict, rank: int) -> tuple[float, list[str]]:
        """
        穴候補スコアを計算。スコアが高いほど一発の可能性あり。
        r: scored要素（player_stats/breakdown含む）, rank: 何位か（4,5,6）
        """
        ps      = r.get("player_stats", {})
        b       = r.get("breakdown", {})
        waku    = r["waku"]
        reasons = []
        score   = 0.0

        motor_norm = float(b.get("motor_2rate", 0) or 0)
        if motor_norm >= 0.045:
            score += 0.30
            reasons.append("モーター良好↑")
        elif motor_norm >= 0.030:
            score += 0.12
            reasons.append("モーター普通")

        st_info = ps.get("hist_avg_st") or {}
        if isinstance(st_info, dict):
            avg_st = float(st_info.get("avg_st", 0) or 0)
        else:
            avg_st = float(st_info or 0)
        if 0 < avg_st <= 0.14:
            score += 0.28
            reasons.append(f"ST{avg_st:.2f}速")
        elif 0 < avg_st <= 0.16:
            score += 0.12
            reasons.append(f"ST{avg_st:.2f}")

        local_w = ps.get("hist_local_win_rate")
        if local_w is not None:
            local_w = float(local_w)
            if local_w >= 25.0:
                score += 0.22
                reasons.append(f"当地W{local_w:.0f}%")
            elif local_w >= 15.0:
                score += 0.12
                reasons.append(f"当地W{local_w:.0f}%")

        glb_w = ps.get("hist_global_win_rate")
        if glb_w is not None:
            glb_w = float(glb_w)
            if glb_w >= 30.0:
                score += 0.18
                reasons.append(f"全国W{glb_w:.0f}%")
            elif glb_w >= 20.0:
                score += 0.08
                reasons.append(f"全国W{glb_w:.0f}%")

        if waku in (2, 3):
            score += 0.14
            reasons.append(f"{waku}枠差し位")

        if wind >= 4.0 and waku in (4, 5, 6):
            score += 0.15
            reasons.append(f"強風まくり({waku}枠)")

        return score, reasons

    # 4〜6位の選手でupset_scoreを計算
    candidates = []
    for rank_idx in range(3, len(scored)):
        r = scored[rank_idx]
        uscore, ureasons = _upset_score(r, rank_idx + 1)
        candidates.append((uscore, r["waku"], ureasons, rank_idx))

    if candidates:
        candidates.sort(key=lambda x: -x[0])
        best_u, best_waku, best_reasons, best_idx = candidates[0]
        reason_str = "⚡穴:" + "/".join(best_reasons) if best_reasons else f"⚡{best_waku}枠穴"

        # v5.13 (1-D): 閾値 0.35 → 0.28 に引き下げ、連れ出し確率でブースト
        if best_u >= 0.28 or (is_rough and gap_12 < 0.025):
            upset_2nd = p[0]
            if combo_stats and str(best_waku) in combo_stats.get("outer_companion", {}):
                oc = combo_stats["outer_companion"][str(best_waku)]
                oc_2nd   = oc["most_likely_2nd"]
                oc_prob  = oc["prob"]
                if oc_2nd != str(p[0]):
                    upset_2nd = int(oc_2nd)
                    reason_str += f" 連れ出し{oc_2nd}枠({oc_prob*100:.0f}%)"
                # 高確率連れ出しは1-D追加で保険を1点プラス
                if oc_prob >= 0.40 and oc_2nd != str(best_waku):
                    try:
                        extra_third = int(oc_2nd) if int(oc_2nd) != best_waku else p[1]
                    except Exception:
                        extra_third = p[1]
            upset_form = _expand_formation(
                [best_waku], [upset_2nd, p[0]], [p[1], p[2], insurance_third],
                reason_str + " 1着狙い", max_count=3,
                excluded_combos=existing_combos
            )
            _add_formation("穴", upset_form)
        elif best_u >= 0.15:  # v5.13 (1-D): 0.18 → 0.15
            partner_form = _expand_formation(
                [main_first], [best_waku, main_second], [main_second, main_third, insurance_third],
                reason_str + " 2着差し", max_count=3,
                excluded_combos=existing_combos
            )
            _add_formation("穴", partner_form)
        else:
            hole_cover = _expand_formation(
                [main_first], [main_second], [insurance_third, p[3], p[4] if len(p) > 4 else insurance_third],
                f"{insurance_third}枠3着(相手抜け保険)", max_count=3,
                excluded_combos=existing_combos
            )
            _add_formation("穴", hole_cover)
    else:
        hole_cover = _expand_formation(
            [main_first], [main_second], [insurance_third, p[3]],
            f"{insurance_third}枠3着差し込み", max_count=3,
            excluded_combos=existing_combos
        )
        _add_formation("穴", hole_cover)

    # ── 出目④: 最頻出よりも「抜けやすい保険」を優先 ──────────────
    insurance_candidates: list[tuple[list[int], list[int], list[int], str]] = []
    if seq_uncertain:
        insurance_candidates.append(([main_first], [main_second, main_third], [main_second, main_third], "順序違い保険"))
    insurance_candidates.append(([main_first], [main_second], [insurance_third, main_third], f"3着{insurance_third}枠保険"))
    if len(seq_ranked) >= 2:
        alt_second = seq_ranked[1][0]
        alt_third_ranked = _rank_third_candidates(main_first, alt_second, excluded={main_second})
        if alt_third_ranked:
            insurance_candidates.append(([main_first], [alt_second], [alt_third_ranked[0][0], main_third],
                                         f"相手替わり保険 2着{alt_second}枠"))
    if combo_stats:
        s2_waku, s2_prob = get_best_2nd(combo_stats, str(main_first))
        s3_waku, s3_prob = get_best_3rd(combo_stats, str(main_first), s2_waku)
        if s2_prob >= 0.18:
            insurance_candidates.append(([main_first], [int(s2_waku)], [int(s3_waku), insurance_third],
                                         f"統計保険 2着{s2_waku}枠({s2_prob*100:.0f}%) 3着{s3_waku}枠({s3_prob*100:.0f}%)"))
    for firsts, seconds, thirds, reason in insurance_candidates:
        form = _expand_formation(firsts, seconds, thirds, reason, max_count=3, excluded_combos=existing_combos)
        if _add_formation("出目④", form):
            break

    # ── v5.15 段階3: EV（回収率）上位の出目を「出目④」に追加 ──
    # 過去実測で count≥10 & EV≥1.3 の高回収率出目を最大2点まで、
    # 予想1着（p[0]）を含まない場合のみ追加（本命筋と被らないように）
    if combo_stats:
        ev_candidates = _collect_axis_ev_combos(
            combo_stats, date_str, race_no, race_name,
            min_count=10, min_ev=1.30
        )
        added_ev = 0
        for combo_str, ev, avg_pay, source in ev_candidates:
            if added_ev >= 2:
                break
            if combo_str in existing_combos:
                continue
            try:
                a, b, c = [int(x) for x in combo_str.split("-")]
            except Exception:
                continue
            # 1着が予想上位4位以内の選手でなければスキップ（無関係な穴は入れない）
            if a not in p[:4]:
                continue
            _add_bet(
                "出目④", combo_str,
                f"EV上位 {source} 平均{avg_pay:.0f}円"
            )
            added_ev += 1

    return bets


def _group_bets_by_label(bets: list[tuple[str, str, str]]) -> dict[str, list[tuple[str, str]]]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for label, combo, reason in bets:
        clean = (label or "").strip()
        grouped.setdefault(clean, []).append((combo, reason))
    return grouped


# ── v5.16: 2セクション構成 (本命 / その他) に正規化 ─────────────────
#
# v5.24 (2026-08-15): 点数の削減と死に筋の除去。
# 3,317R の実測（docs/accuracy_review_2026-08.md）で、tier内の並び順に
# 回収率の単調性が無く、下位の買い目ほど期待値を削っていることが分かった:
#   対抗#2以降 30.0% / 抑え#4 0.0% / 穴#1 56.8%（いずれも本命の75.9%を大きく下回る）
# そこで tier ごとの上限に加えて「本命+対抗+抑え の合計」に上限を設ける。
HONMEI_CAP = 4      # 本命の内部上限（従来どおり）
CORE_CAP   = 4      # 本命+対抗+抑え の合計上限。本命が4点埋めれば対抗/抑えは出ない
TAIKOU_CAP = 1      # 対抗#2以降は実測ROI 30.0%
OSHI_CAP   = 3      # 抑え#4 は実測ROI 0.0%
ANA_CAP    = 1      # 穴は1点だけ（高配当の受け皿は残す）

# 穴は _expand_formation がモデルスコア降順で並べるため、#1 は「穴の中で最も堅い＝
# 最もオッズが低いレグ」になる。妙味が薄く実測ROIも最下位だったので先頭を飛ばす。
# ただしこの判定は的中59件 vs 20件の比較で統計的には弱い。P0-1 の蓄積が進んだら
# 週次レポートの by_cell（穴#1/#2/#3 の回収率）で再確認すること。
ANA_SKIP_TOP = 1

_SUBTYPE_MAP = {
    "本命①": "本命",
    "本命②": "対抗",
    "穴":    "穴",
    "出目④": "抑え",
}


def _normalize_bets(bets: list[tuple[str, str, str]]) -> tuple[list[dict], list[dict]]:
    """
    bets を 2 セクションに正規化する:
      本命  : 本命① のみ（最大 HONMEI_CAP 点）
      その他: 対抗 / 抑え / 穴

    点数制限（v5.24）:
      本命 + 対抗 + 抑え = 合計 CORE_CAP 点まで（本命→対抗→抑えの優先順で詰める）
      穴 = ANA_CAP 点。最有力レグを ANA_SKIP_TOP 個飛ばして採る

    戻り値:
      honmei  = [{"combo": "1-2-3", "reason": "..."}, ...]
      others  = [{"subtype": "対抗|抑え|穴", "combo": "...", "reason": "..."}, ...]

    重複出目は排除する。
    """
    seen: set[str] = set()
    honmei: list[dict] = []
    others_by_subtype: dict[str, list[dict]] = {"対抗": [], "穴": [], "抑え": []}

    for label, combo, reason in bets:
        if combo in seen:
            continue
        clean = (label or "").strip()
        subtype = _SUBTYPE_MAP.get(clean)
        if subtype is None:
            continue
        if subtype == "本命":
            if len(honmei) >= HONMEI_CAP:
                # 本命から溢れた有力出目は抑えに回す
                others_by_subtype["抑え"].insert(0, {"subtype": "抑え", "combo": combo, "reason": f"本命溢れ: {reason}"})
                seen.add(combo)
                continue
            honmei.append({"combo": combo, "reason": reason})
            seen.add(combo)
        else:
            others_by_subtype[subtype].append({"subtype": subtype, "combo": combo, "reason": reason})
            seen.add(combo)

    # ── v5.24: 本命+対抗+抑え を合計 CORE_CAP 点に絞る ──────────────
    # 本命を先に確保し、余った枠にだけ対抗（TAIKOU_CAP まで）→ 抑え（OSHI_CAP まで）
    # を入れる。本命が CORE_CAP を埋めた場合、対抗・抑えは出ない。
    honmei = honmei[:CORE_CAP]
    others: list[dict] = []
    room = CORE_CAP - len(honmei)
    for sub, cap in (("対抗", TAIKOU_CAP), ("抑え", OSHI_CAP)):
        if room <= 0:
            break
        for item in others_by_subtype[sub][:cap]:
            if room <= 0:
                break
            others.append(item)
            room -= 1

    # 穴は CORE_CAP の枠外。最有力レグを飛ばして ANA_CAP 点だけ採る。
    # 候補が最有力レグ1点しか無いレースは穴なしになる（その1点こそ実測で最も
    # 期待値が低かった脚なので、埋め合わせに拾うことはしない）。
    others.extend(others_by_subtype["穴"][ANA_SKIP_TOP:ANA_SKIP_TOP + ANA_CAP])

    return honmei, others


# ── オッズ期待値モデル（v5.1 A1①） ────────────────────────────────
def _calc_win_probs(scored: list) -> dict[str, float]:
    """
    スコアから各選手の1着確率を推定する（ソフトマックス近似）。
    戻り値: {waku_str: probability, ...}
    """
    import math
    scores = [r["score"] for r in scored]
    total  = sum(math.exp(s * 6.0) for s in scores)   # 温度パラメータ6.0で分布を尖らせる
    return {
        str(r["waku"]): math.exp(r["score"] * 6.0) / total
        for r in scored
    }


def _calc_bet_ev(combo: str, scored: list, odds_data: dict | None) -> float | None:
    """
    3連単 combo（例: "1-2-3"）の期待値を計算する。
    期待値 = P(combo) × odds(combo)
    P(combo) = P(A 1st) × P(B 2nd|A 1st) × P(C 3rd|A 1st,B 2nd) で近似
    戻り値: 期待値 (None = オッズデータなし)
    """
    if not odds_data:
        return None
    odds_3t = odds_data.get("odds_3t", {})
    if not odds_3t:
        return None

    parts = combo.split("-")
    if len(parts) != 3:
        return None
    a, b, c = parts[0], parts[1], parts[2]
    key = a + b + c
    odds = odds_3t.get(key)
    if odds is None:
        return None

    probs = _calc_win_probs(scored)
    total_score = {str(r["waku"]): r["score"] for r in scored}

    # P(A 1st)
    p_a = probs.get(a, 0.0)
    # P(B 2nd | A 1st) = score_B / (total_score - score_A)
    remaining_b = {k: v for k, v in total_score.items() if k != a}
    sum_rem_b   = sum(remaining_b.values()) or 1.0
    p_b_given_a = remaining_b.get(b, 0.0) / sum_rem_b
    # P(C 3rd | A 1st, B 2nd)
    remaining_c = {k: v for k, v in remaining_b.items() if k != b}
    sum_rem_c   = sum(remaining_c.values()) or 1.0
    p_c_given_ab = remaining_c.get(c, 0.0) / sum_rem_c

    prob = p_a * p_b_given_a * p_c_given_ab
    return round(prob * odds, 3)


def _distribute_budget_inverse_odds(selected: list[dict], budget: int, unit: int = 100) -> list[int]:
    """オッズ逆数で均しつつ、100円単位に丸めた賭け金配分を返す。"""
    if not selected or budget < unit:
        return [0] * len(selected)

    total_units = budget // unit
    weights = []
    for item in selected:
        odds = max(float(item.get("odds", 0) or 0), 1.01)
        weights.append(1.0 / odds)
    sum_weights = sum(weights) or 1.0

    unit_allocs = [max(1, int(total_units * w / sum_weights)) for w in weights]

    while sum(unit_allocs) > total_units:
        idx = max(range(len(unit_allocs)), key=lambda i: unit_allocs[i])
        if unit_allocs[idx] > 1:
            unit_allocs[idx] -= 1
        else:
            break

    while sum(unit_allocs) < total_units:
        payout_units = [
            unit_allocs[i] * float(selected[i].get("odds", 0) or 0)
            for i in range(len(selected))
        ]
        idx = payout_units.index(min(payout_units))
        unit_allocs[idx] += 1

    return [u * unit for u in unit_allocs]


def _distribute_budget_equal(selected: list[dict], budget: int, unit: int = 100) -> list[int]:
    """均等配分。端数は EV 高い買い目に優先付与。"""
    if not selected or budget < unit:
        return [0] * len(selected)
    total_units = budget // unit
    n = len(selected)
    base = total_units // n
    remainder = total_units - base * n
    allocs = [base] * n
    # EV 降順で余りを加算
    order = sorted(range(n), key=lambda i: -float(selected[i].get("ev", 0) or 0))
    for i in range(remainder):
        allocs[order[i % n]] += 1
    return [u * unit for u in allocs]


def _distribute_budget_ev_weighted(selected: list[dict], budget: int, unit: int = 100) -> list[int]:
    """EV（期待値）を重み係数にした配分。プラス期待値寄りに偏らせる。"""
    if not selected or budget < unit:
        return [0] * len(selected)
    total_units = budget // unit
    # EV を 0 未満にならないよう clip 後に重み化、更にオッズ逆数と0.5ずつブレンド（安定化）
    ev_w = [max(0.2, float(s.get("ev", 0) or 0)) for s in selected]
    odds_w = [1.0 / max(float(s.get("odds", 0) or 0), 1.01) for s in selected]
    weights = [0.6 * e + 0.4 * o * sum(ev_w) / (sum(odds_w) or 1.0) for e, o in zip(ev_w, odds_w)]
    sum_w = sum(weights) or 1.0
    allocs = [max(1, int(total_units * w / sum_w)) for w in weights]
    while sum(allocs) > total_units:
        idx = max(range(len(allocs)), key=lambda i: allocs[i])
        if allocs[idx] > 1:
            allocs[idx] -= 1
        else:
            break
    while sum(allocs) < total_units:
        order = sorted(range(len(allocs)),
                       key=lambda i: -float(selected[i].get("ev", 0) or 0))
        allocs[order[0]] += 1
    return [u * unit for u in allocs]


def _distribute_by_method(method: str, selected: list[dict], budget: int, unit: int = 100) -> list[int]:
    if method == "equal":
        return _distribute_budget_equal(selected, budget, unit)
    if method == "ev_weighted":
        return _distribute_budget_ev_weighted(selected, budget, unit)
    return _distribute_budget_inverse_odds(selected, budget, unit)


def _evaluate_budget_subset(selected: list[dict], budget: int, unit: int = 100,
                            method: str = "inverse_odds") -> dict | None:
    """選択済み買い目セットの配分案を評価して返す（v5.20: method切替対応）。"""
    if not selected or budget < unit:
        return None

    stakes = _distribute_by_method(method, selected, budget, unit=unit)
    rows = []
    min_profit = None
    expected_payout = 0.0
    for item, stake in zip(selected, stakes):
        odds = float(item.get("odds", 0) or 0)
        ev = float(item.get("ev", 0) or 0)
        payout = round(stake * odds)
        profit = payout - budget
        expected_payout += stake * ev
        if min_profit is None or profit < min_profit:
            min_profit = profit
        rows.append({
            "label": item.get("label", ""),
            "combo": item.get("combo", ""),
            "stake": stake,
            "odds": odds,
            "ev": ev,
            "payout": payout,
            "profit_if_hit": profit,
        })

    return {
        "budget": budget,
        "total_stake": sum(stakes),
        "rows": rows,
        "min_profit": min_profit if min_profit is not None else -budget,
        "expected_profit": round(expected_payout - budget),
        "no_trigarami": (min_profit or 0) >= 0,
    }


def _budget_strategy_for_amount(budget: int) -> dict:
    """
    予算額に応じた買い方ポリシー（v5.20 改修）。
    予算帯ごとに点数・組み合わせ・配分方法を変える。
    """
    if budget <= 500:
        return {
            "name": "本命ピンポイント",
            "description": "500円以下は本命①+②の2点まで。回収重視。",
            "max_selected": 2,
            "min_selected": 1,
            "allow_labels": {"本命①", "本命②"},
            "distribution": "inverse_odds",  # 本命寄りに厚く
            "prefer_fewer_bets": True,
        }
    if budget <= 1200:
        return {
            "name": "本命+押さえ",
            "description": "1000円前後は本命2点+押さえで3点、EV重視配分。",
            "max_selected": 3,
            "min_selected": 2,
            "allow_labels": {"本命①", "本命②", "出目④"},
            "distribution": "ev_weighted",  # EV重視
            "prefer_fewer_bets": False,
        }
    if budget <= 2500:
        return {
            "name": "本命+押さえ+穴",
            "description": "2000円前後は本命+押さえ+穴で4点、EV加重。",
            "max_selected": 4,
            "min_selected": 3,
            "allow_labels": {"本命①", "本命②", "出目④", "穴"},
            "distribution": "ev_weighted",
            "prefer_fewer_bets": False,
        }
    return {
        "name": "広め(穴均等)",
        "description": "3000円以上は穴含む4点を均等配分。高配当取りこぼし防止。",
        "max_selected": 4,
        "min_selected": 3,
        "allow_labels": {"本命①", "本命②", "出目④", "穴"},
        "distribution": "equal",  # 均等で穴ヒット時の利益を確保
        "prefer_fewer_bets": False,
    }


_SUBTYPE_TO_LABEL = {v: k for k, v in _SUBTYPE_MAP.items()}


def selected_bets(bets: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """実際に公開する買い目だけを (label, combo, reason) 形式で返す。

    v5.24: 予算プランは生の bets を見ていたため、点数上限で切り落とした買い目が
    配分案に残ってしまっていた（記事から買う側にとっては削減した意味がなくなる）。
    公開する買い目と配分案の母集合を一致させる。
    """
    honmei, others = _normalize_bets(bets or [])
    keep = [("本命①", b["combo"], b.get("reason", "")) for b in honmei]
    keep += [(_SUBTYPE_TO_LABEL.get(b["subtype"], b["subtype"]),
              b["combo"], b.get("reason", "")) for b in others]
    return keep


def _build_budget_plan(bets: list[tuple[str, str, str]], scored: list,
                       odds_data: dict | None, budget: int, unit: int = 100) -> dict | None:
    """予算制約つきの配分案を返す（v5.20: 本命オッズ連動ロジック）。"""
    if not odds_data or not odds_data.get("odds_3t") or budget < unit:
        return None

    strategy = _budget_strategy_for_amount(budget)

    enriched = []
    for label, combo, reason in bets:
        odds = odds_data.get("odds_3t", {}).get(combo.replace("-", ""))
        ev = _calc_bet_ev(combo, scored, odds_data)
        if odds is None or ev is None:
            continue
        clean_label = label.strip()
        if clean_label not in strategy["allow_labels"]:
            continue
        enriched.append({
            "label": clean_label,
            "combo": combo,
            "reason": reason,
            "odds": float(odds),
            "ev": float(ev),
        })
    if not enriched:
        return None

    # v5.20 A: 本命①をオッズ昇順にソートして、最も安い(=本命らしい)ものを筆頭に
    honmei1_sorted = sorted([e for e in enriched if e["label"] == "本命①"], key=lambda x: x["odds"])
    others_sorted = [e for e in enriched if e["label"] != "本命①"]
    enriched = honmei1_sorted + others_sorted

    # v5.20 B: 本命①の最低オッズが高すぎる → 波乱扱い
    min_honmei_odds = honmei1_sorted[0]["odds"] if honmei1_sorted else None
    is_upset = min_honmei_odds is not None and min_honmei_odds > 30.0
    if is_upset:
        # 本命らしい買い目が無いので、strategyを「波乱」モードに変更
        strategy = {
            **strategy,
            "name": f"{strategy['name']} (波乱)",
            "description": f"本命①最低オッズ{min_honmei_odds:.0f}倍と高く、堅い本命なし。多点で分散推奨。",
            # 波乱時は最低点数を増やし、取りこぼし防止
            "min_selected": max(strategy.get("min_selected", 1), 2),
            "distribution": "equal",  # 均等配分で穴ヒット時の利益確保
        }

    # v5.20: 本命①のオッズを基準に、少額予算の点数を動的調整
    # 本命①が低オッズ（堅い）なら 1点絞り、高オッズ（不安）なら多点分散
    honmei1 = honmei1_sorted[0] if honmei1_sorted else None
    if honmei1 and not is_upset:
        h_odds = honmei1["odds"]
        if budget <= 500:
            if h_odds < 10.0:
                strategy = {**strategy, "max_selected": 1, "min_selected": 1,
                            "name": f"{strategy['name']} (本命絞り)",
                            "description": f"本命①が{h_odds:.1f}倍と堅いため1点絞り推奨。"}
            else:
                strategy = {**strategy, "max_selected": 2, "min_selected": 2,
                            "name": f"{strategy['name']} (2点分散)",
                            "description": f"本命①が{h_odds:.1f}倍と不安定なため2点分散推奨。"}
        elif budget <= 1200 and h_odds < 6.0:
            # 1000円でも本命①が6倍未満なら2点まで（3点は過剰）
            strategy = {**strategy, "max_selected": 2, "min_selected": 2,
                        "name": f"{strategy['name']} (低オッズ絞り)",
                        "description": f"本命①が{h_odds:.1f}倍と堅いため2点に絞る。"}

    best_plan = None
    n = len(enriched)
    min_sel = min(strategy.get("min_selected", 1), n)  # enriched が足りない場合のフォールバック
    method = strategy.get("distribution", "inverse_odds")
    # v5.20 A: 本命①の最低オッズ品(筆頭)を必ず含める
    honmei1_top = honmei1_sorted[0] if honmei1_sorted else None
    for mask in range(1, 1 << n):
        subset = [enriched[i] for i in range(n) if (mask >> i) & 1]
        if len(subset) > strategy["max_selected"] or len(subset) < min_sel:
            continue
        if not any(item["label"] == "本命①" for item in subset):
            continue
        # v5.20 A: 最も安い本命①を必ず含む制約（enriched を odds ソート済なので index 0）
        if honmei1_top is not None and honmei1_top not in subset:
            continue
        plan = _evaluate_budget_subset(subset, budget, unit=unit, method=method)
        if not plan:
            continue
        plan["selected_count"] = len(subset)
        plan["strategy_name"] = strategy["name"]
        plan["strategy_description"] = strategy["description"]
        plan["distribution"] = method
        if best_plan is None:
            best_plan = plan
            continue

        current_key = (
            1 if plan["no_trigarami"] else 0,
            plan["min_profit"],
            plan["expected_profit"],
            -plan["selected_count"] if strategy["prefer_fewer_bets"] else plan["selected_count"],
        )
        best_key = (
            1 if best_plan["no_trigarami"] else 0,
            best_plan["min_profit"],
            best_plan["expected_profit"],
            -best_plan["selected_count"] if strategy["prefer_fewer_bets"] else best_plan["selected_count"],
        )
        if current_key > best_key:
            best_plan = plan

    return best_plan


# ── 沈みリスク計算（v5.22） ────────────────────────────────────────
_VENUE_W1_WINRATE_CACHE: dict | None = None
_TOP1_FOLLOWERS_CACHE: dict | None = None


def _load_venue_w1_winrate() -> dict:
    """data/venues/stats/w1_winrate.json をロード（キャッシュ）。

    ⚠️ 無いと 1号艇の沈みリスク推定の基準値が定数 0.578 に固定され、
       会場差が消える。2026-09-05 時点でファイルは無く、**生成するスクリプトも
       存在しない**（機能が未完のまま配線だけ入っている）。
       黙って劣化しないよう一度だけ警告する。点検は scripts/preflight_data.py。
    """
    global _VENUE_W1_WINRATE_CACHE
    if _VENUE_W1_WINRATE_CACHE is None:
        path = BASE_DIR / "data" / "venues" / "stats" / "w1_winrate.json"
        if path.exists():
            try:
                _VENUE_W1_WINRATE_CACHE = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[WARN] w1_winrate.json を読めない: {e} → 基準値0.578で動く")
                _VENUE_W1_WINRATE_CACHE = {}
        else:
            print(f"[WARN] 会場別1号艇勝率が無い: {path}\n"
                  f"       沈みリスクの基準値が全国平均0.545に固定され会場差が消える。"
                  f"作り直し: python3 scripts/build_w1_winrate.py --write")
            _VENUE_W1_WINRATE_CACHE = {}
    return _VENUE_W1_WINRATE_CACHE


def _load_top1_followers() -> dict:
    """data/venues/stats/top1_followers.json をロード（キャッシュ）"""
    global _TOP1_FOLLOWERS_CACHE
    if _TOP1_FOLLOWERS_CACHE is None:
        path = BASE_DIR / "data" / "venues" / "stats" / "top1_followers.json"
        if path.exists():
            try:
                _TOP1_FOLLOWERS_CACHE = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                _TOP1_FOLLOWERS_CACHE = {}
        else:
            _TOP1_FOLLOWERS_CACHE = {}
    return _TOP1_FOLLOWERS_CACHE


def get_top1_followers(jcd: str, w1_winner: int, min_n: int = 8) -> list[dict]:
    """
    会場 jcd で 1着=w1_winner だった場合の最頻 2-3着パターン TOP5 を返す。
    サンプル数が min_n 未満なら空リスト（信頼できない統計のため除外）。
    各要素: {"combo": "X-Y-Z", "count": N, "pct": 0.XXX}
    """
    table = _load_top1_followers()
    by_winner = (table.get(jcd, {}) or {}).get("by_winner", {})
    data = by_winner.get(str(w1_winner), {})
    if not data or data.get("n", 0) < min_n:
        return []
    return data.get("top_combos", [])


def estimate_w1_winrate(scored: list, jcd: str) -> dict:
    """
    1号艇の推定1着率を返す。

    入力:
      scored: スコア降順ソート済みの全6艇のリスト
      jcd:    会場コード

    出力 dict:
      base_rate:      会場ベース1号艇1着率
      grade_mult, score_rank_mult, st_mult, gw_mult: 補正係数
      estimated:      最終推定1着率 [0.05, 0.95]
      sink_risk:      1 - estimated（沈みリスク）
      w1_score_rank:  1号艇のscore順位（1始まり）
      w1_grade:       1号艇のグレード
      reasons:        補正の説明文字列

    背景: v5.20 verify 2440R 分析より、1号艇=B1×特定会場 / score非1位 / ST遅 / 勝率低
    の各条件で1着率が -15〜-27pt 低下することが判明。これらの合成で推定。
    """
    venue_data = _load_venue_w1_winrate().get(jcd, {})
    # フォールバックは実測の全国平均 54.5%（79,867レース）。
    # 以前は 0.578 だったが出典不明で、実測より 3.3pt 高い＝全会場で一律に
    # 1号艇を堅く見積もり、sink_risk が低く出て荒れ判定が鈍る方向にズレていた。
    base_rate = float(venue_data.get("overall_w1_winrate", 0.545))

    # waku=1 の艇を探す
    w1_row = next((r for r in scored if int(r.get("waku", 0)) == 1), None)
    if not w1_row:
        return {
            "base_rate": base_rate, "grade_mult": 1.0, "score_rank_mult": 1.0,
            "st_mult": 1.0, "gw_mult": 1.0,
            "estimated": base_rate, "sink_risk": round(1 - base_rate, 3),
            "w1_score_rank": None, "w1_grade": "", "reasons": [],
        }

    # 1号艇の grade
    w1_grade = (w1_row.get("racer", {}) or {}).get("grade", "") or w1_row.get("grade", "")
    grade_mult_map = {"A1": 1.25, "A2": 1.10, "B1": 0.70, "B2": 0.65}
    grade_mult = grade_mult_map.get(w1_grade, 1.0)

    # score順位
    sorted_by_score = sorted(scored, key=lambda r: -r.get("score", 0))
    try:
        w1_score_rank = next(i + 1 for i, r in enumerate(sorted_by_score) if int(r.get("waku", 0)) == 1)
    except StopIteration:
        w1_score_rank = 6
    score_rank_mult_map = {1: 1.0, 2: 0.70, 3: 0.55, 4: 0.60, 5: 0.65, 6: 0.65}
    score_rank_mult = score_rank_mult_map.get(w1_score_rank, 0.65)

    # ST相対 (w1_st - min(others))
    def get_st(row):
        rm = row.get("raw_metrics", {}) or {}
        st = rm.get("st", {}) or {}
        return st.get("hist_avg") or st.get("racecard_avg") or _avg_st_from_scored(row)
    w1_st = get_st(w1_row)
    other_sts = [get_st(r) for r in scored if int(r.get("waku", 0)) != 1]
    other_sts = [s for s in other_sts if s and s > 0]
    if other_sts and w1_st and w1_st > 0:
        st_gap = w1_st - min(other_sts)
    else:
        st_gap = 0.0
    if st_gap <= -0.005:   st_mult = 1.35
    elif st_gap <= 0:      st_mult = 1.15
    elif st_gap <= 0.005:  st_mult = 1.00
    elif st_gap <= 0.020:  st_mult = 0.85
    else:                  st_mult = 0.75

    # 全国勝率
    racer = w1_row.get("racer", {}) or {}
    gw = float(racer.get("global_win", 0) or 0)
    if gw >= 15.0:   gw_mult = 1.10
    elif gw >= 10.0: gw_mult = 1.00
    elif gw >= 5.0:  gw_mult = 0.85
    else:            gw_mult = 0.70

    estimated = base_rate * grade_mult * score_rank_mult * st_mult * gw_mult
    estimated = max(0.05, min(0.95, estimated))

    reasons = []
    if grade_mult < 1.0:        reasons.append(f"{w1_grade}級 ×{grade_mult:.2f}")
    if score_rank_mult < 1.0:   reasons.append(f"scoreランク{w1_score_rank}位 ×{score_rank_mult:.2f}")
    if st_mult < 1.0:           reasons.append(f"ST不利({st_gap:+.3f}) ×{st_mult:.2f}")
    elif st_mult > 1.0:         reasons.append(f"ST有利({st_gap:+.3f}) ×{st_mult:.2f}")
    if gw_mult < 1.0:           reasons.append(f"勝率{gw:.1f} ×{gw_mult:.2f}")

    return {
        "base_rate":       round(base_rate, 3),
        "grade_mult":      grade_mult,
        "score_rank_mult": score_rank_mult,
        "st_mult":         st_mult,
        "gw_mult":         gw_mult,
        "st_gap":          round(st_gap, 3),
        "estimated":       round(estimated, 3),
        "sink_risk":       round(1 - estimated, 3),
        "w1_score_rank":   w1_score_rank,
        "w1_grade":        w1_grade,
        "reasons":         reasons,
    }


# ── 信頼度計算（v5.8） ────────────────────────────────────────────
def _calc_confidence(scored: list, sink_risk: float | None = None) -> tuple[int, bool, bool]:
    """
    1位・2位のスコア差から信頼度%と荒れフラグを返す。
    戻り値: (confidence_pct, is_rough, is_dominant)
    ベースは 55〜90% に抑え、以下で減点する:
      - 展示データなし
      - コメント根拠が薄い
      - 1位〜3位が接近
      - v5.22: sink_risk >= 0.55 で荒れ判定強化（1号艇が score 上位でない時に頻発）
    """
    if len(scored) < 2:
        return 70, False, False
    gap = max(0.0, scored[0]["score"] - scored[1]["score"])
    gap13 = max(0.0, scored[0]["score"] - scored[min(2, len(scored) - 1)]["score"])

    # ベース: 55〜90
    gap12_norm = min(gap, 0.060) / 0.060
    gap13_norm = min(gap13, 0.120) / 0.120
    pct = 55 + 25 * gap12_norm + 10 * gap13_norm

    # 展示データ未取得なら大きく減点
    top3 = scored[:3]
    has_exhibition = any(
        bool(((r.get("raw_metrics", {}) or {}).get("exhibition", {}) or {}).get("time"))
        for r in top3
    )
    if not has_exhibition:
        pct -= 8

    # コメント根拠が薄い場合は減点
    comment_count = sum(
        1 for r in top3
        if bool(((r.get("raw_metrics", {}) or {}).get("comment", {}) or {}).get("text"))
    )
    if comment_count <= 1:
        pct -= 4
    elif comment_count == 2:
        pct -= 2

    # 上位拮抗時は減点
    if gap13 < 0.050:
        pct -= 6
    elif gap13 < 0.080:
        pct -= 3

    # v5.22: 沈みリスク補正（1号艇が score上位でない/弱い場合の荒れ予想）
    if sink_risk is not None:
        if sink_risk >= 0.65:
            pct -= 10
        elif sink_risk >= 0.55:
            pct -= 5
        elif sink_risk <= 0.15:
            pct += 3  # 1号艇本命確信時

    pct = round(pct)
    is_rough = (gap <= 0.015) or (sink_risk is not None and sink_risk >= 0.55)
    is_dominant = (gap >= 0.040 and gap13 >= 0.080 and pct >= 85 and
                   (sink_risk is None or sink_risk <= 0.20))
    return int(max(55, min(90, pct))), is_rough, is_dominant


def _format_confidence(confidence_pct: int) -> str:
    return f"{int(confidence_pct)}%"


def _confidence_class(confidence_pct: int) -> str:
    if confidence_pct >= 85:
        return "conf-high"
    if confidence_pct >= 65:
        return "conf-mid"
    return "conf-low"


def _rank_marker(rank_no: int, is_dominant: bool = False) -> str:
    if rank_no == 1:
        return "★" if is_dominant else "◎"
    if rank_no == 2:
        return "○"
    if rank_no == 3:
        return "▲"
    if rank_no == 4:
        return "△"
    return ""


def _display_bet_label(label: str, reason: str = "") -> str:
    """
    内部ラベルを画面表示用ラベルへ変換する。
    - 本命① -> ◎本線
    - 本命② -> ○対抗
    - 穴     -> ▲単穴 / 穴狙い / △押さえ
    - 出目④  -> △押さえ
    """
    clean = (label or "").strip()
    reason = reason or ""
    if clean == "本命①":
        return "◎本線"
    if clean == "本命②":
        return "○対抗"
    if clean == "出目④":
        return "△押さえ"
    if clean == "穴":
        if "1着狙い" in reason:
            return "穴狙い"
        if "2着差し" in reason:
            return "▲単穴"
        if "穴要因なし" in reason or "3着" in reason:
            return "△押さえ"
        return "▲単穴"
    return clean


# ── オッズからバリュー候補を検出 ─────────────────────────────────
def _find_value_bets(scored, odds_data):
    """
    スコアが高いがオッズも高い（=人気薄）選手を「バリュー候補」として返す。
    odds_data: {"odds_3t": {"123": 15.6, ...}}
    """
    if not odds_data:
        return []
    odds_3t = odds_data.get("odds_3t", {})
    if not odds_3t:
        return []

    # 1着に来る選手ごとの最低オッズを集計
    min_odds_by_first = {}
    for combo, odds in odds_3t.items():
        first = combo[0] if combo else ""
        if first and isinstance(odds, (int, float)):
            if first not in min_odds_by_first or odds < min_odds_by_first[first]:
                min_odds_by_first[first] = odds

    values = []
    for i, r in enumerate(scored[:4]):   # 上位4着まで対象
        waku_str = str(r["waku"])
        min_odds = min_odds_by_first.get(waku_str)
        if min_odds is None:
            continue
        # スコアが2位以内 かつ 最低オッズが10倍以上 → バリュー
        if i <= 1 and min_odds >= 10.0:
            values.append({
                "waku": r["waku"], "name": r["name"],
                "score": r["score"], "min_odds": min_odds,
            })
    return values


# ── tournament_guide.md 生成 (v5.3) ──────────────────────────────
def _generate_tournament_guide_md(out_dir: Path) -> None:
    """
    data/tournament_grades.json の内容を Markdown に変換して
    output/data/tournament_guide.md として保存する。
    会場ガイド（venue_guide.md）と同じ位置に出力。
    """
    data = _TOURNAMENT_GRADE_DATA
    if not data:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "tournament_guide.md"

    lines = [
        "# ボートレース 大会グレード別傾向ガイド",
        "",
        "このファイルは `predictor.py` 実行時に `data/tournament_grades.json` から自動生成されます。",
        f"最終更新: {datetime.date.today().isoformat()}",
        "",
        "---",
        "",
        "## グレード別 コース補正サマリー",
        "",
        "| グレード | 1コース平均勝率 | 3連単平均払戻 | 荒れ指数 | 概要 |",
        "|:---:|:---:|:---:|:---:|:---|",
    ]

    # ⚠️ 数値前提で書式化しない。calibrate_tournament_grades.py が作る表には
    #    course1_win_pct / avg_payout_3t が無いことがあり、既定値 "-" を
    #    f"¥{...:,}" に渡して ValueError で落ちていた。テーブルが存在しない間は
    #    このループに入らなかったため、2026-09-05 に有効化して初めて表面化した。
    #    **「データが無いと通らない経路」はデータを入れた瞬間に初走行になる。**
    def _num(v, fmt: str) -> str:
        try:
            return format(float(v), fmt)
        except (TypeError, ValueError):
            return "-"

    grades_dict = data.get("grades", {})
    order = ["SG", "G1", "G2", "G3", "一般", "レディース"]
    for gkey in order:
        g = grades_dict.get(gkey)
        if not g:
            continue
        c1     = _num(g.get("course1_win_pct"), ".1f")
        payout = _num(g.get("avg_payout_3t"), ",.0f")
        vol    = _num(g.get("volatility", 1.0), ".2f")
        note   = (g.get("note") or "")[:40] + ("…" if len(g.get("note") or "") > 40 else "")
        c1_str     = f"{c1}%" if c1 != "-" else "-"
        payout_str = f"¥{payout}" if payout != "-" else "-"
        lines.append(f"| **{gkey}** | {c1_str} | {payout_str} | {vol} | {note} |")

    lines += [
        "",
        "---",
        "",
        "## グレード別 詳細",
        "",
    ]

    for gkey in order:
        g = grades_dict.get(gkey)
        if not g:
            continue
        cm  = g.get("course_mod", [1.0]*6)
        cm_str = " / ".join(
            f"{i+1}コース×{v:.2f}" for i, v in enumerate(cm)
        )
        # 数値前提の書式化はしない（欠損時は "-" が来るため。上の _num と同じ理由）
        c1_d     = _num(g.get("course1_win_pct"), ".1f")
        payout_d = _num(g.get("avg_payout_3t"), ",.0f")
        vol_d    = _num(g.get("volatility", 1.0), ".2f")
        lines += [
            f"### {gkey} ({g.get('display', gkey)})",
            "",
            f"- **1コース平均勝率**: {c1_d + '%' if c1_d != '-' else '-'}",
            f"- **3連単平均払戻**: {'¥' + payout_d if payout_d != '-' else '-'}",
            f"- **荒れ指数 (volatility)**: {vol_d}  "
            "（1.0=標準、1.15以上=荒れやすい、0.90以下=堅い）",
            f"- **コース補正係数**: {cm_str}",
            f"- **特徴**: {g.get('note', '') or '-'}",
            "",
        ]

    lines += [
        "---",
        "",
        "## レディース専用大会",
        "",
        "| 大会名 | 1コース勝率 | 荒れ指数 | 特徴 |",
        "|:---|:---:|:---:|:---|",
    ]

    ladies_dict = data.get("ladies_tournaments", {})
    for lname, lt in ladies_dict.items():
        c1   = lt.get("course1_win_pct", "-")
        vol  = lt.get("volatility", 1.15)
        note = lt.get("note", "")[:50] + ("…" if len(lt.get("note","")) > 50 else "")
        lines.append(f"| {lname} | {c1}% | {vol:.2f} | {note} |")

    lines += [
        "",
        "---",
        "",
        "## 判断指針",
        "",
        "- **SG / G1**: 1コース選手（特にA1上位）を厚め本命で。スコア差が小さくても1コースは外しにくい。",
        "- **G2 / G3**: 標準的に扱う。会場特性・モーターを重視。",
        "- **一般**: 会場特性・天候・展示タイムが最もスコアに直結。外枠まくりも頻発。",
        "- **レディース（全員女性）**: 1コース過信禁物。差し・まくり決まりやすい。"
        "外枠（4-6コース）の選手もスコアに関わらず穴候補として警戒。",
        "  モーター・展示タイム差の影響が男性戦より大きい傾向。",
        "",
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[INFO] tournament_guide.md 生成: {out_path}")


# ── HTMLエスケープ ────────────────────────────────────────────────
def _he(s) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def _display_venue_name(name: str) -> str:
    return re.sub(r"\(\d{2}\)$", "", str(name)).strip()


_WAKU_COLORS = {
    1: ("#ffffff", "#222222", "#c9c9c9"),
    2: ("#111111", "#ffffff", "#111111"),
    3: ("#d73030", "#ffffff", "#d73030"),
    4: ("#2f6fd6", "#ffffff", "#2f6fd6"),
    5: ("#f0d44c", "#222222", "#d3b11f"),
    6: ("#4aa35c", "#ffffff", "#4aa35c"),
}


def _waku_label(waku, name="", prefix="") -> str:
    try:
        w = int(waku)
    except (TypeError, ValueError):
        w = 0
    bg, fg, border = _WAKU_COLORS.get(w, ("#eef3ff", "#222222", "#c8d4f0"))
    return (
        '<span class="waku-name-cell">'
        f'<span class="waku-chip" style="background:{bg};color:{fg};border-color:{border};">{_he(w)}</span>'
        f'<span class="waku-name">{prefix}{_he(name)}</span>'
        '</span>'
    )


def _mini_meter(value, max_value=100.0, color="linear-gradient(90deg,#4f7cff,#79a7ff)"):
    """小さなバー表示用HTMLを返す。"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = 0.0
    if max_value <= 0:
        max_value = 1.0
    pct = max(0.0, min(100.0, num / max_value * 100.0))
    return (
        '<span class="meter">'
        f'<span class="meter-fill" style="width:{pct:.1f}%;background:{color}"></span>'
        '</span>'
    )


def _flow_block(rows):
    """実データ → 採用値 → 寄与 の3段表示を返す。"""
    parts = ['<div class="flow-cell">']
    for label, value, tone in rows:
        cls = f'flow-value {tone}' if tone else 'flow-value'
        parts.append(
            f'<div class="flow-row"><span class="flow-label">{_he(label)}</span>'
            f'<span class="{cls}">{_he(value)}</span></div>'
        )
    parts.append('</div>')
    return "".join(parts)


def _print_raw_metrics_section(scored):
    print('<div class="sec">🧭 実データ</div>')
    print('<div class="tbl-wrap"><table class="sticky-name-table">'
          '<tr><th>枠・名前</th><th>全国勝率</th><th>当地勝率</th><th>モーター2連</th>'
          '<th>ボート2連</th><th>平均ST</th><th>今節成績</th><th>展示</th><th>コメント根拠</th></tr>')
    for r in scored:
        raw = r.get("raw_metrics", {})
        g = raw.get("global_win", {})
        l = raw.get("local_win", {})
        m = raw.get("motor_2rate", {})
        b2 = raw.get("boat_2rate", {})
        st = raw.get("st", {})
        se = raw.get("series", {})
        ex = raw.get("exhibition", {})
        cm = raw.get("comment", {})

        g_hist = g.get("hist_pct")
        l_hist = l.get("hist_pct")
        m_hist = m.get("hist_pct")
        g_hist_str = f'{g_hist:.2f}%' if isinstance(g_hist, (int, float)) else '-'
        l_hist_str = f'{l_hist:.2f}%' if isinstance(l_hist, (int, float)) else '-'
        m_hist_str = f'{m_hist:.1f}%' if isinstance(m_hist, (int, float)) else '-'

        global_html = _flow_block([
            ("実データ", f'今期 {g.get("season_pct",0):.2f}% / 実績 {g_hist_str}', "tone-data"),
            ("採用値", f'{g.get("adopted_pct",0):.2f}%', "tone-picked"),
            ("寄与", f'{r["breakdown"].get("global_win_rate",0):.3f}', "tone-score"),
        ])
        local_html = _flow_block([
            ("実データ", f'今期 {l.get("season_pct",0):.2f}% / 実績 {l_hist_str}', "tone-data"),
            ("採用値", f'{l.get("adopted_pct",0):.2f}%', "tone-picked"),
            ("寄与", f'{r["breakdown"].get("local_win_rate",0):.3f}', "tone-score"),
        ])
        motor_html = _flow_block([
            ("実データ", f'今期 {m.get("season_pct",0):.1f}% / 実績 {m_hist_str} ({m.get("hist_races",0)}走)', "tone-data"),
            ("採用値", f'{m.get("adopted_pct",0):.1f}%', "tone-picked"),
            ("寄与", f'{r["breakdown"].get("motor_2rate",0):.3f}', "tone-score"),
        ])

        st_hist = st.get("hist_avg")
        st_hist_str = f'{st_hist:.3f}' if isinstance(st_hist, (int, float)) and st_hist > 0 else '-'
        st_html = _flow_block([
            ("実データ", f'出走表 {st.get("racecard_avg",0):.3f} / 実績 {st_hist_str}', "tone-data"),
            ("補正", f'F{st.get("f_count",0)} / L{st.get("l_count",0)}', "tone-picked"),
            ("寄与", f'{r["breakdown"].get("st_score",0):.3f}', "tone-score"),
        ])
        # v5.19 #3: series.races から「コース-着順」ペアで表示（無ければ ranks のみ）
        se_races = se.get("races") or []
        if se_races:
            series_str = " ".join(f'{s.get("course")}→{s.get("rank")}' for s in se_races)
        elif se.get("ranks"):
            series_str = " ".join(str(x) for x in se["ranks"])
        else:
            series_str = "初日/実績なし"

        ex_parts = []
        if ex.get("time"):
            ex_parts.append(f'T {ex.get("time")}')
        if ex.get("start_timing"):
            ex_parts.append(f'ST {ex.get("start_timing")}')
        if ex.get("tilt"):
            ex_parts.append(f'ﾁﾙﾄ {ex.get("tilt")}')
        entry_course = ex.get("entry_course")
        actual_course = ex.get("actual_course")
        if str(entry_course).strip():
            ex_parts.append(f'進入 {entry_course}')
        elif actual_course:
            ex_parts.append(f'進入 {actual_course}')
        if ex.get("prev_rank"):
            ex_parts.append(f'前走 {ex.get("prev_rank")}着')
        exhibition_str = " / ".join(str(p) for p in ex_parts) if ex_parts else "未取得"

        cm_text = cm.get("text", "") or "コメントなし"
        if len(cm_text) > 40:
            cm_text = cm_text[:40] + "…"
        kw_items = cm.get("matched_keywords", []) or []
        def _fmt_kw(item):
            if isinstance(item, dict):
                return f'{item.get("keyword","")}({item.get("delta", 0):+0.2f})'
            return str(item)
        kw_text = ", ".join(_fmt_kw(item) for item in kw_items[:4]) if kw_items else "一致なし"
        comment_html = _flow_block([
            ("出典", cm.get("source","-"), "tone-data"),
            ("判定", f'{cm.get("final_label","―")} raw {cm.get("raw_score",0):.2f} / 履歴 {cm.get("history_bonus",0):+.2f}', "tone-picked"),
            ("一致", kw_text, ""),
            ("本文", cm_text, ""),
        ])

        boat_str = f"{b2.get('season_pct', 0):.1f}%"
        print(f'<tr>'
              f'<td>{_waku_label(r["waku"], r["name"])}</td>'
              f'<td>{global_html}</td>'
              f'<td>{local_html}</td>'
              f'<td>{motor_html}</td>'
              f'<td><div class="single-metric"><div>{_he(boat_str)}</div>{_mini_meter(b2.get("season_pct", 0), 100.0, "linear-gradient(90deg,#6aa84f,#a4d17b)")}</div></td>'
              f'<td>{st_html}</td>'
              f'<td>{_he(series_str)}</td>'
              f'<td>{_he(exhibition_str)}</td>'
              f'<td>{comment_html}</td>'
              f'</tr>')
    print('</table></div>')


def _print_comment_section(scored):
    pitreport_data_for_display = scored[0].get("pitreport_data") if scored else None
    has_pitreport = bool(pitreport_data_for_display and pitreport_data_for_display.get("comments"))
    has_comments = any(r.get("comment_data") for r in scored)
    has_player_review = any(r.get("player_review") for r in scored)
    print('<div class="sec">💬 コメント実データ</div>')
    if has_pitreport or has_comments or has_player_review:
        print('<div class="tbl-wrap"><table class="sticky-name-table">'
              '<tr><th>枠・名前</th><th>状態</th><th>コメント</th><th>判定根拠</th></tr>')
        for r in sorted(scored, key=lambda x: x["waku"]):
            comment_detail = explain_comment_score(
                r["waku"], r.get("comment_data"),
                pitreport_data=r.get("pitreport_data"),
                player_review=r.get("player_review"),
                reg_no=r.get("reg_no", ""))
            text = comment_detail.get("text", "")
            src = comment_detail.get("source", "")
            cs_raw = comment_detail.get("raw_score", 0.5)
            if cs_raw > 0.55:
                bar, bc = "▲", "cmt-good"
            elif cs_raw < 0.45:
                bar, bc = "▼", "cmt-bad"
            else:
                bar, bc = "―", ""
            if text:
                src_tag = (f'<small style="color:#888;font-weight:normal"> [{_he(src)}]</small>'
                           if src else "")
                cmt = f'{_he(text)}{src_tag}'
            else:
                cmt = "（コメントなし）"
            kw_items = comment_detail.get("matched_keywords", []) or []
            if kw_items:
                def _fmt_kw2(item):
                    if isinstance(item, dict):
                        return f'{item.get("keyword","")}({item.get("delta", 0):+0.2f})'
                    return str(item)
                reason = " / ".join(_fmt_kw2(item) for item in kw_items[:5])
            else:
                reason = "キーワード一致なし"
            reason += f' / raw {cs_raw:.2f}'
            print(f'<tr><td>{_waku_label(r["waku"], r["name"])}</td>'
                  f'<td class="{bc}">{bar}</td>'
                  f'<td>{cmt}</td>'
                  f'<td>{_he(reason)}</td></tr>')
        print('</table></div>')
    else:
        print('<div class="tbl-wrap"><table class="sticky-name-table">'
              '<tr><th>枠・名前</th><th>状態</th><th>コメント</th><th>判定根拠</th></tr>')
        print('<tr><td colspan="4">⚠️ コメント未取得（R1-6はピットレポート対象外 / データ取得前）</td></tr>')
        print('</table></div>')


def _print_exhibition_section(scored, exhibition):
    has_ex = exhibition and any(
        safe_float(e.get("exhibition_time", 0)) > 0
        for e in exhibition.get("exhibition", [])
    )
    print('<div class="sec">🏁 展示実データ</div>')
    if has_ex:
        ex_list = exhibition.get("exhibition", [])
        ex_sorted = sorted(
            [e for e in ex_list if safe_float(e.get("exhibition_time", 0)) > 0],
            key=lambda e: safe_float(e.get("exhibition_time", 99))
        )
        t_min = safe_float(ex_sorted[0].get("exhibition_time", 0)) if ex_sorted else 0
        print('<div class="tbl-wrap"><table class="sticky-name-table">'
              '<tr><th>枠・名前</th><th>展示T</th><th>チルト</th>'
              '<th>進入</th><th>前走ST</th><th>前走着</th><th>評価</th></tr>')
        for rank, e in enumerate(ex_sorted, 1):
            w = e.get("waku", "?")
            t = safe_float(e.get("exhibition_time", 0))
            tilt = e.get("tilt", "-")
            entry = e.get("entry_course", "")
            st_raw = e.get("start_timing", "-")
            p_rank = e.get("prev_rank", "-")
            name = next((r["name"] for r in scored if r["waku"] == w), "")
            diff = t - t_min
            if rank == 1:
                ev_lbl, ec = "★最速", "ex-best"
            elif diff <= 0.03:
                ev_lbl, ec = "▲好調", "ex-good"
            elif diff >= 0.10:
                ev_lbl, ec = "▼遅", "ex-slow"
            else:
                ev_lbl, ec = "", ""
            if str(entry).strip() == "":
                entry_str = "—"
            elif str(entry).isdigit():
                entry_str = f"{entry}コース"
                if int(entry) != int(w):
                    entry_str += "⚠"
            else:
                entry_str = str(entry)
            tc = "tilt-neg" if safe_float(str(tilt), 999) < 0 else ""
            print(f'<tr>'
                  f'<td>{_waku_label(w, name)}</td>'
                  f'<td><b>{t:.2f}</b></td>'
                  f'<td class="{tc}">{_he(str(tilt))}</td>'
                  f'<td>{_he(entry_str)}</td>'
                  f'<td>{_he(str(st_raw))}</td>'
                  f'<td>{_he(str(p_rank))}</td>'
                  f'<td class="{ec}">{ev_lbl}</td>'
                  f'</tr>')
        co = exhibition.get("course_order", [])
        if co:
            co_str = " &nbsp; ".join(
                f'{c["course"]}{"[F]" if c.get("foul") else ""}({c["st"]:.2f})'
                for c in co
            )
            print(f'<tr class="co-row"><td colspan="7">スタート展示順: {co_str}</td></tr>')
        print('</table></div>')
    else:
        print('<p class="no-data">未取得（発走前に自動取得予定）</p>')


def _print_bet_section(scored, weather, odds_data, combo_stats, exhibition_data=None,
                       date_str: str = "", race_no: int = 0, race_name: str = "",
                       jcd: str = ""):
    confidence_pct, is_rough, _ = _calc_confidence(scored)
    bets = _suggest_3rentan(scored, weather, combo_stats=combo_stats, exhibition_data=exhibition_data,
                            date_str=date_str, race_no=race_no, race_name=race_name, jcd=jcd)
    has_odds = bool(odds_data and odds_data.get("odds_3t"))
    rough_str = ' <span class="conf-low">⚡荒れ注意</span>' if is_rough else ""
    conf_cls = _confidence_class(confidence_pct)

    print('<div class="sec">💴 予算別買い目</div>')
    if has_odds:
        # v5.24: 配分案の母集合は「公開する買い目」に揃える
        plan_bets = selected_bets(bets)
        budget_plans = []
        for amount in (500, 1000):
            plan = _build_budget_plan(plan_bets, scored, odds_data, budget=amount, unit=100)
            if plan:
                budget_plans.append(plan)
        if budget_plans:
            for plan in budget_plans:
                status = "トリガミ回避" if plan["no_trigarami"] else "トリガミ回避不可"
                status_cls = "plan-ok" if plan["no_trigarami"] else "plan-ng"
                print('<div class="budget-box">')
                print(f'<div class="budget-head">予算 {plan["budget"]:,}円'
                      f' / {plan.get("strategy_name","配分案")}'
                      f' <span class="{status_cls}">{status}</span>'
                      f' <span class="budget-note">最悪収支 {plan["min_profit"]:+,}円 / 期待収支 {plan["expected_profit"]:+,}円</span></div>')
                if plan.get("strategy_description"):
                    print(f'<div class="note">{_he(plan["strategy_description"])}</div>')
                print('<div class="tbl-wrap"><table class="budget-tbl">'
                      '<tr><th>種別</th><th>買い目</th><th>配分</th><th>オッズ</th><th>的中時収支</th><th>理由</th></tr>')
                for row in plan["rows"]:
                    reason = next((r for l, c, r in plan_bets if l.strip() == row["label"] and c == row["combo"]), "")
                    display_label = _display_bet_label(row["label"], reason)
                    print(f'<tr>'
                          f'<td>{_he(display_label)}</td>'
                          f'<td><span class="bet">{_he(row["combo"])}</span></td>'
                          f'<td>{row["stake"]:,}円</td>'
                          f'<td>{row["odds"]:.1f}倍</td>'
                          f'<td>{row["profit_if_hit"]:+,}円</td>'
                          f'<td>{_he(reason)}</td>'
                          f'</tr>')
                print('</table></div>')
                print('</div>')
        else:
            print('<p class="no-data">オッズはありますが、予算配分案を作れませんでした。</p>')
    else:
        print('<p class="no-data">オッズ未取得のため、500円/1000円の配分案は未表示です。</p>')

    # v5.16: 2セクション構成 (本命 最大4 / その他 最大4)
    honmei, others = _normalize_bets(bets)

    def _cell_for_combo(combo: str):
        ev_val = _calc_bet_ev(combo, scored, odds_data) if has_odds else None
        if has_odds and ev_val is not None:
            o = odds_data.get("odds_3t", {}).get(combo.replace("-", ""))
            ev_str = f"{ev_val:.2f}"
            if ev_val >= 1.20:
                ev_td = f'<span class="ev-high">{ev_str} 💰</span>'
            elif ev_val < 0.80:
                ev_td = f'<span class="ev-low">{ev_str} ⚡</span>'
            else:
                ev_td = ev_str
            odds_td = f"{o:.1f}倍" if o else "---"
        else:
            odds_td, ev_td = "---", "---"
        return odds_td, ev_td

    print('<div class="sec">🎯 システム選択の買い目</div>')
    print('<div class="bet-box">')
    print(f'<div class="conf-line">📊 信頼度: <span class="{conf_cls}">{_format_confidence(confidence_pct)}</span>{rough_str}</div>')

    # ── 本命セクション（最大4点、買い目のみ表示） ──
    print('<div class="bet-title">本命（最大4点）</div>')
    if honmei:
        print('<div class="tbl-wrap"><table class="bet-tbl">'
              '<tr><th>買い目</th><th>オッズ</th><th>EV</th><th>理由</th></tr>')
        for item in honmei:
            combo = item["combo"]
            reason = item.get("reason", "")
            odds_td, ev_td = _cell_for_combo(combo)
            print(f'<tr>'
                  f'<td><span class="bet bet1">{combo}</span></td>'
                  f'<td>{odds_td}</td><td>{ev_td}</td>'
                  f'<td>{_he(reason)}</td></tr>')
        print('</table></div>')
    else:
        print('<p class="no-data">本命候補なし</p>')

    # ── その他セクション（最大4点、subtype付き） ──
    print('<div class="bet-title" style="margin-top:12px;">その他（最大4点 抑え／対抗／穴）</div>')
    if others:
        print('<div class="tbl-wrap"><table class="bet-tbl">'
              '<tr><th>種別</th><th>買い目</th><th>オッズ</th><th>EV</th><th>理由</th></tr>')
        for item in others:
            subtype = item["subtype"]
            combo = item["combo"]
            reason = item.get("reason", "")
            odds_td, ev_td = _cell_for_combo(combo)
            if subtype == "穴":
                bc_cls = "bet bet-ana"
                badge_cls = "subtype-ana"
            elif subtype == "対抗":
                bc_cls = "bet bet2"
                badge_cls = "subtype-tai"
            else:  # 抑え
                bc_cls = "bet bet-sub"
                badge_cls = "subtype-oshi"
            print(f'<tr>'
                  f'<td><span class="subtype-badge {badge_cls}">{_he(subtype)}</span></td>'
                  f'<td><span class="{bc_cls}">{combo}</span></td>'
                  f'<td>{odds_td}</td><td>{ev_td}</td>'
                  f'<td>{_he(reason)}</td></tr>')
        print('</table></div>')
    else:
        print('<p class="no-data">その他候補なし</p>')

    print('</div>')  # bet-box


def _print_score_section(scored):
    _, _, is_dominant = _calc_confidence(scored)
    print('<div class="sec">⚙️ システム計算ロジック</div>')
    print('<p class="note">※ 下表は、実データに係数を掛けた後の寄与値です。</p>')
    print('<div class="tbl-wrap"><table class="sticky-score-table">'
          '<tr><th>順</th><th>枠・名前</th><th>級</th>'
          '<th>総合</th><th>全勝寄与</th><th>当地寄与</th><th>モータ寄与</th>'
          '<th>コース寄与</th><th>ST寄与</th><th>展示寄与</th><th>枠実績寄与</th><th>コメ寄与</th><th>ｴﾝｼﾞﾝ補正</th></tr>')
    for i, r in enumerate(scored, 1):
        b = r["breakdown"]
        flag = _rank_marker(i, is_dominant=is_dominant)
        grade = r["grade"]
        gc = "grade-a1" if grade == "A1" else ("grade-a2" if grade == "A2" else "grade-b")
        rc = ' class="rank1"' if i == 1 else ""
        gmark = '<span style="color:#e00020;font-size:11px;font-weight:bold;">♥</span> ' if is_female(r.get("reg_no",""), r.get("player_stats",{})) else ""
        print(f'<tr{rc}>'
              f'<td>{i}{flag}</td>'
              f'<td>{_waku_label(r["waku"], r["name"], prefix=gmark)}</td>'
              f'<td class="{gc}">{_he(grade)}</td>'
              f'<td><b>{r["score"]:.4f}</b></td>'
              f'<td>{b.get("global_win_rate",0):.3f}</td>'
              f'<td>{b.get("local_win_rate",0):.3f}</td>'
              f'<td>{b.get("motor_2rate",0):.3f}</td>'
              f'<td>{b.get("course_advantage",0):.3f}'
              + (f'<span style="font-size:10px;color:#c04000"> ▶{b["_entry_course_note"]}コース</span>'
                 if "_entry_course_note" in b else "")
              + f'</td>'
              f'<td>{b.get("st_score",0):.3f}</td>'
              f'<td>{b.get("exhibition_score",0):.3f}</td>'
              f'<td>{b.get("hist_waku_score",0):.3f}</td>'
              f'<td>{b.get("comment_score",0):.3f}</td>'
              + (f'<td style="color:{"#c04000" if b.get("engine_bonus",0) < 0 else "#0070c0"}">{b["engine_bonus"]:+.3f}</td>'
                 if "engine_bonus" in b else '<td style="color:#aaa">—</td>')
              + f'</tr>')
    print('</table></div>')


def _write_output_indexes(output_root: Path) -> None:
    """output 配下の会場別 index.html と全体 index.html を再生成する。"""
    venue_dirs = []
    for child in sorted(output_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name == "data":
            continue
        html_files = sorted(
            [p for p in child.glob("*.html") if p.name != "index.html"],
            key=lambda p: p.stem,
            reverse=True,
        )
        if not html_files:
            continue
        venue_dirs.append((child, html_files))

    for venue_dir, html_files in venue_dirs:
        rows = []
        for html_path in html_files:
            date_label = html_path.stem
            rows.append(
                f'<tr><td><a href="{html_path.name}">{date_label}</a></td></tr>'
            )
        venue_index = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{venue_dir.name} index</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 860px; margin: 24px auto; padding: 0 16px; color: #111; }}
h1 {{ font-size: 22px; margin-bottom: 8px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #d9dfe8; padding: 8px 10px; text-align: left; }}
th {{ background: #2c4a8a; color: #fff; }}
tr:nth-child(even) td {{ background: #f7f9fc; }}
a {{ color: #0b57d0; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.back {{ margin-bottom: 16px; display: inline-block; }}
</style>
</head>
<body>
<a class="back" href="../index.html">← output index</a>
<h1>{venue_dir.name}</h1>
<table>
<tr><th>日付</th></tr>
{''.join(rows)}
</table>
</body>
</html>
"""
        (venue_dir / "index.html").write_text(venue_index, encoding="utf-8")

    venue_rows = []
    recent_rows = []
    recent_files = []
    for venue_dir, html_files in venue_dirs:
        venue_rows.append(
            f'<tr><td><a href="{venue_dir.name}/index.html">{venue_dir.name}</a></td><td>{len(html_files)}</td><td>{html_files[0].stem}</td></tr>'
        )
        for html_path in html_files:
            recent_files.append((html_path.stem, venue_dir.name, html_path))
    recent_files.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for date_label, venue_name, html_path in recent_files[:50]:
        recent_rows.append(
            f'<tr><td>{date_label}</td><td>{venue_name}</td><td><a href="{venue_name}/{html_path.name}">{html_path.name}</a></td></tr>'
        )

    root_index = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>boat output index</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 1040px; margin: 24px auto; padding: 0 16px; color: #111; }}
h1 {{ font-size: 24px; margin-bottom: 8px; }}
h2 {{ font-size: 18px; margin-top: 28px; margin-bottom: 8px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #d9dfe8; padding: 8px 10px; text-align: left; }}
th {{ background: #2c4a8a; color: #fff; }}
tr:nth-child(even) td {{ background: #f7f9fc; }}
a {{ color: #0b57d0; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.note {{ color: #666; margin-bottom: 16px; }}
</style>
</head>
<body>
<h1>boat output index</h1>
<p class="note">会場別フォルダへの入口と、最近の出力ファイル一覧です。</p>
<h2>検証</h2>
<table>
<tr><th>区分</th><th>リンク</th></tr>
<tr><td>的中率サマリ</td><td><a href="data/verify_log.html">data/verify_log.html</a></td></tr>
<tr><td>日別詳細</td><td><a href="data/verify/">data/verify/</a></td></tr>
</table>
<h2>会場別</h2>
<table>
<tr><th>会場</th><th>件数</th><th>最新日付</th></tr>
{''.join(venue_rows) if venue_rows else '<tr><td colspan="3">出力ファイルなし</td></tr>'}
</table>
<h2>最近の出力</h2>
<table>
<tr><th>日付</th><th>会場</th><th>ファイル</th></tr>
{''.join(recent_rows) if recent_rows else '<tr><td colspan="3">出力ファイルなし</td></tr>'}
</table>
</body>
</html>
"""
    (output_root / "index.html").write_text(root_index, encoding="utf-8")


# ── 出力 ──────────────────────────────────────────────────────────
def _print_result(jcd, date, race_no, scored, venue, exhibition, weather,
                  tide_data=None, odds_data=None, race_name: str = "", race_category: str = "",
                  start_time: str = "", combo_stats: dict | None = None,
                  tournament_grade: str = "一般"):
    vname     = _display_venue_name(venue["name"] if venue else VENUE_NAMES.get(jcd, jcd))
    season    = get_season(date)
    period    = get_race_period(race_no)
    season_jp = {"spring":"春","summer":"夏","autumn":"秋","winter":"冬"}[season]
    period_jp = {"early":"序盤","middle":"中盤","late":"終盤"}[period]

    venue_note = ""
    tide_note  = ""
    if venue:
        sn = venue.get("seasonal",{}).get(season,{}).get("note","")
        pn = venue.get("race_no_tendency",{}).get(period,{}).get("note","")
        venue_note = f"{sn} / {pn}" if sn or pn else ""
        tide = get_tide_status(weather, tide_data=tide_data, race_no=race_no)
        if tide and venue.get("tidal_conditions"):
            tide_note = venue["tidal_conditions"].get(tide,{}).get("note","")

    tide_info   = get_tide_info(tide_data, race_no)
    tide_label  = tide_info.get("label_jp", "")
    tide_pct    = tide_info.get("height_pct")
    tide_source = "気象庁" if (tide_data and tide_info.get("status")) else ""
    next_ev     = tide_info.get("next_event", {})
    next_note   = next_ev.get("note", "")

    category_label = {"finalist": "🏆優勝/準優", "general": "一般戦", "qualifier": "予選/通常"}
    cat_jp    = category_label.get(race_category, "")

    # グレードバッジ表示
    _grade_badge_map = {
        "SG":       '<span style="background:#c8860a;color:#fff;padding:1px 5px;border-radius:3px;font-size:11px;font-weight:bold">SG</span>',
        "G1":       '<span style="background:#7755cc;color:#fff;padding:1px 5px;border-radius:3px;font-size:11px;font-weight:bold">G1</span>',
        "G2":       '<span style="background:#1a7f3c;color:#fff;padding:1px 5px;border-radius:3px;font-size:11px;font-weight:bold">G2</span>',
        "G3":       '<span style="background:#3366aa;color:#fff;padding:1px 5px;border-radius:3px;font-size:11px;font-weight:bold">G3</span>',
        "レディース": '<span style="background:#e00020;color:#fff;padding:1px 5px;border-radius:3px;font-size:11px;font-weight:bold">♥ Ladies</span>',
    }
    grade_badge = _grade_badge_map.get(tournament_grade, "")
    tg_mods     = get_tournament_grade_mods(tournament_grade)

    sub_parts = [f"〔{_he(race_name)}〕" if race_name else "",
                 grade_badge if grade_badge else "",
                 f"[{cat_jp}]" if cat_jp else ""]
    sub_label = " ".join(p for p in sub_parts if p)

    # ── セクション見出し ─────────────────────────────────────────
    time_badge = (f'<span class="race-time">🕐{_he(start_time)}</span>' if start_time else "")
    print(f'<div class="race-block">')
    print(f'<h2 id="r{race_no}">R{race_no}{time_badge}'
          + (f'<span class="race-label">{sub_label}</span>' if sub_label else '')
          + f'<a class="back" href="#top">↑TOP</a></h2>')

    # ── レース情報 ───────────────────────────────────────────────
    print('<div class="race-info">')
    stime_str = f' &nbsp; 🕐発走 <b>{_he(start_time)}</b>' if start_time else ""
    print(f'<p>🚤 {date[:4]}/{date[4:6]}/{date[6:]} &nbsp; '
          f'{_he(vname)} &nbsp; {race_no}R &nbsp; [{season_jp}・{period_jp}]{stime_str}</p>')
    if venue_note:
        print(f'<p>📍 会場特性: {_he(venue_note)}</p>')
    # グレード補正情報
    if tournament_grade and tournament_grade != "一般":
        tg_note = tg_mods.get("note", "")
        c1_pct  = (_TOURNAMENT_GRADE_DATA.get("grades", {})
                   .get(tournament_grade, {})
                   .get("course1_win_pct") or
                   _TOURNAMENT_GRADE_DATA.get("ladies_tournaments", {})
                   .get(tournament_grade, {})
                   .get("course1_win_pct", ""))
        c1_str  = f" / 1コース平均勝率: {c1_pct}%" if c1_pct else ""
        print(f'<p>🏅 大会グレード: <b>{_he(tournament_grade)}</b>{c1_str}'
              + (f' — {_he(tg_note[:50])}…' if len(tg_note) > 50 else f' — {_he(tg_note)}' if tg_note else "")
              + '</p>')
    if tide_source and tide_label:
        pct_str = f" (潮位{tide_pct}%)" if tide_pct is not None else ""
        print(f'<p>🌊 潮汐[{tide_source}]: {_he(tide_label)}{pct_str} &nbsp; {_he(next_note)}</p>')
        if tide_note:
            print(f'<p>&nbsp;&nbsp;&nbsp;└ {_he(tide_note)}</p>')
    elif tide_note:
        print(f'<p>🌊 潮汐状況: {_he(tide_note)}</p>')
    if weather:
        w_tide = weather.get("潮汐", "")
        w_str  = (f'<p>🌤 気象: {_he(str(weather.get("天候","-")))} &nbsp;'
                  f' 風向:{_he(str(weather.get("風向","-")))} &nbsp;'
                  f' 風速:{_he(str(weather.get("風速","-")))}m')
        if w_tide and not tide_source:
            w_str += f' &nbsp; 潮汐:{_he(w_tide)}'
        print(w_str + '</p>')
        wind_summary = get_wind_summary(weather, venue)
        if wind_summary:
            print(f'<p>💨 {_he(wind_summary)}</p>')
    if not exhibition:
        print('<p>⚠️ 展示データなし（発走前に自動取得予定）</p>')
    print('</div>')

    _print_raw_metrics_section(scored)
    _print_comment_section(scored)
    _print_exhibition_section(scored, exhibition)

    # ── 枠別着順実績 ────────────────────────────────────────────
    print('<div class="sec">📊 枠別着順実績（当地・全国）</div>')
    print('<div class="tbl-wrap"><table class="sticky-name-table">'
          '<tr><th>枠・名前</th><th>参照</th>'
          '<th>1着%</th><th>2着%</th><th>3着%</th><th>3連内%</th>'
          '<th>全国1着%</th><th>R数</th></tr>')
    for r in scored:
        ps        = r["player_stats"]
        w         = str(r["waku"])
        local_ws  = ps.get("hist_local_waku_stats",{}).get(w)
        global_ws = ps.get("hist_global_waku_stats",{}).get(w)
        has_local  = local_ws  and local_ws.get("races",0)  >= 3
        has_global = global_ws and global_ws.get("races",0) >= 3
        if has_local:    src, ws = "当地", local_ws
        elif has_global: src, ws = "全国", global_ws
        else:            src, ws = "---",  {}
        races = ws.get("races", 0)
        def _fmt(v): return f"{v:.1f}" if isinstance(v, float) else str(v)
        p1s   = _fmt(ws.get("1st_pct",  "-"))
        p2s   = _fmt(ws.get("2nd_pct",  "-"))
        p3s   = _fmt(ws.get("3rd_pct",  "-"))
        top3s = _fmt(ws.get("top3_pct", "-"))
        g1    = f"{global_ws['1st_pct']:.1f}" if has_global else "---"
        p1v = ws.get("1st_pct", 0.0) if isinstance(ws.get("1st_pct", 0.0), (int, float)) else 0.0
        p2v = ws.get("2nd_pct", 0.0) if isinstance(ws.get("2nd_pct", 0.0), (int, float)) else 0.0
        p3v = ws.get("3rd_pct", 0.0) if isinstance(ws.get("3rd_pct", 0.0), (int, float)) else 0.0
        top3v = ws.get("top3_pct", 0.0) if isinstance(ws.get("top3_pct", 0.0), (int, float)) else 0.0
        print(f'<tr>'
              f'<td>{_waku_label(r["waku"], r["name"])}</td>'
              f'<td>{src}</td>'
              f'<td><div class="pct-cell"><span>{p1s}</span>{_mini_meter(p1v, 100.0, "linear-gradient(90deg,#2f80ed,#64b5ff)")}</div></td>'
              f'<td><div class="pct-cell"><span>{p2s}</span>{_mini_meter(p2v, 100.0, "linear-gradient(90deg,#5c6bc0,#9fa8da)")}</div></td>'
              f'<td><div class="pct-cell"><span>{p3s}</span>{_mini_meter(p3v, 100.0, "linear-gradient(90deg,#8e7cc3,#c1b2ea)")}</div></td>'
              f'<td><div class="pct-cell"><span>{top3s}</span>{_mini_meter(top3v, 100.0, "linear-gradient(90deg,#2ca58d,#7bd8c8)")}</div></td>'
              f'<td>{g1}</td><td>{races}R</td>'
              f'</tr>')
    print('</table></div>')

    _print_score_section(scored)
    _print_bet_section(scored, weather, odds_data, combo_stats, exhibition_data=exhibition,
                       date_str=date, race_no=race_no, race_name=race_name, jcd=jcd)

    print('</div>')  # race-block


if __name__ == "__main__":
    import argparse, sys, io

    parser = argparse.ArgumentParser(description="ボートレース予想エンジン v4.2")
    parser.add_argument("--jcd",    default="22",  help="会場コード (デフォルト: 22=福岡)")
    parser.add_argument("--date",   default=datetime.date.today().strftime("%Y%m%d"),
                        help="開催日 YYYYMMDD (デフォルト: 今日)")
    parser.add_argument("--race",   type=int, default=0,
                        help="レース番号 1〜12 (省略時: 全レース)")
    parser.add_argument("--output", default="auto",
                        help="出力先ファイルパス (auto=自動, none=ターミナルのみ)")
    parser.add_argument("--no-tide", action="store_true",
                        help="気象庁潮汐データを使わない（weatherのみ使用）")
    parser.add_argument("--wp-publish", action="store_true",
                        help="予測後に WordPress 独自受信口へ投稿を同期する")
    parser.add_argument("--wp-sync-url", default="",
                        help="WordPress 受信口URL。未指定時は WP_SYNC_URL を使用")
    parser.add_argument("--wp-sync-token", default="",
                        help="WordPress 共有トークン。未指定時は WP_SYNC_TOKEN を使用")
    parser.add_argument("--wp-timeout", type=float, default=10.0,
                        help="WordPress 投稿時のHTTPタイムアウト秒数")
    args = parser.parse_args()

    races = [args.race] if args.race else list(range(1, 13))

    # 潮汐データを一度だけ読み込む（全レース共通）
    tide_data = None if args.no_tide else load_tide(args.jcd, args.date)
    if tide_data:
        print(f"[INFO] 潮汐データ: {args.jcd} / {args.date} (気象庁 観測局:{tide_data.get('jma_station','')})")
    else:
        # 潮汐対象会場かどうかを fetch_tide から確認（importできない場合は無視）
        try:
            import sys as _sys
            import importlib
            _ft = importlib.import_module("fetch_tide")
            if _ft.VENUE_TO_JMA_STN.get(args.jcd):
                print(f"[WARN] 潮汐データ未取得。先に実行してください: python3 scripts/fetch_tide.py --jcd {args.jcd}")
        except Exception:
            pass

    # 出力先の決定（会場名を動的に取得）
    venue_name_safe = VENUE_NAMES.get(args.jcd, f"venue{args.jcd}")
    if args.output.lower() == "none":
        out_path = None
    elif args.output.lower() == "auto":
        out_dir = BASE_DIR / "output"
        out_dir.mkdir(exist_ok=True)
        venue_dir = out_dir / venue_name_safe
        venue_dir.mkdir(parents=True, exist_ok=True)
        out_path = venue_dir / f"{args.date}.html"
    else:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

    # tournament_guide.md を output/data/ に生成（初回 or 更新時）
    _generate_tournament_guide_md(BASE_DIR / "output" / "data")

    # ── 第1パス: 全レースを quiet で予測してデータ収集 ────────────
    # 発走時刻を一括取得（キャッシュあれば即時）
    try:
        from scraper import scrape_start_times as _get_stimes
        start_times = _get_stimes(args.jcd, args.date)
    except Exception:
        start_times = {}

    # 会場出目統計を一括ロード（全レース共通）
    combo_stats = load_combo_stats(args.jcd) if _COMBO_STATS_AVAILABLE else None

    all_race_data = []
    for r in races:
        scored, ctx = predict(jcd=args.jcd, date=args.date, race_no=r,
                              tide_data=tide_data, save_log=True,
                              verbose=False, _return_context=True)
        if scored:
            bets       = _suggest_3rentan(scored, ctx.get("weather"), combo_stats=combo_stats,
                                          exhibition_data=ctx.get("exhibition"),
                                          date_str=args.date, race_no=r,
                                          race_name=ctx.get("race_name",""),
                                          jcd=args.jcd)
            conf_pct, rough, dominant = _calc_confidence(scored)
            all_race_data.append({
                "race_no":   r,
                "scored":    scored,
                "ctx":       ctx,
                "bets":      bets,
                "conf_pct":  conf_pct,
                "rough":     rough,
                "dominant":  dominant,
                "start_time": start_times.get(r, ""),
            })

    # ── バッファリングして画面＋ファイル両方に出力 ─────────────────
    if out_path:
        buf = io.StringIO()
        old_stdout = sys.stdout
        class Tee:
            def write(self, s):
                old_stdout.write(s)
                buf.write(s)
            def flush(self):
                old_stdout.flush()
        sys.stdout = Tee()

    # ── 早見表（全レースサマリー） ──────────────────────────────
    vname_header = _display_venue_name(VENUE_NAMES.get(args.jcd, args.jcd))
    d = args.date
    date_str = f"{d[:4]}/{d[4:6]}/{d[6:]}"
    cat_short = {"finalist": "🏆決勝", "general": "一般", "qualifier": "予選"}

    # HTMLヘッダー＋CSSスタイル
    title_str = f"🚤 {vname_header} — {date_str}"
    print('<!DOCTYPE html>')
    print('<html lang="ja">')
    print('<head>')
    print('<meta charset="UTF-8">')
    print('<meta name="viewport" content="width=device-width, initial-scale=1">')
    print(f'<title>{title_str}</title>')
    print('''<style>
body { font-family: -apple-system, sans-serif; font-size: 13px; padding: 8px 10px; background: #fff; color: #111; }
h1 { font-size: 16px; margin: 0 0 10px; }
h2 { font-size: 13px; margin: 14px 0 4px; padding: 5px 8px;
     background: #eef3ff; border-left: 4px solid #3366cc;
     display: flex; align-items: center; gap: 6px; }
.race-label { font-size: 11px; font-weight: normal; color: #555; flex: 1; }
.race-time  { font-size: 12px; font-weight: bold; color: #1a5c8a; margin-left: 6px; }
.back { font-size: 11px; color: #888; margin-left: auto; white-space: nowrap; }
.race-block { margin-bottom: 16px; border-bottom: 2px solid #e8edf8; padding-bottom: 8px; }
/* ── 共通テーブル ── */
.tbl-wrap { overflow-x: auto; margin-bottom: 8px; -webkit-overflow-scrolling: touch; }
table { border-collapse: collapse; min-width: 100%; font-size: 12px; }
th { background: #2c4a8a; color: #fff; padding: 5px 8px; white-space: nowrap; font-weight: bold; }
td { border: 1px solid #ddd; padding: 4px 8px; white-space: nowrap; }
tr:nth-child(even) td { background: #f5f7fb; }
tr:hover td { background: #dce8ff !important; }
/* ── 早見表専用 ── */
.rough-row td { background: #fff4e0 !important; }
.rough-row:hover td { background: #ffe0b0 !important; }
.r-link { font-weight: bold; color: #0055cc; text-decoration: none; }
.r-link:hover { text-decoration: underline; }
.stime  { font-size: 11.5px; color: #1a5c8a; font-weight: bold; }
/* ── 買い目 ── */
.bet { font-family: monospace; font-size: 12.5px; letter-spacing: 0.5px; }
.bet1 { font-weight: bold; color: #111; }
.bet2 { color: #444; }
.bet-ana { color: #888; }
.bet-sub { color: #5a6b88; }
.bet-stack { display: grid; gap: 3px; }
/* v5.16: その他セクションの種別バッジ */
.subtype-badge { display: inline-block; padding: 1px 6px; border-radius: 3px;
                 font-size: 11px; font-weight: bold; color: #fff; min-width: 24px; text-align: center; }
.subtype-tai  { background: #5a6fc2; }
.subtype-oshi { background: #6f8a8a; }
.subtype-ana  { background: #c65050; }
/* ── 信頼度・荒れ ── */
.conf-high { color: #1a7f1a; font-weight: bold; }
.conf-mid  { color: #8a6800; }
.conf-low  { color: #c04000; font-weight: bold; }
.note-rough { color: #c04000; font-weight: bold; }
a { color: #0055cc; text-decoration: none; }
a:hover { text-decoration: underline; }
/* ── レース情報 ── */
.race-info { background: #f5f7fb; border-left: 3px solid #3366cc;
             padding: 5px 10px; margin: 3px 0 8px; font-size: 12px; }
.race-info p { margin: 2px 0; }
/* ── セクション見出し ── */
.sec { font-size: 12px; font-weight: bold; color: #2c4a8a;
       margin: 8px 0 2px; border-bottom: 1px solid #c8d4f0; padding-bottom: 1px; }
/* ── 買い目ボックス ── */
.bet-box { background: #fffbe6; border: 1px solid #d4b800;
           border-radius: 3px; padding: 6px 10px; margin: 4px 0 8px; }
.bet-box .conf-line { font-size: 12px; font-weight: bold; margin-bottom: 4px; }
.bet-box .bet-title { font-size: 11.5px; color: #555; margin-bottom: 3px; }
.bet-tbl { min-width: unset !important; }
.bet-tbl th { background: #9a7800; padding: 3px 7px; }
.bet-tbl td { border-color: #e0c840; background: #fffef5 !important; padding: 3px 7px; }
.budget-box { background: #f8fbff; border: 1px solid #cfdcf3; border-radius: 4px; padding: 6px 10px; margin: 4px 0 8px; }
.budget-head { font-size: 12px; font-weight: bold; margin-bottom: 4px; }
.budget-note { color: #555; font-weight: normal; margin-left: 8px; }
.budget-tbl th { background: #5070a8; padding: 3px 7px; }
.budget-tbl td { background: #fbfdff !important; border-color: #d9e3f4; padding: 3px 7px; }
.plan-ok { color: #1a7f1a; }
.plan-ng { color: #c04000; }
.ev-high { color: #1a7f1a; font-weight: bold; }
.ev-low  { color: #c04000; }
/* ── スコアテーブル ── */
.rank1 td { background: #fffbe0 !important; }
.grade-a1 { color: #c62828; font-weight: bold; }
.grade-a2 { color: #c62828; font-weight: bold; }
.grade-b  { color: #1565c0; font-weight: bold; }
/* ── コメント ── */
.cmt-good { color: #1a7f1a; font-weight: bold; }
.cmt-bad  { color: #c04000; font-weight: bold; }
/* ── 展示データ ── */
.ex-best  { color: #1a7f1a; font-weight: bold; }
.ex-good  { color: #4a7a1a; }
.ex-slow  { color: #c04000; }
.tilt-neg { color: #0055cc; font-weight: bold; }
.co-row td { background: #f0f4ff !important; font-style: italic; text-align: center; }
.no-data  { color: #888; font-style: italic; font-size: 12px; margin: 2px 0 6px; }
.note { color: #666; font-size: 11.5px; margin: 3px 0 8px; }
.flow-cell { display: grid; gap: 3px; white-space: normal; min-width: 185px; }
.flow-row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.flow-label { color: #666; font-size: 10.5px; flex: 0 0 auto; }
.flow-value { font-weight: 600; text-align: right; }
.tone-data { color: #355c7d; }
.tone-picked { color: #8a6800; }
.tone-score { color: #0b6e4f; }
.single-metric { display: grid; gap: 4px; min-width: 92px; }
.pct-cell { display: grid; gap: 4px; min-width: 74px; }
.meter { display: inline-block; width: 72px; height: 7px; background: #e5ebf5; border-radius: 999px; overflow: hidden; vertical-align: middle; }
.meter-fill { display: block; height: 100%; border-radius: 999px; }
.waku-name-cell { display:flex; align-items:center; gap:6px; }
.waku-chip { display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border:1px solid #ccc; border-radius:999px; font-size:11px; font-weight:700; line-height:1; flex:0 0 18px; }
.waku-name { font-weight:600; }
.sticky-name-table th:nth-child(1),
.sticky-name-table td:nth-child(1) {
  position: sticky;
  left: 0;
  z-index: 3;
  min-width: 88px;
}
.sticky-score-table th:nth-child(1),
.sticky-score-table td:nth-child(1) {
  position: sticky;
  left: 0;
  z-index: 4;
}
.sticky-score-table th:nth-child(2),
.sticky-score-table td:nth-child(2) {
  position: sticky;
  left: 32px;
  z-index: 4;
  min-width: 92px;
}
.sticky-name-table td:nth-child(1),
.sticky-score-table td:nth-child(1),
.sticky-score-table td:nth-child(2) {
  background: #ffffff;
  box-shadow: 1px 0 0 #d9dfe8;
}
.sticky-name-table tr:nth-child(even) td:nth-child(1),
.sticky-score-table tr:nth-child(even) td:nth-child(1),
.sticky-score-table tr:nth-child(even) td:nth-child(2) {
  background: #f5f7fb;
}
.sticky-name-table tr:hover td:nth-child(1),
.sticky-score-table tr:hover td:nth-child(1),
.sticky-score-table tr:hover td:nth-child(2) {
  background: #dce8ff !important;
}
.sticky-name-table th:nth-child(1),
.sticky-score-table th:nth-child(1),
.sticky-score-table th:nth-child(2) {
  background: #2c4a8a;
  z-index: 5;
}
</style>''')
    print('</head>')
    print('<body>')
    print('<a id="top"></a>')

    # タイトル + HTMLテーブル（アンカーリンク付き早見表）
    print(f'<h1>{title_str}  全{len(all_race_data)}R</h1>')
    print('<div class="tbl-wrap"><table>')
    print('<tr><th>R</th><th>発走</th><th>本線</th><th>対抗</th><th>単穴</th><th>信頼</th><th>種別</th><th>備考</th></tr>')
    for rd in all_race_data:
        bets  = rd["bets"]
        grouped_bets = _group_bets_by_label(bets)
        conf_pct = rd["conf_pct"]
        rough = rd["rough"]
        b1_list = [combo for combo, _ in grouped_bets.get("本命①", [])] or ["---"]
        b2_list = [combo for combo, _ in grouped_bets.get("本命②", [])] or ["---"]
        b3_list = [combo for combo, _ in grouped_bets.get("穴", [])] or ["---"]
        b1 = '<div class="bet-stack">' + ''.join(f'<span class="bet bet1">{_he(combo)}</span>' for combo in b1_list) + '</div>'
        b2 = '<div class="bet-stack">' + ''.join(f'<span class="bet bet2">{_he(combo)}</span>' for combo in b2_list) + '</div>'
        b3 = '<div class="bet-stack">' + ''.join(f'<span class="bet bet-ana">{_he(combo)}</span>' for combo in b3_list) + '</div>'
        note = "⚡荒れ" if rough else ""
        cat  = cat_short.get(rd["ctx"].get("race_category",""), "予選")
        rn   = rd["race_no"]
        st   = rd.get("start_time", "")
        conf_cls = _confidence_class(conf_pct)
        row_cls = ' class="rough-row"' if rough else ''
        note_td = f'<span class="note-rough">{note}</span>' if note else ""
        st_td   = f'<span class="stime">{st}</span>' if st else "---"
        # HTMLアンカーリンク: <a href="#r10">10R</a> → 各レースの id="r10" へジャンプ
        print(f'<tr{row_cls}>'
              f'<td><a class="r-link" href="#r{rn}">{rn}R</a></td>'
              f'<td>{st_td}</td>'
              f'<td>{b1}</td>'
              f'<td>{b2}</td>'
              f'<td>{b3}</td>'
              f'<td class="{conf_cls}">{_format_confidence(conf_pct)}</td>'
              f'<td>{cat}</td>'
              f'<td>{note_td}</td>'
              f'</tr>')
    print('</table></div>')

    # ── 第2パス: 各レースの詳細を出力 ──────────────────────────
    for rd in all_race_data:
        ctx = rd["ctx"]
        _print_result(args.jcd, args.date, rd["race_no"],
                      rd["scored"], ctx.get("venue"), ctx.get("exhibition"),
                      ctx.get("weather"), tide_data=tide_data,
                      odds_data=ctx.get("odds_data"),
                      race_name=ctx.get("race_name",""),
                      race_category=ctx.get("race_category",""),
                      start_time=rd.get("start_time",""),
                      combo_stats=combo_stats,
                      tournament_grade=ctx.get("tournament_grade","一般"))

    print('</body></html>')

    if out_path:
        sys.stdout = old_stdout
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(buf.getvalue())
        if args.output.lower() == "auto":
            _write_output_indexes(BASE_DIR / "output")
        print(f"\n💾 出力ファイル: {out_path}")

    if args.wp_publish:
        try:
            # v5.16 fix: write_payload_file もセットで呼び、ローカル payload を常に最新に保つ
            from publish_wordpress import build_request_payload, publish_payload, write_payload_file
            wp_payload = build_request_payload(args.jcd, args.date)
            payload_path = write_payload_file(args.jcd, args.date, wp_payload)
            print(f"📦 payload 保存: {payload_path.name}")

            wp_sync_url = args.wp_sync_url or os.getenv("WP_SYNC_URL", "")
            wp_sync_token = args.wp_sync_token or os.getenv("WP_SYNC_TOKEN", "")
            if not wp_sync_url or not wp_sync_token:
                print("[WARN] WordPress 送信をスキップ: --wp-sync-url / --wp-sync-token または環境変数が未設定です（ローカル payload は保存済み）")
            else:
                wp_result = publish_payload(wp_payload, wp_sync_url, wp_sync_token, args.wp_timeout)
                print(f"🌐 WordPress 同期: {wp_result.get('action', 'unknown')} / {wp_result.get('link', '-')}")
        except Exception as e:
            print(f"[WARN] WordPress 同期失敗: {e}")
