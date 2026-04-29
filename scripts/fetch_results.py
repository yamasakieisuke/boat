#!/usr/bin/env python3
from __future__ import annotations

"""
ボートレース 競走成績 一括取得・CSV変換
========================================
公式サーバーから LZH 形式の競走成績をダウンロードし、
固定長テキストを解析して CSV に変換・蓄積します。

出力 CSV 列:
  date, venue_name, race_no, race_type,
  weather, wind_dir, wind_ms, wave_cm,
  rank, waku, reg_no, name,
  motor_no, boat_no, exhibition_time, course_enter, st_timing, race_time,
  won3, won3_pay, won3_pop,
  won2, won2_pay, won2_pop,
  trio, trio_pay, trio_pop,
  pair, pair_pay, pair_pop

使い方:
  python fetch_results.py --years 3          # 直近3年
  python fetch_results.py --start 20230101 --end 20231231
  python fetch_results.py --date 20250304    # 1日だけ
"""

import re, csv, time, json, argparse, datetime, requests, lhafile
from pathlib import Path
from io import BytesIO

from fetch_results_official import fetch_official_results

BASE_DIR = Path(__file__).parent.parent
RAW_DIR  = BASE_DIR / "data" / "results_raw"
CSV_DIR  = BASE_DIR / "data" / "results_csv"
OUT_CSV  = CSV_DIR  / "results_all.csv"
RAW_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL  = "https://www1.mbrace.or.jp/od2/K/{ym}/k{ymd6}.lzh"
WAIT_SEC  = 1.5
TIMEOUT   = 30

CSV_HEADER = [
    "date","venue_name","race_no","race_type",
    "weather","wind_dir","wind_ms","wave_cm",
    "rank","waku","reg_no","name",
    "motor_no","boat_no","exhibition_time","course_enter","st_timing","race_time",
    "won3","won3_pay","won3_pop",
    "won2","won2_pay","won2_pop",
    "trio","trio_pay","trio_pop",
    "pair","pair_pay","pair_pop",
    # v5.21: 福岡オリジナル展示（一周/まわり足/直線）。福岡以外は空、過去レースも空
    "lap_time","turn_time","straight_time",
    "lap_rank","turn_rank","straight_rank",
    "exhibition_eval",
]

# ── 正規表現 ──────────────────────────────────────────
# レース環境行: "   1R  カタメン  H1800m  雨  風  北  1m  波  2cm"
RE_ENV = re.compile(
    r'^\s+(\d{1,2})R\s+(.+?)\s+H\d+m\s+'
    r'(\S+)\s+風\s+(\S+)\s+(\d+)m\s+波\s+(\d+)cm'
)
# 着順行（全角SP正規化後）
RE_RANK = re.compile(
    r'^\s{2}(\d{2})\s{2}(\d)\s(\d{4})\s(.+?)\s+'
    r'(\d{1,3})\s+(\d{1,3})\s+(\d\.\d{2})\s+(\d)\s+([\dF.]+)\s*([\d:. ]*)'
)
# 払戻行（個別レース内）
RE_PAY = re.compile(
    r'(３連単|２連単|３連複|２連複)\s+([\d-]+)\s+(\d+)(?:\s+人気\s+(\d+))?'
)
# 先頭サマリー: "  1R  1-4-2  3930  1-2-4  700  1-4  1160  1-4  1050"
RE_SUM = re.compile(
    r'^\s+(\d{1,2})R\s+([\d-]+)\s+(\d+)\s+([\d-]+)\s+(\d+)\s+([\d-]+)\s+(\d+)\s+([\d-]+)\s+(\d+)'
)
# 会場名（全角スペース \u3000 を含む2文字以上の会場名に対応）
RE_VENUE = re.compile(r'ボートレース([\S\u3000]+)\s*$')
RE_BLOCK_BEGIN = re.compile(r'^(\d{2})KBGN$')
RE_BLOCK_END   = re.compile(r'^(\d{2})KEND$')
PLACEHOLDER_TEXT = "データは、この場の全レース終了後に登録されます。"


