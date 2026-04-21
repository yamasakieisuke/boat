#!/usr/bin/env python3
"""
選手マスターデータベース構築スクリプト

2つのサイトから選手データを収集して master.json を生成する：
1. br-racers.jp   → 全1,623名の基本情報（名前・登録番号・級別・支部・勝率など）
2. ladies-info.jp → 女性選手全員の登録番号（性別判定に使用）

出力:
  data/players/master.json          全選手マスター
  data/players/female_players.json  女性選手リスト（更新）

Usage:
  python3 scripts/build_player_master.py                  # 両サイト取得
  python3 scripts/build_player_master.py --br-only        # br-racers.jpのみ
  python3 scripts/build_player_master.py --ladies-only    # ladies-info.jpのみ
  python3 scripts/build_player_master.py --merge-only     # 既存CSVをマージのみ
"""

import argparse
import json
import pathlib
import re
import time
import sys

import requests
from bs4 import BeautifulSoup

DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
MASTER_PATH = DATA_DIR / "players" / "master.json"
FEMALE_PATH = DATA_DIR / "players" / "female_players.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ──────────────────────────────────────────
# br-racers.jp スクレイピング
# ──────────────────────────────────────────

def scrape_br_racers() -> dict:
    """br-racers.jp から全選手の基本情報を取得する。"""
    print("=" * 50)
    print("[br-racers.jp] 全選手取得開始")
    base_url = "https://br-racers.jp/"
    players = {}

    # 総ページ数を確認
    r = requests.get(base_url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    last_page_link = soup.select_one('a[href*="page=17"], a[href*="page=16"], a[href*="page=18"]')
    # ページネーションから最大ページ取得
    page_links = soup.select('a[href*="?page="]')
    page_nums = []
    for link in page_links:
        m = re.search(r'\?page=(\d+)', link.get('href', ''))
        if m:
            page_nums.append(int(m.group(1)))
    max_page = max(page_nums) if page_nums else 17
    print(f"  総ページ数: {max_page}")

    for page in range(1, max_page + 1):
        url = base_url if page == 1 else f"{base_url}?page={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.select(".c-result-item")
            for item in items:
                # 登録番号
                reg_el = item.select_one(".registration-number-cell")
                if not reg_el:
                    continue
                reg_no = reg_el.text.strip()

                # 氏名
                kana_parts = [el.text.strip() for el in item.select(".name-item-kana")]
                main_parts = [el.text.strip() for el in item.select(".name-item-main")]
                name_kana = " ".join(kana_parts)
                name_kanji = " ".join(main_parts)

                # 級別
                rank_el = item.select_one(".rank[data-value]")
                grade_raw = rank_el["data-value"].upper() if rank_el else ""
                grade = grade_raw.replace("A1", "A1").replace("A2", "A2").replace("B1", "B1").replace("B2", "B2")

                # 支部・出身
                branch_el = item.select_one(".branch-name")
                pref_el = item.select_one(".prefecture-name")
                branch = branch_el.text.strip().replace("支部", "") if branch_el else ""
                prefecture = pref_el.text.strip() if pref_el else ""

                # 成績
                stats = {}
                labels = item.select(".info-item-label")
                values = item.select(".info-item-value")
                for label, value in zip(labels, values):
                    k = label.text.strip()
                    v = value.text.strip()
                    if k == "勝率":
                        stats["win_rate"] = float(v) if v else None
                    elif k == "優勝回数":
                        m2 = re.search(r"\d+", v)
                        stats["championship_count"] = int(m2.group()) if m2 else 0
                    elif k == "能力指数":
                        stats["ability_index"] = int(v) if v.isdigit() else None

                players[reg_no] = {
                    "reg_no": reg_no,
                    "name_kanji": name_kanji,
                    "name_kana": name_kana,
                    "grade": grade,
                    "branch": branch,
                    "prefecture": prefecture,
                    **stats,
                }

            print(f"  page {page:02d}/{max_page}: {len(items)}件取得 (累計 {len(players)}名)")
            time.sleep(0.5)

        except Exception as e:
            print(f"  [ERROR] page {page}: {e}")
            time.sleep(2)

    print(f"[br-racers.jp] 完了: {len(players)}名")
    return players


# ──────────────────────────────────────────
# ladies-info.jp スクレイピング
# ──────────────────────────────────────────

def scrape_ladies_info() -> dict:
    """
    ladies-info.jp から女性選手全員の登録番号を取得する。
    WordPressのページネーションを順次クリックしていく。
    Returns: {reg_no: {name_kanji, name_kana, branch, prefecture}}
    """
    print("=" * 50)
    print("[ladies-info.jp] 女性選手取得開始")

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=" + HEADERS["User-Agent"])

    all_ladies = {}

    try:
        driver = webdriver.Chrome(options=options)
        driver.get("https://www.ladies-info.jp/list/")
        time.sleep(3)

        page_num = 1
        while True:
            # 現ページの選手を取得
            items = driver.find_elements(By.CSS_SELECTOR, 'li[data-template="racer"]')
            page_count = 0
            for item in items:
                try:
                    reg_no = item.find_element(By.CSS_SELECTOR, ".number").text.strip()
                    name_el = item.find_element(By.CSS_SELECTOR, ".name")
                    yomi_el = item.find_element(By.CSS_SELECTOR, ".yomi")
                    pref_el = item.find_element(By.CSS_SELECTOR, ".pref")
                    branch_el = item.find_element(By.CSS_SELECTOR, ".shibu")

                    name = re.sub(r"\s+", " ", name_el.text.strip())
                    yomi = re.sub(r"\s+", " ", yomi_el.text.strip())
                    pref = pref_el.text.strip().replace("出身", "").strip()
                    branch = branch_el.text.strip().replace("支部", "").strip()

                    all_ladies[reg_no] = {
                        "reg_no": reg_no,
                        "name_kanji": name,
                        "name_kana": yomi,
                        "prefecture": pref,
                        "branch": branch,
                        "gender": "F",
                    }
                    page_count += 1
                except Exception:
                    pass

            print(f"  page {page_num:03d}: {page_count}件取得 (累計 {len(all_ladies)}名)")

            # 次ページへ
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a.nextpostslink")
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(2)
                page_num += 1
            except Exception:
                print("  次ページなし → 完了")
                break

        driver.quit()

    except ImportError:
        print("  [WARNING] seleniumが未インストール。requests+BeautifulSoupでフォールバック")
        all_ladies = _scrape_ladies_info_requests()

    print(f"[ladies-info.jp] 完了: {len(all_ladies)}名の女性選手")
    return all_ladies


def _scrape_ladies_info_requests() -> dict:
    """
    selenium不使用の場合のフォールバック。
    WordPressのREST APIを試みる。
    """
    all_ladies = {}
    base = "https://www.ladies-info.jp"

    # WordPressのREST API
    for per_page in [100]:
        for page in range(1, 30):
            url = f"{base}/wp/wp-json/wp/v2/racers?per_page={per_page}&page={page}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code == 400:
                    break
                if r.status_code != 200:
                    break
                data = r.json()
                if not data:
                    break
                for item in data:
                    reg_no = str(item.get("slug", "")).strip()
                    if not reg_no.isdigit():
                        # タイトルから登録番号を抽出
                        title = item.get("title", {}).get("rendered", "")
                        m = re.search(r"(\d{4})", title)
                        reg_no = m.group(1) if m else ""
                    if reg_no:
                        all_ladies[reg_no] = {
                            "reg_no": reg_no,
                            "name_kanji": BeautifulSoup(
                                item.get("title", {}).get("rendered", ""), "html.parser"
                            ).get_text(),
                            "gender": "F",
                        }
                print(f"  REST API page {page}: {len(data)}件")
                if len(data) < per_page:
                    break
                time.sleep(0.5)
            except Exception as e:
                print(f"  REST API失敗: {e}")
                break

    if not all_ladies:
        print("  [WARNING] REST API取得失敗。Chromeブラウザ経由でのみ取得可能")

    return all_ladies


# ──────────────────────────────────────────
# マスターJSON生成・更新
# ──────────────────────────────────────────

def load_master() -> dict:
    if MASTER_PATH.exists():
        return json.loads(MASTER_PATH.read_text())
    return {}


def save_master(master: dict) -> None:
    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTER_PATH.write_text(json.dumps(master, ensure_ascii=False, indent=2))
    print(f"[OK] master.json 保存: {len(master)}名 → {MASTER_PATH}")


def update_female_players(ladies: dict) -> None:
    """ladies-info.jpのデータでfemale_players.jsonを更新する。"""
    fp = {}
    if FEMALE_PATH.exists():
        fp = json.loads(FEMALE_PATH.read_text())

    existing_regs = set(int(x) for x in fp.get("reg_nos", []))
    existing_names = fp.get("names", {})

    added = 0
    for reg_no, info in ladies.items():
        try:
            reg_int = int(reg_no)
        except ValueError:
            continue
        if reg_int not in existing_regs:
            existing_regs.add(reg_int)
            added += 1
        existing_names[reg_no] = info.get("name_kanji", "")

    fp["reg_nos"] = sorted(existing_regs)
    fp["names"] = existing_names
    fp["_count"] = len(fp["reg_nos"])
    fp["_updated"] = __import__("datetime").date.today().isoformat()
    fp["_source"] = "ladies-info.jp + manual"

    FEMALE_PATH.write_text(json.dumps(fp, ensure_ascii=False, indent=2))
    print(f"[OK] female_players.json 更新: {fp['_count']}名 (新規追加 {added}名)")


def merge_and_save(br_players: dict, ladies: dict) -> dict:
    """br-racers.jpデータ + ladies-info.jpデータをマージしてmaster.jsonを作成。"""
    master = load_master()

    # br-racers.jpデータを反映
    for reg_no, info in br_players.items():
        if reg_no not in master:
            master[reg_no] = {}
        master[reg_no].update(info)

    # ladies-info.jpデータを反映（名前・よみ・性別）
    for reg_no, info in ladies.items():
        if reg_no not in master:
            master[reg_no] = {}
        master[reg_no].update(info)
        master[reg_no]["gender"] = "F"

    # 性別未設定の選手はMとする
    for reg_no in master:
        if "gender" not in master[reg_no]:
            master[reg_no]["gender"] = "M"

    # 統計表示
    f_count = sum(1 for v in master.values() if v.get("gender") == "F")
    m_count = sum(1 for v in master.values() if v.get("gender") == "M")
    print(f"\n📊 マスター統計: 合計 {len(master)}名 (女性 {f_count}名 / 男性 {m_count}名)")

    save_master(master)
    return master


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="選手マスターDB構築")
    parser.add_argument("--br-only", action="store_true", help="br-racers.jpのみ取得")
    parser.add_argument("--ladies-only", action="store_true", help="ladies-info.jpのみ取得")
    parser.add_argument("--merge-only", action="store_true", help="既存データのマージのみ")
    args = parser.parse_args()

    br_players = {}
    ladies = {}

    if args.merge_only:
        master = load_master()
        print(f"既存master.json: {len(master)}名")
        return

    if not args.ladies_only:
        br_players = scrape_br_racers()

    if not args.br_only:
        ladies = scrape_ladies_info()

    # マージして保存
    merge_and_save(br_players, ladies)
    update_female_players(ladies)

    print("\n✅ 完了")


if __name__ == "__main__":
    main()
