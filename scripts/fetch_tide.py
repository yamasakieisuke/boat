#!/usr/bin/env python3
"""
潮汐データ自動取得スクリプト v1.0
──────────────────────────────────────────────────────────────
気象庁「潮汐・海面水位のデータ」から満潮・干潮の時刻と高さを取得し、
各レースの開始予定時刻における潮汐ステータスを推定して保存する。

保存先: data/tides/{date}/{jcd}_tide.json
predictor.py から load_tide(jcd, date) で読み込む。

使い方:
  # 今日の福岡(22)の潮汐を取得
  python3 scripts/fetch_tide.py --jcd 22

  # 日付と複数会場を指定
  python3 scripts/fetch_tide.py --jcd 22 --date 20260315

  # 全tidal会場を一括取得
  python3 scripts/fetch_tide.py --all
──────────────────────────────────────────────────────────────
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import datetime
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── 会場コード → 気象庁 潮汐観測局コード ──────────────────────────
# tidal=True の会場のみ定義（内陸は None）
VENUE_TO_JMA_STN = {
    "01": None,   # 桐生（内陸）
    "02": None,   # 戸田（内陸）
    "03": "TK",   # 江戸川 → 東京
    "04": "TK",   # 平和島 → 東京
    "05": "TK",   # 多摩川 → 東京
    "06": "ZU",   # 浜名湖 → 舞阪（浜名湖口）
    "07": "NG",   # 蒲郡  → 名古屋
    "08": "NG",   # 常滑  → 名古屋
    "09": "TB",   # 津    → 鳥羽
    "10": "XM",   # 三国  → 敦賀
    "11": None,   # びわこ（内陸）
    "12": "OS",   # 住之江 → 大阪
    "13": "KB",   # 尼崎  → 神戸
    "14": "TA",   # 鳴門  → 高松
    "15": "TA",   # 丸亀  → 高松
    "16": "UN",   # 児島  → 宇野
    "17": "Q8",   # 宮島  → 広島
    "18": "QA",   # 徳山  → 徳山
    "19": "DS",   # 下関  → 下関
    "20": "O3",   # 若松  → 苅田
    "21": "O3",   # 芦屋  → 苅田
    "22": "QF",   # 福岡  → 博多
    "23": "KA",   # 唐津  → 唐津
    "24": "NS",   # 大村  → 長崎
}

# ── レース番号ごとの標準開始時刻（会場によって前後するが概算） ────
# 実際のレース時刻が取得できない場合のフォールバック
DEFAULT_RACE_TIMES = {
    1: "10:00", 2: "10:45", 3: "11:30", 4: "12:15",
    5: "13:00", 6: "13:45", 7: "14:30", 8: "15:15",
    9: "16:00", 10: "16:45", 11: "17:30", 12: "18:15",
}

# 満潮・干潮ピークとみなす許容範囲（分）
PEAK_TOLERANCE_MIN = 60


def fetch_html(url, params=None, wait=1.5):
    time.sleep(wait)
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text
    except Exception as e:
        print(f"[ERROR] fetch: {url} → {e}")
        return None


def parse_time_hm(t_str):
    """'8:35' → datetime.time(8, 35)、失敗時はNone"""
    t_str = t_str.strip()
    if not t_str or t_str == "*":
        return None
    m = re.match(r"(\d{1,2}):(\d{2})", t_str)
    if m:
        return datetime.time(int(m.group(1)), int(m.group(2)))
    return None


def fetch_tide_events(stn_code: str, date_str: str):
    """
    気象庁から満潮・干潮イベントリストを取得。
    返値: [{"time": datetime.time, "type": "high"|"low", "height_cm": int}, ...]

    テーブル行フォーマット（18セル）:
      cells[0] = "YYYY/MM/DD(曜日)"  ← 日付
      cells[1] = ""  ← 月齢記号（朔/上弦/望/下弦 or 空）
      cells[2..9]  = 満潮1〜4の（時刻, 高さcm）× 4組
      cells[10..17] = 干潮1〜4の（時刻, 高さcm）× 4組
    """
    year  = date_str[:4]
    month = date_str[4:6].lstrip("0") or "1"
    day   = date_str[6:8].lstrip("0") or "1"

    html = fetch_html(
        "https://www.data.jma.go.jp/kaiyou/db/tide/suisan/suisan.php",
        params={"stn": stn_code, "ys": year, "ms": month, "ds": day, "de": day},
        wait=2.0,
    )
    if not html:
        return None

    soup   = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    # 満潮・干潮テーブルを探す
    # 条件: 最初のヘッダー行の最初セルが「年/月/日」を含む
    target_table = None
    for tbl in tables:
        rows = tbl.find_all("tr")
        if len(rows) < 3:
            continue
        first_cells = [td.get_text(strip=True) for td in rows[0].find_all(["td","th"])]
        if first_cells and "年/月/日" in first_cells[0]:
            target_table = tbl
            break

    if not target_table:
        print(f"[WARN] 潮汐テーブルが見つかりません: stn={stn_code}")
        return None

    date_prefix = f"{year}/{month.zfill(2)}/{day.zfill(2)}"
    events = []

    for row in target_table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        # 対象日付の行を検出（cells[0] が日付で始まる）
        if not cells or date_prefix not in cells[0]:
            continue
        if len(cells) < 10:
            continue

        # cells[1] は月齢記号（スキップ）
        # cells[2..9]  → 満潮 4組
        # cells[10..17] → 干潮 4組
        def parse_pairs(start, count=4):
            result = []
            for i in range(count):
                idx_t = start + i * 2
                idx_h = start + i * 2 + 1
                if idx_h >= len(cells):
                    break
                t_str = cells[idx_t].strip()
                h_str = cells[idx_h].strip()
                t = parse_time_hm(t_str)
                if t and h_str != "*" and re.match(r"-?\d+", h_str):
                    result.append((t, int(h_str)))
            return result

        for t, h in parse_pairs(start=2, count=4):
            events.append({"time": t, "type": "high", "height_cm": h})
        for t, h in parse_pairs(start=10, count=4):
            events.append({"time": t, "type": "low", "height_cm": h})
        break

    if not events:
        return None

    events.sort(key=lambda e: e["time"].hour * 60 + e["time"].minute)
    return events


def tide_status_at(events: list[dict], race_time_str: str) -> dict:
    """
    レース時刻における潮汐ステータスを推定。
    返値:
      {
        "status":   "high_tide"|"low_tide"|"rising_tide"|"falling_tide",
        "label_jp": "満潮"|"干潮"|"上げ"|"下げ",
        "height_pct": 0〜100  (干潮=0, 満潮=100 の相対位置),
        "next_event": {"type": ..., "time": "HH:MM", "height_cm": ...},
        "note": "次の満潮 XX:XX(XXXcm) まで約XX分"
      }
    """
    t_obj = parse_time_hm(race_time_str)
    if not t_obj or not events:
        return {"status": None, "label_jp": "不明", "height_pct": 50}

    race_min = t_obj.hour * 60 + t_obj.minute

    # イベントを分に変換
    evs = [{"min": e["time"].hour * 60 + e["time"].minute, **e} for e in events]

    # レース時刻の前後イベントを探す
    prev_ev = None
    next_ev = None
    for ev in evs:
        if ev["min"] <= race_min:
            prev_ev = ev
        elif next_ev is None:
            next_ev = ev

    # ステータス判定
    if prev_ev is None:
        # レース時刻が全イベントより前 → 最初のイベントに向かって変化
        if next_ev:
            status = "rising_tide" if next_ev["type"] == "high" else "falling_tide"
        else:
            status = None
    elif next_ev is None:
        # レース時刻が全イベントより後 → 最後のイベントからの延長
        status = "falling_tide" if prev_ev["type"] == "high" else "rising_tide"
    else:
        # 前後イベントが存在
        diff_from_prev = race_min - prev_ev["min"]
        diff_to_next   = next_ev["min"] - race_min

        # ピーク付近判定
        if diff_from_prev <= PEAK_TOLERANCE_MIN and prev_ev["type"] == "high":
            status = "high_tide"
        elif diff_from_prev <= PEAK_TOLERANCE_MIN and prev_ev["type"] == "low":
            status = "low_tide"
        elif diff_to_next <= PEAK_TOLERANCE_MIN and next_ev["type"] == "high":
            status = "high_tide"
        elif diff_to_next <= PEAK_TOLERANCE_MIN and next_ev["type"] == "low":
            status = "low_tide"
        elif next_ev["type"] == "high":
            status = "rising_tide"
        else:
            status = "falling_tide"

    label_map = {
        "high_tide":    "満潮",
        "low_tide":     "干潮",
        "rising_tide":  "上げ",
        "falling_tide": "下げ",
    }

    # 潮位パーセント（前後のイベント高さから線形補間）
    height_pct = 50
    if prev_ev and next_ev:
        span = next_ev["min"] - prev_ev["min"]
        if span > 0:
            ratio = (race_min - prev_ev["min"]) / span
            h0 = prev_ev["height_cm"]
            h1 = next_ev["height_cm"]
            # 全イベントの最大・最小で正規化
            h_min = min(e["height_cm"] for e in evs)
            h_max = max(e["height_cm"] for e in evs)
            if h_max > h_min:
                h_interp = h0 + (h1 - h0) * ratio
                height_pct = round((h_interp - h_min) / (h_max - h_min) * 100)

    # 次のイベント情報
    next_info = {}
    if next_ev:
        mins_to_next = next_ev["min"] - race_min
        next_label   = "満潮" if next_ev["type"] == "high" else "干潮"
        next_time_str = f"{next_ev['time'].hour}:{next_ev['time'].minute:02d}"
        next_info = {
            "type":       next_ev["type"],
            "time":       next_time_str,
            "height_cm":  next_ev["height_cm"],
            "mins_away":  mins_to_next,
            "note":       f"次の{next_label} {next_time_str}({next_ev['height_cm']}cm)まで約{mins_to_next}分",
        }

    return {
        "status":     status,
        "label_jp":   label_map.get(status, "不明"),
        "height_pct": height_pct,
        "next_event": next_info,
    }


def fetch_and_save_tide(jcd: str, date_str: str):
    """
    指定会場・日付の潮汐データを取得し、全レース分のステータスを保存。
    """
    stn = VENUE_TO_JMA_STN.get(jcd)
    if not stn:
        print(f"[SKIP] {jcd}: 潮汐対象外（内陸または未設定）")
        return None

    print(f"[INFO] 潮汐データ取得中: 会場={jcd}  観測局={stn}  日付={date_str}")
    events = fetch_tide_events(stn, date_str)
    if not events:
        print(f"[WARN] 潮汐イベント取得失敗: {jcd} / {stn}")
        return None

    # イベント一覧をログ表示
    for ev in events:
        print(f"  → {ev['type']:5s}  {ev['time'].strftime('%H:%M')}  {ev['height_cm']}cm")

    # 全レース（1〜12）のステータスを計算
    race_tides = {}
    for race_no in range(1, 13):
        race_time = DEFAULT_RACE_TIMES.get(race_no, "12:00")
        info = tide_status_at(events, race_time)
        race_tides[str(race_no)] = {
            "race_time":  race_time,
            "status":     info["status"],
            "label_jp":   info["label_jp"],
            "height_pct": info["height_pct"],
            "next_event": info.get("next_event", {}),
        }
        label = info["label_jp"]
        pct   = info["height_pct"]
        note  = info.get("next_event", {}).get("note", "")
        print(f"  R{race_no:2d} ({race_time})  {label}  潮位{pct}%  {note}")

    result = {
        "venue_code":  jcd,
        "jma_station": stn,
        "date":        date_str,
        "fetched_at":  datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tide_events": [
            {
                "type":       e["type"],
                "time":       e["time"].strftime("%H:%M"),
                "height_cm":  e["height_cm"],
            }
            for e in events
        ],
        "race_tides": race_tides,
    }

    save_dir = DATA_DIR / "tides" / date_str
    save_dir.mkdir(parents=True, exist_ok=True)
    out_path = save_dir / f"{jcd}_tide.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 潮汐データ保存: {out_path}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="気象庁から潮汐データを取得")
    parser.add_argument("--jcd",  default="22", help="会場コード (デフォルト: 22=福岡)")
    parser.add_argument("--date", default=datetime.date.today().strftime("%Y%m%d"),
                        help="開催日 YYYYMMDD (デフォルト: 今日)")
    parser.add_argument("--all",  action="store_true",
                        help="全潮汐会場を一括取得")
    args = parser.parse_args()

    if args.all:
        tidal_venues = [jcd for jcd, stn in VENUE_TO_JMA_STN.items() if stn]
        print(f"[INFO] 対象会場: {tidal_venues}")
        for jcd in tidal_venues:
            fetch_and_save_tide(jcd, args.date)
            time.sleep(2)
    else:
        fetch_and_save_tide(args.jcd, args.date)
