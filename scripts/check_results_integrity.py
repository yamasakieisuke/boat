#!/usr/bin/env python3
"""
取り込み済み結果データの整合性チェック
=========================================
`data/results_csv/{YYYYMMDD}.csv` に対して「壊れていたら必ず破れる不変条件」を
検査する。取り込みパイプライン（fetch_results.py の LZH パーサ / 公式HTML）が
静かに壊れたことを、その日のうちに検知するのが目的。

背景（2026-08-16）:
  LZH パーサの flush() タイミングの誤りで、各会場ブロックの最終レース（R12等）が
  1つ隣の会場の成績として記録されていた。505日中451日・全レースの約8%。
  results_csv は verify・回収率・build_stats すべての土台なので、ここが壊れると
  下流が全部静かに壊れる。にもかかわらず1年半誰も気づかなかった。
  検出自体は「同一日に複数会場で走っている選手を数える」だけで即座にできた
  （修復前16,714人 → 修復後0人）。二度と同じ見落としをしないための常設チェック。

判定レベル:
  ERROR … 物理的にありえない / 構造が壊れている。終了コードを非ゼロにする
  WARN  … 異常の可能性が高いが、正当な理由（中止・順延・不成立）もありうる
  INFO  … 既知の限界・正常な例外（同着など）。終了コードに影響しない

既知の限界（誤検知させないための扱い）:
  * fetch_results.py:65 の RE_RANK が着順を2桁数字で要求するため、F・失格・転覆の艇は
    レコードごと落ちる。6艇そろわないレースが全体の約6.5%ある（ロードマップ D-9）。
    → 「6艇未満」は INFO 止まりにしてある。ERROR にすると毎日鳴りっぱなしになる。
  * 同着（デッドヒート）は実在する。rank の重複それ自体は異常ではないので、
    「順位の多重集合が競技順位として妥当か」まで見て初めて ERROR にする。

使い方:
  # 全期間（data/results_csv/ にある日付CSV全部）
  python3 scripts/check_results_integrity.py

  # 1日だけ
  python3 scripts/check_results_integrity.py --date 20260817

  # 期間指定
  python3 scripts/check_results_integrity.py --from 20250315 --to 20250331

  # CI 用（ERROR のみ表示、違反があれば exit 1）
  python3 scripts/check_results_integrity.py --quiet

  # WARN も失敗扱いにする
  python3 scripts/check_results_integrity.py --strict

終了コード:
  0 … ERROR なし（--strict 時は WARN もなし）
  1 … 違反あり
  2 … 対象ファイルが1件も見つからない等の実行時エラー
"""

from __future__ import annotations

import argparse
import csv
import datetime
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_DIR = BASE_DIR / "data" / "results_csv"

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"
LEVEL_ORDER = {ERROR: 0, WARN: 1, INFO: 2}

# fetch_results_official.JCD_TO_VENUE と同じ24会場。
# あちらは requests / bs4 を import するため、CI で依存なしに動かせるよう値だけ持つ。
VENUE_NAMES = frozenset({
    "桐生", "戸田", "江戸川", "平和島", "多摩川",
    "浜名湖", "蒲郡", "常滑", "津", "三国",
    "びわこ", "住之江", "尼崎", "鳴門", "丸亀",
    "児島", "宮島", "徳山", "下関", "若松",
    "芦屋", "福岡", "唐津", "大村",
})

EXPECTED_RACES = 12       # 通常の1会場1日あたりレース数
MAX_BOATS = 6             # 1レースの艇数
MAX_RACES_PER_DAY = 2     # 1選手が1会場1日で走る上限（実測: 最大2）
MIN_PAYOUT = 100          # 払戻金の下限（100円未満はありえない）

DATE_RE = re.compile(r"^\d{8}$")
DAY_CSV_RE = re.compile(r"^\d{8}\.csv$")
COMBO3_RE = re.compile(r"^[1-6]-[1-6]-[1-6]$")
COMBO2_RE = re.compile(r"^[1-6]-[1-6]$")
REG_NO_RE = re.compile(r"^\d{4}$")


