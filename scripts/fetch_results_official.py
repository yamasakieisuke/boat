#!/usr/bin/env python3
from __future__ import annotations

"""
boatrace.jp の公式結果ページから、指定会場・指定日の結果を補完する。
LZH 日次成績が未反映、または一部会場だけ欠けている日の埋め戻し用途。
"""

import argparse
import csv
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent
CSV_DIR = BASE_DIR / "data" / "results_csv"

CSV_HEADER = [
    "date","venue_name","race_no","race_type",
    "weather","wind_dir","wind_ms","wave_cm",
    "rank","waku","reg_no","name",
    "motor_no","boat_no","exhibition_time","course_enter","st_timing","race_time",
    "won3","won3_pay","won3_pop",
    "won2","won2_pay","won2_pop",
    "trio","trio_pay","trio_pop",
    "pair","pair_pay","pair_pop",
]

JCD_TO_VENUE = {
    "01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川",
    "06":"浜名湖","07":"蒲郡","08":"常滑","09":"津","10":"三国",
    "11":"びわこ","12":"住之江","13":"尼崎","14":"鳴門","15":"丸亀",
    "16":"児島","17":"宮島","18":"徳山","19":"下関","20":"若松",
    "21":"芦屋","22":"福岡","23":"唐津","24":"大村",
}

RESULTLIST_URL = "https://www.boatrace.jp/owpc/pc/race/resultlist?hd={date}&jcd={jcd}"
RACERESULT_URL = "https://www.boatrace.jp/owpc/pc/race/raceresult?rno={rno}&jcd={jcd}&hd={date}"
BEFOREINFO_URL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={rno}&jcd={jcd}&hd={date}"


def norm_num(text: str) -> str:
    text = (text or "").replace(",", "").replace("¥", "").replace("\xa0", " ").strip()
    m = re.search(r"(\d+)", text)
    return m.group(1) if m else ""


def combo_from_cell(td) -> str:
    nums = [x.get_text(strip=True) for x in td.select(".numberSet1_number")]
    if nums:
        return "-".join(nums)
    nums = re.findall(r"\d+", td.get_text(" ", strip=True))
    return "-".join(nums)


def parse_start_info(soup) -> tuple[dict[int, dict], str]:
    """
    スタート情報テーブルから {waku: {course, st, kimarite}} と全体決まり手を返す。
    HTML 構造:
      <span class="table1_boatImage1Number is-typeN"> N </span>  ← N = コース順位（進入順）
      <span class="table1_boatImage1Time"> .15  逃げ </span>     ← ST と (1着艇のみ) 決まり手
    数字の先頭は枠番、.XX が ST。
    """
    result: dict[int, dict] = {}
    kimarite_all = ""

    start_tbl = None
    for t in soup.select("table"):
        heads = [th.get_text(" ", strip=True) for th in t.select("thead th")]
        if heads and heads[0] == "スタート情報":
            start_tbl = t
            break
    if not start_tbl:
        return result, kimarite_all

    for tr in start_tbl.select("tbody tr"):
        td = tr.select_one("td")
        if not td:
            continue
        num_span = td.select_one(".table1_boatImage1Number")
        time_span = td.select_one(".table1_boatImage1Time")
        if not num_span:
            continue
        waku_txt = num_span.get_text(strip=True)
        try:
            waku = int(waku_txt)
        except ValueError:
            continue
        course = waku
        for cls in num_span.get("class", []):
            m = re.match(r"is-type(\d)", cls)
            if m:
                course = int(m.group(1))
                break
        time_txt = (time_span.get_text(" ", strip=True) if time_span else "").strip()
        st = ""
        m = re.match(r"(F?\.\d{2}|F?\d\.\d{2})", time_txt)
        if m:
            st = m.group(1)
        # 1着艇の場合、ST 後ろに「逃げ」「差し」等が付く
        km = ""
        if st:
            after = time_txt[len(st):].strip()
            if after:
                km = after.split()[0] if after.split() else ""
        result[waku] = {"course": course, "st_timing": st, "kimarite": km}

    # 決まり手テーブル（単独）からも拾う
    for t in soup.select("table"):
        heads = [th.get_text(" ", strip=True) for th in t.select("thead th")]
        if heads == ["決まり手"]:
            cells = [td.get_text(" ", strip=True) for td in t.select("tbody td")]
            if cells:
                kimarite_all = cells[0].strip()
            break

    return result, kimarite_all


