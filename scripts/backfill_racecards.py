#!/usr/bin/env python3
"""
data/racecards/ の再取得（バックフィル）ツール

2026-08-10 の iCloud 事故で `data/racecards/` が全消失した。過去日のバックテストを
再開するために、boatrace.jp の出走表ページから過去分を取り直す。

## 設計方針

- **パーサは持たない**。`scripts/scraper.py` の `scrape_racecard()` をそのまま呼ぶ。
  出走表のHTML構造が変わったときに直す場所を1箇所に保つため。
- **取得対象は `data/results_csv/` から作る**。結果CSVに存在する (日付, 会場, R) だけを
  取りに行く。開催のない会場・中止レースを叩かずに済み、無駄なリクエストが出ない。
  そもそも結果が無い日の出走表を取ってもバックテストには使えない。
- **再開は「ファイルがあればスキップ」で実現する**。進捗ファイルを別に持つと、それ自体が
  壊れたときに事故る。実体（保存済みJSON）を唯一の真実にする。
- **既定値は安全側**。`--sleep` は長め、`--limit` は小さめ。大量取得は明示的に
  引数を渡したときだけ起きる。

## 相手サーバへの配慮（重要）

boatrace.jp は第三者のサーバ。実測で1リクエストの応答に **8〜10秒**かかる
（TTFB がそのまま8秒台。回線ではなくサーバ側の処理時間）。つまり何もしなくても
直列実行なら 0.1 req/s 程度にしかならない。ここにさらに sleep を足す。

- 直列（並列なし）固定。
- `scraper.fetch()` が内部で 1.5 秒待つ。`--sleep` はそれに**上乗せ**される。
- 連続失敗が `--max-failures` に達したら中断する（サーバが不調なときに叩き続けない）。
- User-Agent は素性と連絡先を名乗るものに差し替える（`--user-agent` で変更可）。

## 使い方

    # 何件取ることになるか数えるだけ（リクエストは飛ばない）
    python3 scripts/backfill_racecards.py --dry-run --from 20260601 --to 20260630

    # 実際に取る（既定は控えめ。まず少数で様子を見る）
    python3 scripts/backfill_racecards.py --from 20260601 --to 20260630 --limit 50

    # 全件（承認後に実行すること）
    python3 scripts/backfill_racecards.py --limit 0 --sleep 2.0
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import json
import signal
import sys
import time
from pathlib import Path

BOAT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOAT_DIR))

import scripts.scraper as sc  # noqa: E402  パーサを二重に持たないための再利用

DATA_DIR = BOAT_DIR / "data"
RESULTS_CSV_DIR = DATA_DIR / "results_csv"
RACECARD_DIR = DATA_DIR / "racecards"
CONFIG_PATH = BOAT_DIR / "config.json"

DEFAULT_USER_AGENT = (
    "boat-backfill/1.0 (personal backtest data recovery; "
    "contact: ask11nl@gmail.com) python-requests"
)

# 既定値はすべて安全側に倒す
DEFAULT_SLEEP = 3.0     # scraper.fetch() 内部の 1.5 秒に上乗せされる
DEFAULT_LIMIT = 50      # 0 で無制限。既定では「うっかり全件」が起きない
DEFAULT_MAX_FAILURES = 10   # 連続失敗でアボート


# ──────────────────────────────────────────
# 取得対象の組み立て
# ──────────────────────────────────────────
def load_venue_name_map() -> dict[str, str]:
    """config.json の会場マスタから 会場名 -> jcd の対応表を作る。"""
    venues = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["venues"]
    return {name: jcd for jcd, name in venues.items()}


def collect_targets(date_from: str | None, date_to: str | None,
                    jcd_filter: set[str] | None) -> list[tuple[str, str, int]]:
    """results_csv から (date, jcd, race_no) の一覧を作って返す（ソート済み・重複排除済み）。"""
    name2jcd = load_venue_name_map()
    targets: set[tuple[str, str, int]] = set()

    for path in sorted(RESULTS_CSV_DIR.glob("*.csv")):
        if path.stem == "results_all":
            continue  # 日別CSVの合算。venue_name が空なので使えない
        # ファイル名は YYYYMMDD.csv。日付レンジ外はファイルごと読み飛ばす
        if path.stem.isdigit():
            if date_from and path.stem < date_from:
                continue
            if date_to and path.stem > date_to:
                continue
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                date = (row.get("date") or "").strip()
                venue = (row.get("venue_name") or "").strip()
                rno_raw = (row.get("race_no") or "").strip()
                if not date or not venue or not rno_raw.isdigit():
                    continue
                if date_from and date < date_from:
                    continue
                if date_to and date > date_to:
                    continue
                jcd = name2jcd.get(venue)
                if not jcd:
                    continue
                if jcd_filter and jcd not in jcd_filter:
                    continue
                rno = int(rno_raw)
                if not 1 <= rno <= 12:
                    continue
                targets.add((date, jcd, rno))

    return sorted(targets)


def racecard_path(date: str, jcd: str, rno: int) -> Path:
    return RACECARD_DIR / date / f"{jcd}_R{rno:02d}.json"


def is_done(date: str, jcd: str, rno: int) -> bool:
    """保存済みなら True。中身が壊れている（空/不正JSON）ものは未取得扱いにする。"""
    p = racecard_path(date, jcd, rno)
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("racers"))


# ──────────────────────────────────────────
# 見積り表示
# ──────────────────────────────────────────
def format_estimate(n: int, sleep: float) -> str:
    """1件あたりの実測応答時間を踏まえた所要時間の目安。"""
    per_req = sleep + 1.5 + 8.5   # --sleep + fetch()内部wait + 実測レスポンス時間
    total_sec = n * per_req
    return (f"{n:,}件 × 約{per_req:.1f}秒 = "
            f"約{total_sec/3600:.1f}時間（{total_sec/86400:.1f}日）")


def print_dry_run(pending: list[tuple[str, str, int]],
                  total: int, done: int, sleep: float) -> None:
    print("=" * 64)
    print("DRY RUN — リクエストは一切送信していない")
    print("=" * 64)
    print(f"対象レース数（results_csv 由来）: {total:,}")
    print(f"  取得済み（スキップ）         : {done:,}")
    print(f"  これから取得                 : {len(pending):,}")
    print(f"所要時間の目安                 : {format_estimate(len(pending), sleep)}")

    if not pending:
        return

    by_month = collections.Counter(d[:6] for d, _, _ in pending)
    print("\n── 月別 ──")
    for m in sorted(by_month):
        print(f"  {m[:4]}-{m[4:]}  {by_month[m]:6,}件")

    venues = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["venues"]
    by_jcd = collections.Counter(j for _, j, _ in pending)
    print("\n── 会場別 ──")
    for jcd in sorted(by_jcd):
        name = venues.get(jcd, "?")
        print(f"  {jcd} {name}{'　' * max(0, 5 - len(name))} {by_jcd[jcd]:6,}件")

    print(f"\n最初: {pending[0][0]} jcd={pending[0][1]} R{pending[0][2]:02d}")
    print(f"最後: {pending[-1][0]} jcd={pending[-1][1]} R{pending[-1][2]:02d}")


# ──────────────────────────────────────────
# 本体
# ──────────────────────────────────────────
_interrupted = False


def _on_sigint(signum, frame):  # noqa: ARG001
    global _interrupted
    if _interrupted:
        raise KeyboardInterrupt
    _interrupted = True
    print("\n[INFO] 中断要求を受け付けた。現在のリクエスト完了後に停止する"
          "（もう一度 Ctrl-C で即時終了）", flush=True)


def run(pending: list[tuple[str, str, int]], sleep: float, max_failures: int) -> int:
    ok = 0
    failed: list[tuple[str, str, int]] = []
    consecutive_failures = 0
    started = time.time()

    signal.signal(signal.SIGINT, _on_sigint)

    for i, (date, jcd, rno) in enumerate(pending, 1):
        if _interrupted:
            print("[INFO] 中断した。再実行すれば取得済みはスキップされ続きから走る")
            break

        if i > 1:
            time.sleep(sleep)

        t0 = time.time()
        try:
            result = sc.scrape_racecard(jcd, date, rno)
        except Exception as e:  # noqa: BLE001 1件の失敗で全体を止めない
            print(f"[ERROR] {date} jcd={jcd} R{rno:02d} 例外: {e}")
            result = None
        elapsed = time.time() - t0

        if result:
            ok += 1
            consecutive_failures = 0
        else:
            failed.append((date, jcd, rno))
            consecutive_failures += 1
            print(f"[WARN] 取得失敗: {date} jcd={jcd} R{rno:02d} "
                  f"(連続{consecutive_failures}件目)")
            if consecutive_failures >= max_failures:
                print(f"[ABORT] 連続{max_failures}件失敗。サーバ側の問題の可能性が高いので中断する。"
                      "しばらく時間を空けてから再実行すること")
                break

        if i % 20 == 0 or i == len(pending):
            per = (time.time() - started) / i
            remain = (len(pending) - i) * per
            print(f"[PROGRESS] {i}/{len(pending)} 成功{ok} 失敗{len(failed)} "
                  f"直近{elapsed:.1f}s 平均{per:.1f}s/件 残り約{remain/3600:.1f}h",
                  flush=True)

    dur = time.time() - started
    print("\n" + "=" * 64)
    print(f"完了: 成功 {ok} / 失敗 {len(failed)} / 経過 {dur/60:.1f}分")
    if failed:
        print("失敗一覧（先頭20件）:")
        for date, jcd, rno in failed[:20]:
            print(f"  {date} jcd={jcd} R{rno:02d}")
        print("※ 出走表が公開されていない日（中止・過去すぎる等）も失敗として出る。"
              "再実行すれば同じ対象を再試行する")
    return 0 if not failed else 1


def parse_date_arg(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    v = value.replace("-", "").strip()
    if len(v) != 8 or not v.isdigit():
        raise SystemExit(f"[ERROR] --{label} は YYYYMMDD 形式で指定する: {value}")
    try:
        datetime.datetime.strptime(v, "%Y%m%d")
    except ValueError:
        raise SystemExit(f"[ERROR] --{label} が日付として不正: {value}")
    return v


def main() -> int:
    p = argparse.ArgumentParser(
        description="data/racecards/ を boatrace.jp から再取得する（中断・再開可）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="既定値は意図的に控えめ。全件取得は --limit 0 を明示的に渡したときだけ起きる。",
    )
    p.add_argument("--from", dest="date_from", default=None,
                   help="開始日 YYYYMMDD（含む）。省略時は results_csv の最古日")
    p.add_argument("--to", dest="date_to", default=None,
                   help="終了日 YYYYMMDD（含む）。省略時は results_csv の最新日")
    p.add_argument("--jcd", default=None,
                   help="会場コードを絞る。カンマ区切りで複数可（例: 22,24）")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                   help=f"取得する最大件数。0で無制限（既定: {DEFAULT_LIMIT}）")
    p.add_argument("--sleep", type=float, default=DEFAULT_SLEEP,
                   help=f"1件ごとの追加待機秒。scraper.fetch() の1.5秒に上乗せされる"
                        f"（既定: {DEFAULT_SLEEP}）")
    p.add_argument("--dry-run", action="store_true",
                   help="件数と見積りだけ出して終了。リクエストは送らない")
    p.add_argument("--max-failures", type=int, default=DEFAULT_MAX_FAILURES,
                   help=f"連続失敗がこの数に達したら中断（既定: {DEFAULT_MAX_FAILURES}）")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT,
                   help="送信する User-Agent。素性と連絡先を名乗る文字列を既定にしている")
    args = p.parse_args()

    date_from = parse_date_arg(args.date_from, "from")
    date_to = parse_date_arg(args.date_to, "to")
    if date_from and date_to and date_from > date_to:
        raise SystemExit("[ERROR] --from が --to より後になっている")
    if args.sleep < 0:
        raise SystemExit("[ERROR] --sleep は0以上")

    jcd_filter = None
    if args.jcd:
        jcd_filter = {j.strip().zfill(2) for j in args.jcd.split(",") if j.strip()}
        known = set(json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["venues"])
        unknown = jcd_filter - known
        if unknown:
            raise SystemExit(f"[ERROR] 未知の会場コード: {sorted(unknown)}")

    if not RESULTS_CSV_DIR.exists():
        raise SystemExit(f"[ERROR] {RESULTS_CSV_DIR} が無い。取得対象を決められない")

    targets = collect_targets(date_from, date_to, jcd_filter)
    if not targets:
        print("[INFO] 対象レースが0件。--from/--to/--jcd を確認すること")
        return 0

    pending = [t for t in targets if not is_done(*t)]
    done = len(targets) - len(pending)

    if args.limit and args.limit > 0:
        pending = pending[:args.limit]

    if args.dry_run:
        print_dry_run(pending, len(targets), done, args.sleep)
        if args.limit and args.limit > 0:
            print(f"\n※ --limit {args.limit} 適用後の件数。"
                  "全体を見るには --limit 0 を付けて再実行する")
        return 0

    if not pending:
        print(f"[INFO] 取得対象はすべて取得済み（{done:,}件）")
        return 0

    # 相手サーバに名乗る（scraper.py 側は書き換えず、実行時にヘッダだけ差し替える）
    sc.HEADERS["User-Agent"] = args.user_agent

    print(f"対象 {len(targets):,}件 / 取得済み {done:,}件 / 今回取得 {len(pending):,}件")
    print(f"見積り: {format_estimate(len(pending), args.sleep)}")
    print(f"User-Agent: {args.user_agent}")
    print("Ctrl-C で安全に中断できる（再実行で続きから）\n")

    return run(pending, args.sleep, args.max_failures)


if __name__ == "__main__":
    sys.exit(main())