class Violation:
    """1件の違反。"""

    __slots__ = ("date", "level", "code", "venue", "race_no", "detail")

    def __init__(self, date: str, level: str, code: str, detail: str,
                 venue: str = "", race_no: str = "") -> None:
        self.date = date
        self.level = level
        self.code = code
        self.venue = venue
        self.race_no = race_no
        self.detail = detail

    def where(self) -> str:
        parts = [self.date]
        if self.venue:
            parts.append(self.venue)
        if self.race_no:
            parts.append(f"{self.race_no}R")
        return " ".join(parts)

    def __str__(self) -> str:
        return f"[{self.level}] {self.code:24s} {self.where():24s} {self.detail}"


class Report:
    """検査結果のまとめ。"""

    def __init__(self) -> None:
        self.violations: List[Violation] = []
        self.days = 0
        self.rows = 0
        self.races = 0
        self.missing_files: List[str] = []

    def add(self, v: Violation) -> None:
        self.violations.append(v)

    def extend(self, vs: Iterable[Violation]) -> None:
        self.violations.extend(vs)

    def merge(self, other: "Report") -> None:
        self.violations.extend(other.violations)
        self.days += other.days
        self.rows += other.rows
        self.races += other.races
        self.missing_files.extend(other.missing_files)

    def by_level(self, level: str) -> List[Violation]:
        return [v for v in self.violations if v.level == level]

    @property
    def error_count(self) -> int:
        return len(self.by_level(ERROR))

    @property
    def warn_count(self) -> int:
        return len(self.by_level(WARN))

    @property
    def info_count(self) -> int:
        return len(self.by_level(INFO))

    def failed(self, strict: bool = False) -> bool:
        return self.error_count > 0 or (strict and self.warn_count > 0)


# ── 補助 ───────────────────────────────────────────────

def _int_or_none(s: Optional[str]) -> Optional[int]:
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


def _is_valid_competition_ranking(ranks: Sequence[int]) -> bool:
    """順位の多重集合が「競技順位（同着を含む標準順位）」として妥当か。

    妥当例: 1,2,3,4,5,6 / 1,2,3,3,5,6（3着同着）/ 1,2,3,4,5,5 / 1,2,3,4,5（艇落ち）
    不正例: 1,1,2,2,3,3（別レースの混入。1が2つなら次は3でなければならない）

    ルール: 順位 k は「k より上位の行数 + 1」に一致しなければならない。
    """
    counts = Counter(ranks)
    for k, _n in counts.items():
        better = sum(m for kk, m in counts.items() if kk < k)
        if k != better + 1:
            return False
    return True


def load_day_rows(date_str: str, csv_dir: Optional[Path] = None) -> Optional[List[dict]]:
    """{date}.csv を読む。存在しなければ None。"""
    path = (csv_dir or CSV_DIR) / f"{date_str}.csv"
    if not path.exists():
        return None
    # 書き出しは utf-8-sig（BOM 付き）。BOM を剥がさないと先頭列名が壊れる。
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ── 個別チェック ────────────────────────────────────────

def _check_rows(date_str: str, rows: List[dict], report: Report) -> None:
    """行単位の値域チェック。壊れた行は以降のチェックから除外はしない
    （除外すると壊れ方によっては別のチェックがすり抜けるため）。"""
    for r in rows:
        venue = (r.get("venue_name") or "").strip()
        race_no = (r.get("race_no") or "").strip()

        d = (r.get("date") or "").strip()
        if d != date_str:
            report.add(Violation(date_str, ERROR, "date_mismatch",
                                 f"date列={d!r} がファイル名と不一致", venue, race_no))
        if venue not in VENUE_NAMES:
            report.add(Violation(date_str, ERROR, "unknown_venue",
                                 f"未知の会場名 {venue!r}", venue, race_no))

        rn = _int_or_none(race_no)
        if rn is None or not (1 <= rn <= EXPECTED_RACES):
            report.add(Violation(date_str, ERROR, "race_no_out_of_range",
                                 f"race_no={race_no!r}", venue, race_no))

        waku = _int_or_none(r.get("waku"))
        if waku is None or not (1 <= waku <= MAX_BOATS):
            report.add(Violation(date_str, ERROR, "waku_out_of_range",
                                 f"waku={r.get('waku')!r}", venue, race_no))

        # rank=0 は LZH の "00"（レース不成立）。値としては許すが下で別途 WARN。
        rank = _int_or_none(r.get("rank"))
        if rank is None or not (0 <= rank <= MAX_BOATS):
            report.add(Violation(date_str, ERROR, "rank_out_of_range",
                                 f"rank={r.get('rank')!r}", venue, race_no))

        course = (r.get("course_enter") or "").strip()
        if course:
            ci = _int_or_none(course)
            if ci is None or not (1 <= ci <= MAX_BOATS):
                report.add(Violation(date_str, ERROR, "course_out_of_range",
                                     f"course_enter={course!r}", venue, race_no))

        reg = (r.get("reg_no") or "").strip()
        if not REG_NO_RE.match(reg):
            report.add(Violation(date_str, ERROR, "reg_no_malformed",
                                 f"reg_no={reg!r}", venue, race_no))

        if not (r.get("name") or "").strip():
            report.add(Violation(date_str, WARN, "name_empty",
                                 f"選手名が空 (reg_no={reg})", venue, race_no))