def fetch_exhibition_map(html: str) -> dict[int, dict]:
    """
    beforeinfo ページから {waku: {exhibition_time, tilt}} を返す。
    """
    soup = BeautifulSoup(html, "html.parser")
    out: dict[int, dict] = {}
    for t in soup.select("table"):
        heads = [th.get_text(" ", strip=True) for th in t.select("thead th")]
        if not any("展示" in h for h in heads):
            continue
        # 各艇 = 4行構成 (1行目: 枠/写真/選手名/体重/展示タイム/チルト/...) を抽出
        for tr in t.select("tbody tr"):
            tds = tr.select("td")
            if len(tds) < 6:
                continue
            waku_txt = tds[0].get_text(" ", strip=True)
            if not waku_txt.isdigit():
                continue
            try:
                waku = int(waku_txt)
            except ValueError:
                continue
            ex_time = tds[4].get_text(" ", strip=True).strip()
            tilt    = tds[5].get_text(" ", strip=True).strip()
            out[waku] = {"exhibition_time": ex_time, "tilt": tilt}
        break
    return out


def parse_result_page(html: str, date_str: str, jcd: str, race_no: int,
                      exhibition_map: dict[int, dict] | None = None) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    result_table = None
    for table in soup.select("table"):
        heads = [th.get_text(" ", strip=True) for th in table.select("thead th")]
        if heads[:4] == ["着", "枠", "ボートレーサー", "レースタイム"]:
            result_table = table
            break
    if not result_table:
        return []

    race_type = ""
    title = soup.select_one(".title16_titleDetail__add2020")
    if title:
        race_type = re.sub(r"\s*1800m.*$", "", title.get_text(" ", strip=True)).strip()

    weather = wind_dir = wind_ms = wave_cm = ""
    weather_box = soup.select_one(".weather1")
    if weather_box:
        weather_el = weather_box.select_one(".weather1_bodyUnit.is-weather .weather1_bodyUnitLabelTitle")
        if weather_el:
            weather = weather_el.get_text(strip=True)
        for unit in weather_box.select(".weather1_bodyUnit"):
            key = unit.select_one(".weather1_bodyUnitLabelTitle")
            data = unit.select_one(".weather1_bodyUnitLabelData")
            if not key or not data:
                continue
            label = key.get_text(strip=True)
            if label == "風速":
                wind_ms = norm_num(data.get_text(" ", strip=True))
            elif label == "波高":
                wave_cm = norm_num(data.get_text(" ", strip=True))
        direction = weather_box.select_one(".weather1_bodyUnit.is-windDirection p")
        if direction:
            m = re.search(r"is-wind(\d+)", " ".join(direction.get("class", [])))
            wind_dir = m.group(1) if m else ""

    pays = {k:"" for k in [
        "won3","won3_pay","won3_pop",
        "won2","won2_pay","won2_pop",
        "trio","trio_pay","trio_pop",
        "pair","pair_pay","pair_pop",
    ]}
    pay_table = None
    for table in soup.select("table"):
        heads = [th.get_text(" ", strip=True) for th in table.select("thead th")]
        if heads[:4] == ["勝式", "組番", "払戻金", "人気"]:
            pay_table = table
            break
    if pay_table:
        for tbody in pay_table.select("tbody"):
            tr = tbody.select_one("tr")
            if not tr:
                continue
            tds = tr.select("td")
            if len(tds) < 4:
                continue
            kind = tds[0].get_text(strip=True)
            combo = combo_from_cell(tds[1])
            pay = norm_num(tds[2].get_text(" ", strip=True))
            pop = norm_num(tds[3].get_text(" ", strip=True))
            if kind == "3連単":
                pays.update({"won3": combo, "won3_pay": pay, "won3_pop": pop})
            elif kind == "2連単":
                pays.update({"won2": combo, "won2_pay": pay, "won2_pop": pop})
            elif kind == "3連複":
                pays.update({"trio": combo, "trio_pay": pay, "trio_pop": pop})
            elif kind == "2連複":
                pays.update({"pair": combo, "pair_pay": pay, "pair_pop": pop})

    start_map, _km_all = parse_start_info(soup)
    if exhibition_map is None:
        exhibition_map = {}

    rows = []
    for tr in result_table.select("tbody tr"):
        tds = tr.select("td")
        if len(tds) < 4:
            continue
        rank = tds[0].get_text(strip=True).translate(str.maketrans("１２３４５６", "123456"))
        if rank not in {"1","2","3","4","5","6"}:
            continue
        racer_text = tds[2].get_text(" ", strip=True)
        nums = re.findall(r"\d{4}", racer_text)
        reg_no = nums[0] if nums else ""
        name = re.sub(r"^\d{4}\s*", "", racer_text).strip()
        try:
            waku_int = int(tds[1].get_text(strip=True))
        except ValueError:
            waku_int = 0
        sinfo = start_map.get(waku_int, {})
        einfo = exhibition_map.get(waku_int, {})
        row = {k:"" for k in CSV_HEADER}
        row.update({
            "date": date_str,
            "venue_name": JCD_TO_VENUE[jcd],
            "race_no": str(race_no),
            "race_type": race_type,
            "weather": weather,
            "wind_dir": wind_dir,
            "wind_ms": wind_ms,
            "wave_cm": wave_cm,
            "rank": rank,
            "waku": str(waku_int) if waku_int else tds[1].get_text(strip=True),
            "reg_no": reg_no,
            "name": name,
            "exhibition_time": einfo.get("exhibition_time", ""),
            "course_enter":    str(sinfo.get("course", "")) if sinfo.get("course") else "",
            "st_timing":       sinfo.get("st_timing", ""),
            "race_time": tds[3].get_text(strip=True).replace("'", ".").replace('"', ""),
            **pays,
        })
        rows.append(row)
    return rows


