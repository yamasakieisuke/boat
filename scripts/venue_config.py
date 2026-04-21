from __future__ import annotations

"""
venue_config.py  ── 会場ごとの能力・特性マップ

各会場のスクレイピング対応状況・潮汐・ナイター・地域特性などを一元管理。
predictor.py / scraper.py / run_pending.py から import して使用する。
"""

# ── 会場設定マスタ ────────────────────────────────────────────────
# キー: 会場コード（2桁文字列）
# has_comments   : 選手コメントの取得に対応しているか
# jma_station    : 気象庁潮汐観測局コード（None=潮汐非対応）
# is_night       : ナイター開催か（主）
# is_morning     : モーニング開催か（主）
# region         : 地域（気象・水面傾向の参考）
# tidal_influence: 潮汐影響度 "high"/"medium"/"low"/None
# water_type     : "sea"（海） / "lake"（湖・ダム） / "river"（河川）
# course_notes   : コースの特徴メモ

VENUE_CONFIG: dict[str, dict] = {
    "01": {
        "name": "桐生", "region": "関東",
        "has_comments": False, "jma_station": None,
        "is_night": False, "is_morning": False,
        "tidal_influence": None, "water_type": "lake",
        "course_notes": "内陸ダム湖。強風・横風が多く荒れやすい。1コース勝率低め。",
    },
    "02": {
        "name": "戸田", "region": "関東",
        "has_comments": False, "jma_station": None,
        "is_night": False, "is_morning": False,
        "tidal_influence": None, "water_type": "lake",
        "course_notes": "内陸河川跡。コース幅が狭く1コース有利。",
    },
    "03": {
        "name": "江戸川", "region": "関東",
        "has_comments": False, "jma_station": "TK",
        "is_night": False, "is_morning": False,
        "tidal_influence": "high", "water_type": "river",
        "course_notes": "河川・潮流の影響大。荒れレースが多い。難水面で有名。",
    },
    "04": {
        "name": "平和島", "region": "関東",
        "has_comments": False, "jma_station": "TK",
        "is_night": True, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "東京湾。風の影響を受けやすい。ナイター主体。",
    },
    "05": {
        "name": "多摩川", "region": "関東",
        "has_comments": False, "jma_station": "TK",
        "is_night": False, "is_morning": True,
        "tidal_influence": "medium", "water_type": "river",
        "course_notes": "河川。流れにより差し・まくりが出やすい。モーニング開催あり。",
    },
    "06": {
        "name": "浜名湖", "region": "東海",
        "has_comments": False, "jma_station": "ZU",
        "is_night": False, "is_morning": False,
        "tidal_influence": "medium", "water_type": "lake",
        "course_notes": "汽水湖。潮汐の影響あり。比較的安定した水面。",
    },
    "07": {
        "name": "蒲郡", "region": "東海",
        "has_comments": False, "jma_station": "NG",
        "is_night": True, "is_morning": False,
        "tidal_influence": "high", "water_type": "sea",
        "course_notes": "三河湾。干満差が大きく水流が速い。ナイター主体。1コース有利だが潮で変動。",
    },
    "08": {
        "name": "常滑", "region": "東海",
        "has_comments": False, "jma_station": "NG",
        "is_night": True, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "伊勢湾。ナイター主体。1コース比較的有利。",
    },
    "09": {
        "name": "津", "region": "東海",
        "has_comments": False, "jma_station": "TB",
        "is_night": True, "is_morning": False,
        "tidal_influence": "high", "water_type": "sea",
        "course_notes": "伊勢湾内。ナイター。潮の影響で差し・まくりが出やすい日あり。",
    },
    "10": {
        "name": "三国", "region": "北陸",
        "has_comments": False, "jma_station": "XM",
        "is_night": False, "is_morning": True,
        "tidal_influence": "low", "water_type": "sea",
        "course_notes": "九頭竜川河口。モーニング開催。強風時は外差しが決まりやすい。",
    },
    "11": {
        "name": "びわこ", "region": "近畿",
        "has_comments": False, "jma_station": None,
        "is_night": False, "is_morning": False,
        "tidal_influence": None, "water_type": "lake",
        "course_notes": "内陸淡水湖。風の影響大。1コースやや不利。",
    },
    "12": {
        "name": "住之江", "region": "近畿",
        "has_comments": False, "jma_station": "OS",
        "is_night": True, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "大阪湾。ナイター主体。1コース有利傾向。",
    },
    "13": {
        "name": "尼崎", "region": "近畿",
        "has_comments": False, "jma_station": "KB",
        "is_night": False, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "阪神間。1コース有利。荒れ少なめだが終盤は荒れやすい。",
    },
    "14": {
        "name": "鳴門", "region": "四国",
        "has_comments": False, "jma_station": "TA",
        "is_night": False, "is_morning": False,
        "tidal_influence": "high", "water_type": "sea",
        "course_notes": "鳴門海峡近く。潮流が強く荒れやすい。外差しが出やすい。",
    },
    "15": {
        "name": "丸亀", "region": "四国",
        "has_comments": False, "jma_station": "TA",
        "is_night": False, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "瀬戸内海。1コース有利。比較的安定。",
    },
    "16": {
        "name": "児島", "region": "中国",
        "has_comments": False, "jma_station": "UN",
        "is_night": False, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "瀬戸内海。潮汐影響あり。1コースやや有利。",
    },
    "17": {
        "name": "宮島", "region": "中国",
        "has_comments": False, "jma_station": "Q8",
        "is_night": False, "is_morning": False,
        "tidal_influence": "high", "water_type": "sea",
        "course_notes": "厳島神社近く。干満差が大きい。引き潮時は荒れやすい。",
    },
    "18": {
        "name": "徳山", "region": "中国",
        "has_comments": False, "jma_station": "QA",
        "is_night": True, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "徳山湾。ナイター主体。1コース有利。",
    },
    "19": {
        "name": "下関", "region": "中国",
        "has_comments": False, "jma_station": "DS",
        "is_night": True, "is_morning": False,
        "tidal_influence": "high", "water_type": "sea",
        "course_notes": "関門海峡近く。ナイター主体。潮流が速く差し・まくりが出やすい。1コース安定しない日あり。",
    },
    "20": {
        "name": "若松", "region": "九州",
        "has_comments": False, "jma_station": "O3",
        "is_night": True, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "洞海湾。ナイター主体。",
    },
    "21": {
        "name": "芦屋", "region": "九州",
        "has_comments": False, "jma_station": "O3",
        "is_night": False, "is_morning": True,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "響灘。モーニング開催あり。比較的1コース有利。",
    },
    "22": {
        "name": "福岡", "region": "九州",
        "has_comments": True,   # ← 現在唯一コメント取得に対応
        "jma_station": "QF",
        "is_night": False, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "博多湾。1コース有利。荒れ少なめで予想しやすい会場。",
    },
    "23": {
        "name": "唐津", "region": "九州",
        "has_comments": True, "jma_station": "KA",
        "is_night": False, "is_morning": False,
        "tidal_influence": "medium", "water_type": "sea",
        "course_notes": "唐津湾。1コース有利。比較的安定。",
    },
    "24": {
        "name": "大村", "region": "九州",
        "has_comments": False, "jma_station": "NS",
        "is_night": True, "is_morning": False,
        "tidal_influence": "low", "water_type": "lake",
        "course_notes": "大村湾（閉鎖性湾）。ナイター主体。波が少なく1コース最強クラス。",
    },
}


def get_venue_config(jcd: str) -> dict:
    """会場コードから設定を取得。未知の場合はデフォルト値を返す。"""
    return VENUE_CONFIG.get(str(jcd), {
        "name": f"venue{jcd}", "region": "不明",
        "has_comments": False, "jma_station": None,
        "is_night": False, "is_morning": False,
        "tidal_influence": None, "water_type": "sea",
        "course_notes": "",
    })


def has_comments(jcd: str) -> bool:
    """この会場でコメント取得に対応しているか"""
    return get_venue_config(jcd).get("has_comments", False)


def is_night_venue(jcd: str) -> bool:
    """主にナイター開催の会場か"""
    return get_venue_config(jcd).get("is_night", False)


def get_jma_station(jcd: str):
    """JMA潮汐観測局コードを返す（非対応はNone）"""
    return get_venue_config(jcd).get("jma_station")


def get_tidal_influence(jcd: str):
    """潮汐影響度 "high"/"medium"/"low"/None"""
    return get_venue_config(jcd).get("tidal_influence")