def _check_cross_venue_racers(date_str: str, rows: List[dict], report: Report) -> None:
    """★最重要★ 同一日に複数会場で走っている選手がいないか。

    選手は1日に1会場でしか走れない。会場割り当てがズレるとここが必ず破れる。
    2026-08-16 の会場ズレ事故は、この1本で16,714人として即座に出た。
    """
    venues_of: Dict[str, set] = defaultdict(set)
    names: Dict[str, str] = {}
    for r in rows:
        reg = (r.get("reg_no") or "").strip()
        venue = (r.get("venue_name") or "").strip()
        if not reg or not venue:
            continue
        venues_of[reg].add(venue)
        names.setdefault(reg, (r.get("name") or "").strip())

    for reg, vs in sorted(venues_of.items()):
        if len(vs) > 1:
            report.add(Violation(
                date_str, ERROR, "racer_in_multiple_venues",
                f"選手 {reg} {names.get(reg, '')} が {len(vs)}会場に出走: {'/'.join(sorted(vs))}"))


def _check_racer_race_count(date_str: str, races: Dict[Tuple[str, str], List[dict]],
                            report: Report) -> None:
    """1選手が同一会場・同一日に走るレース数の上限。

    実測では最大2（全507日・286,019件）。3以上はレースブロックの重複取り込みを疑う。
    """
    seen: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for (venue, race_no), rs in races.items():
        for r in rs:
            reg = (r.get("reg_no") or "").strip()
            if reg:
                seen[(venue, reg)].append(race_no)
    for (venue, reg), race_nos in sorted(seen.items()):
        if len(race_nos) > MAX_RACES_PER_DAY:
            order = sorted(race_nos, key=lambda x: _int_or_none(x) or 99)
            report.add(Violation(
                date_str, ERROR, "racer_too_many_races",
                f"選手 {reg} が同一会場で {len(race_nos)}走: R{',R'.join(order)}", venue))