def discover_available_races(date_str: str, jcd: str, session: requests.Session) -> list[int]:
    html = session.get(RESULTLIST_URL.format(date=date_str, jcd=jcd), timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    races = []
    for a in soup.select('a[href*="/owpc/pc/race/raceresult?"]'):
        href = a.get("href") or ""
        m = re.search(r"rno=(\d+)&jcd=" + re.escape(jcd) + r"&hd=" + re.escape(date_str), href)
        if m:
            races.append(int(m.group(1)))
    return sorted(set(races))


def fetch_official_results(date_str: str, jcd: str) -> list[dict]:
    session = requests.Session()
    rows = []
    for race_no in discover_available_races(date_str, jcd, session):
        html = session.get(RACERESULT_URL.format(date=date_str, jcd=jcd, rno=race_no), timeout=30).text
        ex_map: dict[int, dict] = {}
        try:
            ex_html = session.get(BEFOREINFO_URL.format(date=date_str, jcd=jcd, rno=race_no), timeout=30).text
            ex_map = fetch_exhibition_map(ex_html)
        except Exception as e:
            print(f"[WARN] beforeinfo 取得失敗 {date_str} {jcd} R{race_no}: {e}")
        rows.extend(parse_result_page(html, date_str, jcd, race_no, exhibition_map=ex_map))
    return rows


def write_day_csv(date_str: str, jcd: str, rows_out: list[dict], replace: bool) -> Path:
    csv_path = CSV_DIR / f"{date_str}.csv"
    existing = []
    if csv_path.exists():
        with open(csv_path, encoding="utf-8-sig") as f:
            existing = list(csv.DictReader(f))
    if replace:
        venue_name = JCD_TO_VENUE[jcd]
        existing = [r for r in existing if not (r.get("date") == date_str and r.get("venue_name") == venue_name)]
    existing.extend(rows_out)
    def _rank_key(r: dict) -> int:
        """非完走艇の rank は "F"/"S1"/"K0" 等のコード。数値でなければ末尾に送る。"""
        v = str(r.get("rank") or "").strip()
        return int(v) if v.isdigit() else 99

    existing.sort(key=lambda r: (r.get("date", ""), r.get("venue_name", ""),
                                 int(r.get("race_no") or 0), _rank_key(r)))
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(existing)
    return csv_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYYMMDD")
    ap.add_argument("--jcd", required=True, help="会場コード")
    ap.add_argument("--replace", action="store_true", help="同日同会場の既存行を置換して保存")
    args = ap.parse_args()

    jcd = str(args.jcd).zfill(2)
    if jcd not in JCD_TO_VENUE:
        raise SystemExit(f"unknown jcd: {jcd}")

    rows = fetch_official_results(args.date, jcd)
    if not rows:
        print(f"[INFO] 公式結果ページに公開データなし: {args.date} {jcd} {JCD_TO_VENUE[jcd]}")
        return
    csv_path = write_day_csv(args.date, jcd, rows, replace=args.replace)
    print(f"[OK] 公式結果補完: {args.date} {jcd} {JCD_TO_VENUE[jcd]} {len(rows)}行 → {csv_path}")


if __name__ == "__main__":
    main()