def norm(line: str) -> str:
    """全角スペース → 半角スペース"""
    return line.replace('\u3000', ' ')

def clean(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()


def find_placeholder_jcds(text: str) -> list[str]:
    """
    LZH テキスト内で「会場ブロックはあるが結果本文が未反映」の jcd を返す。
    例:
      24KBGN
      ボートレース大　村
      データは、この場の全レース終了後に登録されます。
      24KEND
    """
    pending: list[str] = []
    current_jcd = ""
    buf: list[str] = []
    for line in text.splitlines():
        m = RE_BLOCK_BEGIN.match(line.strip())
        if m:
            current_jcd = m.group(1)
            buf = []
            continue
        m = RE_BLOCK_END.match(line.strip())
        if m and current_jcd:
            block = "\n".join(buf)
            if PLACEHOLDER_TEXT in block:
                pending.append(current_jcd)
            current_jcd = ""
            buf = []
            continue
        if current_jcd:
            buf.append(line)
    return sorted(set(pending))


# ── ダウンロード & 解凍 ───────────────────────────────
def fetch_text(date_str: str) -> str | None:
    txt_path = RAW_DIR / f"K{date_str[2:]}.txt"
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8", errors="replace")

    url = BASE_URL.format(ym=date_str[:6], ymd6=date_str[2:])
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
    except Exception as e:
        print(f"[WARN] {date_str}: {e}")
        return None
    try:
        lhf  = lhafile.LhaFile(BytesIO(r.content))
        info = lhf.infolist()
        if not info:
            return None
        text = lhf.read(info[0].filename).decode("cp932", errors="replace")
        txt_path.write_text(text, encoding="utf-8")
        return text
    except Exception as e:
        print(f"[WARN] LZH解凍失敗 {date_str}: {e}")
        return None


# ── テキストパーサー ──────────────────────────────────
def parse_text(text: str, date_str: str) -> list[dict]:
    lines = text.splitlines()

    # 払戻サマリーを先に収集（先頭ブロック）
    pay_db: dict[int, dict] = {}
    for line in lines:
        m = RE_SUM.match(line)
        if m:
            rn = int(m.group(1))
            pay_db[rn] = {
                "won3": m.group(2), "won3_pay": m.group(3),
                "trio": m.group(4), "trio_pay": m.group(5),
                "won2": m.group(6), "won2_pay": m.group(7),
                "pair": m.group(8), "pair_pay": m.group(9),
                "won3_pop":"","won2_pop":"","trio_pop":"","pair_pop":"",
            }

    venue_name = ""
    race_no    = 0
    race_type  = ""
    weather    = ""
    wind_dir   = ""
    wind_ms    = ""
    wave_cm    = ""
    cur_ranks: list[dict] = []
    records:   list[dict] = []

    def flush():
        nonlocal cur_ranks
        pd = pay_db.get(race_no, {})
        for r in cur_ranks:
            records.append({
                "date": date_str, "venue_name": venue_name,
                "race_no": race_no, "race_type": race_type,
                "weather": weather, "wind_dir": wind_dir,
                "wind_ms": wind_ms, "wave_cm": wave_cm,
                **r,
                "won3":     pd.get("won3",""),    "won3_pay": pd.get("won3_pay",""),
                "won3_pop": pd.get("won3_pop",""),
                "won2":     pd.get("won2",""),    "won2_pay": pd.get("won2_pay",""),
                "won2_pop": pd.get("won2_pop",""),
                "trio":     pd.get("trio",""),    "trio_pay": pd.get("trio_pay",""),
                "trio_pop": pd.get("trio_pop",""),
                "pair":     pd.get("pair",""),    "pair_pay": pd.get("pair_pay",""),
                "pair_pop": pd.get("pair_pop",""),
            })
        cur_ranks = []

    for line in lines:
        nl = norm(line)

        # 会場名（全角スペースを除去して正規化）
        if 'ボートレース' in line and re.search(r'\d{4}/', line):
            m = RE_VENUE.search(line)
            if m:
                vn = clean(m.group(1)).replace('\u3000', '').replace(' ', '').strip()
                if vn:
                    venue_name = vn

        # レース環境行
        m = RE_ENV.match(line)
        if m:
            flush()
            race_no   = int(m.group(1))
            race_type = clean(m.group(2))
            weather   = clean(norm(m.group(3)))
            wind_dir  = clean(norm(m.group(4)))
            wind_ms   = m.group(5)
            wave_cm   = m.group(6)
            continue

        # 着順行
        m = RE_RANK.match(nl)
        if m and race_no > 0:
            rt = m.group(10).strip()
            # "1.49.0" や ".  ." を整理
            rt = rt if re.search(r'\d', rt) else ""
            cur_ranks.append({
                "rank":            m.group(1).lstrip("0") or "0",
                "waku":            m.group(2),
                "reg_no":          m.group(3),
                "name":            clean(m.group(4)),
                "motor_no":        m.group(5),
                "boat_no":         m.group(6),
                "exhibition_time": m.group(7),
                "course_enter":    m.group(8),
                "st_timing":       m.group(9),
                "race_time":       rt,
            })
            continue

        # 人気行（個別レース内払戻）→ pop を補完
        m = RE_PAY.search(line)
        if m:
            kind = m.group(1)
            comb = m.group(2)
            pay  = m.group(3)
            pop  = m.group(4) or ""
            rn   = race_no
            if rn not in pay_db:
                pay_db[rn] = {k:"" for k in ["won3","won3_pay","won3_pop",
                                              "won2","won2_pay","won2_pop",
                                              "trio","trio_pay","trio_pop",
                                              "pair","pair_pay","pair_pop"]}
            if   kind == "３連単": pay_db[rn].update({"won3":comb,"won3_pay":pay,"won3_pop":pop})
            elif kind == "２連単": pay_db[rn].update({"won2":comb,"won2_pay":pay,"won2_pop":pop})
            elif kind == "３連複": pay_db[rn].update({"trio":comb,"trio_pay":pay,"trio_pop":pop})
            elif kind == "２連複": pay_db[rn].update({"pair":comb,"pair_pay":pay,"pair_pop":pop})

    flush()
    return records


# ── 福岡オリジナル展示の join（v5.21） ────────────────
def _attach_fukuoka_original_exhibition(records: list[dict], date_str: str) -> None:
    """
    福岡(venue_name=='福岡')のレコードに対し、scrape済の
    data/raw/{date}/22_R{nn}_original_exhibition.json から
    lap_time / turn_time / straight_time / lap_rank / turn_rank /
    straight_rank / exhibition_eval を join する（in-place 更新）。
    JSON が無いレース・福岡以外のレコードは空欄のまま。
    """
    raw_dir = BASE_DIR / "data" / "raw" / date_str
    if not raw_dir.exists():
        return

    # レース番号→{waku: row} の lookup を作る
    cache: dict[int, dict[int, dict]] = {}
    for r in records:
        if r.get("venue_name") != "福岡":
            continue
        try:
            race_no = int(r.get("race_no", 0))
            waku    = int(r.get("waku", 0))
        except (TypeError, ValueError):
            continue
        if race_no not in cache:
            json_path = raw_dir / f"22_R{race_no:02d}_original_exhibition.json"
            if not json_path.exists():
                cache[race_no] = {}
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                cache[race_no] = {}
                continue
            cache[race_no] = {
                int(row.get("waku", 0)): row
                for row in data.get("rows", []) or []
                if isinstance(row.get("waku"), int)
            }
        row = cache[race_no].get(waku)
        if not row:
            continue
        r["lap_time"]        = row.get("lap_time", "") if row.get("lap_time") is not None else ""
        r["turn_time"]       = row.get("turn_time", "") if row.get("turn_time") is not None else ""
        r["straight_time"]   = row.get("straight_time", "") if row.get("straight_time") is not None else ""
        r["lap_rank"]        = row.get("lap_rank", "") if row.get("lap_rank") is not None else ""
        r["turn_rank"]       = row.get("turn_rank", "") if row.get("turn_rank") is not None else ""
        r["straight_rank"]   = row.get("straight_rank", "") if row.get("straight_rank") is not None else ""
        r["exhibition_eval"] = row.get("evaluation", "") if row.get("evaluation") is not None else ""


# ── CSV 書き出し ──────────────────────────────────────
def write_csv(records: list[dict], path: Path, append=True):
    mode   = "a" if (append and path.exists()) else "w"
    need_h = not (append and path.exists())
    with open(path, mode, newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER, extrasaction="ignore")
        if need_h:
            w.writeheader()
        w.writerows(records)


# ── 日付リスト ────────────────────────────────────────
def date_range(start: str, end: str) -> list[str]:
    s = datetime.date(int(start[:4]), int(start[4:6]), int(start[6:]))
    e = datetime.date(int(end[:4]),   int(end[4:6]),   int(end[6:]))
    out, d = [], s
    while d <= e:
        out.append(d.strftime("%Y%m%d"))
        d += datetime.timedelta(days=1)
    return out


# ── 1日分処理 ────────────────────────────────────────
def process_day(date_str: str) -> list[dict]:
    text = fetch_text(date_str)
    if not text:
        return []
    records = parse_text(text, date_str)
    placeholder_jcds = find_placeholder_jcds(text)
    if placeholder_jcds:
        for jcd in placeholder_jcds:
            try:
                extra = fetch_official_results(date_str, jcd)
            except Exception as e:
                print(f"[WARN] 公式結果補完失敗 {date_str} {jcd}: {e}")
                continue
            if extra:
                records.extend(extra)
                print(f"[INFO] 公式結果補完 {date_str} {jcd}: {len(extra)}行")
            else:
                print(f"[INFO] 公式結果未公開 {date_str} {jcd}")
    if records:
        records.sort(key=lambda r: (r.get("venue_name", ""), int(r.get("race_no", 0) or 0), int(r.get("rank", 99) or 99)))
        # v5.21: 福岡レコードにオリジナル展示（一周/まわり足/直線）を join
        _attach_fukuoka_original_exhibition(records, date_str)
        write_csv(records, CSV_DIR / f"{date_str}.csv", append=False)
    return records


# ── メイン ───────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years",    type=int, default=3)
    ap.add_argument("--start",    type=str, default="")
    ap.add_argument("--end",      type=str, default="")
    ap.add_argument("--date",     type=str, default="")
    ap.add_argument("--no-merge", action="store_true")
    args = ap.parse_args()

    today     = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=1)).strftime("%Y%m%d")

    if args.date:
        dates = [args.date]
    else:
        end   = args.end   or yesterday
        start = args.start or (today - datetime.timedelta(days=365*args.years)).strftime("%Y%m%d")
        dates = date_range(start, end)

    print(f"取得期間: {dates[0]} 〜 {dates[-1]}  計{len(dates)}日")
    print(f"保存先  : {CSV_DIR}\n")

    all_records, ok, skip = [], 0, 0

    for i, d in enumerate(dates, 1):
        day_csv = CSV_DIR / f"{d}.csv"
        if day_csv.exists():
            skip += 1
            if i % 100 == 0:
                print(f"  [{i:4d}/{len(dates)}] {d} skip")
            continue

        print(f"  [{i:4d}/{len(dates)}] {d} ...", end=" ", flush=True)
        recs = process_day(d)

        if recs:
            all_records.extend(recs)
            ok += 1
            venues = len(set(r["venue_name"] for r in recs))
            print(f"✓ {len(recs):4d}行  {venues}場")
        else:
            print("- 休場/データなし")

        time.sleep(WAIT_SEC)

    if not args.no_merge and all_records:
        print(f"\n全期間CSV書き込み中: {OUT_CSV}")
        write_csv(all_records, OUT_CSV, append=True)

    print(f"\n完了: 取得{ok}日 / スキップ{skip}日 / 新規{len(all_records)}レコード")


if __name__ == "__main__":
    main()