def _check_race_block(date_str: str, venue: str, race_no: str, rs: List[dict],
                      report: Report) -> None:
    """1レース（会場×レース番号）単位の内部整合性。"""
    n = len(rs)

    # ① 7行以上 = 別レースが重複して積まれている
    #    実例: 20260217 びわこ1R に三国・常滑のレースが混在していた
    if n > MAX_BOATS:
        report.add(Violation(date_str, ERROR, "race_row_overflow",
                             f"{n}行（上限{MAX_BOATS}）。別レースの混入を疑う", venue, race_no))
    elif n < MAX_BOATS:
        # 既知の限界（D-9）。F/失格/転覆の艇が行ごと落ちるため 6.5% で発生する。
        # ERROR にすると毎日鳴るので INFO 止まり。
        report.add(Violation(date_str, INFO, "race_incomplete",
                             f"{n}艇のみ（F/失格/転覆の行落ち。既知: RE_RANK の制約）",
                             venue, race_no))

    # ② 枠番の重複
    wakus = [(r.get("waku") or "").strip() for r in rs]
    dup_w = [w for w, c in Counter(wakus).items() if c > 1]
    if dup_w:
        report.add(Violation(date_str, ERROR, "duplicate_waku",
                             f"枠番が重複: {sorted(dup_w)} / 全枠={wakus}", venue, race_no))

    # ③ 同一選手が同一レースに2回
    regs = [(r.get("reg_no") or "").strip() for r in rs]
    dup_r = [x for x, c in Counter(regs).items() if c > 1 and x]
    if dup_r:
        report.add(Violation(date_str, ERROR, "duplicate_reg_no",
                             f"同一選手が複数行: {sorted(dup_r)}", venue, race_no))

    # ④ 進入コースの重複
    courses = [(r.get("course_enter") or "").strip() for r in rs]
    courses = [c for c in courses if c]
    dup_c = [x for x, c in Counter(courses).items() if c > 1]
    if dup_c:
        report.add(Violation(date_str, ERROR, "duplicate_course_enter",
                             f"進入コースが重複: {sorted(dup_c)} / 全進入={courses}",
                             venue, race_no))

    # ⑤ 着順の重複 → 同着かどうかまで判定する
    ranks = [_int_or_none(r.get("rank")) for r in rs]
    ranked = [k for k in ranks if k is not None and k > 0]
    void_rows = [r for r, k in zip(rs, ranks) if k == 0]
    rank_counts = Counter(ranked)
    dup_k = sorted(k for k, c in rank_counts.items() if c > 1)
    if dup_k:
        if not _is_valid_competition_ranking(ranked):
            report.add(Violation(
                date_str, ERROR, "duplicate_rank",
                f"着順が重複し競技順位として不正: {sorted(ranked)}。別レースの混入を疑う",
                venue, race_no))
        else:
            # 同着は実在する（全507日で48〜60件）。同着艇はレースタイムも一致するはず。
            bad_time = False
            for k in dup_k:
                times = {(r.get("race_time") or "").strip()
                         for r, kk in zip(rs, ranks) if kk == k}
                times = {t for t in times if t}
                if len(times) > 1:
                    bad_time = True
            if bad_time:
                report.add(Violation(
                    date_str, ERROR, "duplicate_rank",
                    f"同着なのにレースタイムが不一致: 着順={sorted(ranked)}", venue, race_no))
            else:
                report.add(Violation(date_str, INFO, "dead_heat",
                                     f"同着 {dup_k}着（正常）", venue, race_no))
    elif ranked and not _is_valid_competition_ranking(ranked):
        report.add(Violation(date_str, ERROR, "rank_sequence_broken",
                             f"着順が連番でない: {sorted(ranked)}", venue, race_no))

    # ⑥ 払戻列がレース内の全行で一致しているか（行ごとに違う＝マージ事故）
    for fld in ("won3", "won3_pay", "won2", "trio", "pair"):
        vals = {(r.get(fld) or "").strip() for r in rs}
        if len(vals) > 1:
            report.add(Violation(date_str, ERROR, "payout_row_mismatch",
                                 f"{fld} が行ごとに異なる: {sorted(vals)}", venue, race_no))

    head = rs[0]
    won3 = (head.get("won3") or "").strip()
    won2 = (head.get("won2") or "").strip()
    trio = (head.get("trio") or "").strip()
    pair = (head.get("pair") or "").strip()

    # ⑦ won3 が着順から復元した組み合わせと一致するか
    #    同着があると勝ち組み合わせが複数成立するので、同着艇のどれかに当たれば OK とする。
    top: Dict[int, set] = defaultdict(set)
    for r, k in zip(rs, ranks):
        if k in (1, 2, 3):
            top[k].add((r.get("waku") or "").strip())
    if won3:
        if not COMBO3_RE.match(won3):
            report.add(Violation(date_str, WARN, "won3_malformed",
                                 f"won3={won3!r}", venue, race_no))
        elif all(k in top for k in (1, 2, 3)):
            a, b, c = won3.split("-")
            if not (a in top[1] and b in top[2] and c in top[3]):
                recon = "-".join("|".join(sorted(top[k])) for k in (1, 2, 3))
                report.add(Violation(
                    date_str, ERROR, "won3_mismatch",
                    f"won3={won3} だが着順からの復元は {recon}", venue, race_no))

    # ⑧ won2 / trio / pair が won3 と整合するか
    #    不成立などで個別レースの払戻行が無いと、fetch_results.py の pay_db
    #    （レース番号のみをキーに全会場ぶんを先読みする）から他会場の値が残る。
    #    実測 110件/507日。実害のある取り込み欠陥だが既知・低頻度なので WARN。
    if COMBO3_RE.match(won3):
        a, b, c = won3.split("-")
        if won2 and COMBO2_RE.match(won2) and won2 != f"{a}-{b}":
            report.add(Violation(date_str, WARN, "payout_combo_inconsistent",
                                 f"won3={won3} に対し won2={won2}（他会場の払戻混入を疑う）",
                                 venue, race_no))
        if trio and trio != "-".join(sorted([a, b, c])):
            report.add(Violation(date_str, WARN, "payout_combo_inconsistent",
                                 f"won3={won3} に対し trio={trio}（他会場の払戻混入を疑う）",
                                 venue, race_no))
        if pair and pair != "-".join(sorted([a, b])):
            report.add(Violation(date_str, WARN, "payout_combo_inconsistent",
                                 f"won3={won3} に対し pair={pair}（他会場の払戻混入を疑う）",
                                 venue, race_no))

    # ⑨ 払戻金の値域
    for fld in ("won3_pay", "won2_pay", "trio_pay", "pair_pay"):
        val = (head.get(fld) or "").strip()
        if not val:
            continue
        num = _int_or_none(val)
        if num is None or num < MIN_PAYOUT:
            report.add(Violation(date_str, WARN, "payout_value_invalid",
                                 f"{fld}={val!r}", venue, race_no))

    # ⑩ レース不成立（rank=0）なのに払戻が入っている
    if void_rows and (won3 or won2 or trio or pair):
        report.add(Violation(
            date_str, WARN, "void_race_has_payout",
            f"着順00（レース不成立）なのに払戻あり won3={won3} pay={head.get('won3_pay')}"
            "（他会場の払戻混入を疑う）", venue, race_no))


def _check_race_counts(date_str: str, races: Dict[Tuple[str, str], List[dict]],
                       report: Report) -> None:
    """1会場あたりのレース数と番号の連続性。"""
    per_venue: Dict[str, List[int]] = defaultdict(list)
    for (venue, race_no), _rs in races.items():
        rn = _int_or_none(race_no)
        if rn is not None:
            per_venue[venue].append(rn)

    for venue, nos in sorted(per_venue.items()):
        n = len(nos)
        if n > EXPECTED_RACES:
            report.add(Violation(date_str, ERROR, "race_count_over",
                                 f"{n}レース（通常{EXPECTED_RACES}）。会場の取り違えを疑う", venue))
        elif n < EXPECTED_RACES:
            # 中止・順延・打ち切りで正当に減ることがある（実測 65/6,389 会場日）
            report.add(Violation(date_str, WARN, "race_count_short",
                                 f"{n}レースのみ（通常{EXPECTED_RACES}）。"
                                 "中止・順延なら正常、そうでなければ取り込み漏れ", venue))
        expected = set(range(1, max(nos) + 1)) if nos else set()
        missing = sorted(expected - set(nos))
        if missing:
            report.add(Violation(date_str, WARN, "race_no_gap",
                                 f"レース番号が飛んでいる: 欠番 R{',R'.join(map(str, missing))}",
                                 venue))


# ── 日次・期間の検査 ──────────────────────────────────

def check_day(date_str: str, csv_dir: Optional[Path] = None) -> Report:
    """1日ぶんの results_csv を検査して Report を返す。

    morning_verify.py からもこの関数を直接呼ぶ。
    """
    report = Report()
    rows = load_day_rows(date_str, csv_dir)
    if rows is None:
        report.missing_files.append(date_str)
        return report
    return check_rows(date_str, rows, report)


def check_rows(date_str: str, rows: List[dict], report: Optional[Report] = None) -> Report:
    """メモリ上の行リストを検査する（CSV を経由しない呼び出し用）。"""
    report = report if report is not None else Report()
    report.days += 1
    report.rows += len(rows)

    if not rows:
        report.add(Violation(date_str, WARN, "empty_day", "1行もない"))
        return report

    races: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for r in rows:
        races[((r.get("venue_name") or "").strip(),
               (r.get("race_no") or "").strip())].append(r)
    report.races += len(races)

    _check_rows(date_str, rows, report)
    _check_cross_venue_racers(date_str, rows, report)
    _check_racer_race_count(date_str, races, report)
    _check_race_counts(date_str, races, report)
    for (venue, race_no), rs in sorted(
            races.items(), key=lambda kv: (kv[0][0], _int_or_none(kv[0][1]) or 99)):
        _check_race_block(date_str, venue, race_no, rs, report)
    return report


def check_dates(dates: Sequence[str], csv_dir: Optional[Path] = None) -> Report:
    total = Report()
    for d in dates:
        total.merge(check_day(d, csv_dir))
    return total


# ── 対象日の決定 ──────────────────────────────────────

def available_dates(csv_dir: Optional[Path] = None) -> List[str]:
    csv_dir = csv_dir or CSV_DIR
    if not csv_dir.exists():
        return []
    return sorted(p.name[:8] for p in csv_dir.iterdir() if DAY_CSV_RE.match(p.name))


def resolve_dates(args: argparse.Namespace, csv_dir: Path) -> List[str]:
    if args.date:
        return [args.date]
    have = available_dates(csv_dir)
    lo = args.date_from or ""
    hi = args.date_to or "99999999"
    return [d for d in have if lo <= d <= hi]


# ── 出力 ──────────────────────────────────────────────

def format_report(report: Report, quiet: bool = False, limit: int = 20,
                  show_info: bool = True) -> List[str]:
    """人が読む形にする。morning_verify からも使う。"""
    out: List[str] = []
    levels = [ERROR, WARN] if (quiet or not show_info) else [ERROR, WARN, INFO]
    if quiet:
        levels = [ERROR]

    for level in levels:
        vs = report.by_level(level)
        if not vs:
            continue
        by_code: Dict[str, List[Violation]] = defaultdict(list)
        for v in vs:
            by_code[v.code].append(v)
        out.append(f"  {level}: {len(vs)}件")
        for code, items in sorted(by_code.items(), key=lambda kv: -len(kv[1])):
            out.append(f"    - {code}: {len(items)}件")
            for v in items[:limit]:
                out.append(f"        {v.where()}  {v.detail}")
            if len(items) > limit:
                out.append(f"        ... 他 {len(items) - limit}件")

    summary = (f"  対象 {report.days}日 / {report.races:,}レース / {report.rows:,}行"
               f"  →  ERROR {report.error_count}件 / WARN {report.warn_count}件"
               f" / INFO {report.info_count}件")
    out.append(summary)
    if report.missing_files:
        out.append(f"  結果CSVなし: {len(report.missing_files)}日"
                   f"（{', '.join(report.missing_files[:5])}"
                   f"{' ...' if len(report.missing_files) > 5 else ''}）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="results_csv の整合性チェック（会場ズレ・重複・払戻不整合の検出）")
    ap.add_argument("--date", help="対象日 YYYYMMDD（単日）")
    ap.add_argument("--from", dest="date_from", help="開始日 YYYYMMDD")
    ap.add_argument("--to", dest="date_to", help="終了日 YYYYMMDD")
    ap.add_argument("--quiet", action="store_true",
                    help="ERROR のみ表示（CI 向け）")
    ap.add_argument("--no-info", action="store_true",
                    help="INFO を表示しない（WARN までは出す）")
    ap.add_argument("--strict", action="store_true",
                    help="WARN も失敗扱いにする")
    ap.add_argument("--limit", type=int, default=20,
                    help="違反種別ごとの明細表示件数の上限（デフォルト20）")
    ap.add_argument("--dir", default=str(CSV_DIR),
                    help="results_csv ディレクトリ（デフォルト: data/results_csv）")
    args = ap.parse_args()

    for key in ("date", "date_from", "date_to"):
        val = getattr(args, key)
        if val and not DATE_RE.match(val):
            print(f"[ERROR] 日付は YYYYMMDD 形式で指定してください: {val}", file=sys.stderr)
            return 2

    csv_dir = Path(args.dir)
    dates = resolve_dates(args, csv_dir)
    if not dates:
        print(f"[ERROR] 対象の結果CSVが見つかりません: {csv_dir}", file=sys.stderr)
        return 2

    report = check_dates(dates, csv_dir)

    if not args.quiet:
        print(f"\n{'=' * 64}")
        print(f"  results_csv 整合性チェック: {dates[0]} 〜 {dates[-1]}（{len(dates)}日）")
        print(f"{'=' * 64}")
    for line in format_report(report, quiet=args.quiet, limit=args.limit,
                              show_info=not args.no_info):
        print(line)

    if report.failed(strict=args.strict):
        print("  判定: NG（違反あり）")
        return 1
    if not args.quiet:
        print("  判定: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
