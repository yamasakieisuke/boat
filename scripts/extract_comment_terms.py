#!/usr/bin/env python3
"""
コメント本文から判定に使えそうな用語候補を抽出する。

- Janome が入っていれば形態素解析を併用
- 未導入でも句読点分割 + n-gram で候補を抽出
- 既存 COMMENT_KEYWORDS で文脈極性を粗く付ける
- output/data/comment_term_candidates.{json,md} を出力
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output" / "data"
sys.path.insert(0, str(Path(__file__).parent))
from predictor import COMMENT_KEYWORDS, match_comment_keywords  # noqa: E402

COMMENT_JSON_GLOB = [
    DATA_DIR / "comments",
    DATA_DIR / "player_comments",
]

TARGET_PATTERNS = (
    "出足", "行き足", "回り足", "まわり足", "ターン回り", "レース足",
    "直線", "スリット", "押し感", "バランス", "回転", "エンジン", "ペラ",
    "乗り心地", "ゾーン", "パンチ", "下がって", "下がる", "出ていない", "出ていく",
    "甘い", "重い", "弱い", "余裕がある", "問題ない", "申し分ない",
    "しっかりしている", "力強さ", "良くなった", "よさそう", "良さそう",
    "乗りづら", "普通に", "回っていない", "しのげ", "直らない", "治らない",
    "ずれて", "反省", "突破", "伴っていない",
)

STOP_PHRASES = {
    "と思う", "でした", "ですね", "かな", "けど", "けれど", "ですが", "くらい",
    "みたい", "感じ", "こと", "あと", "ただ", "それだけ", "自分", "選手",
    "前半", "後半", "準優", "予選", "本番", "試運転", "メンバー", "節一",
}

IGNORE_CLAUSES = {
    "またペラを叩き変えてみます",
    "マイナスにしてバランスを取って行った",
}

ADJUSTMENT_ONLY_PATTERNS = (
    "ペラを叩", "ペラ調整", "調整して", "調整をして", "調整していく",
    "取り付けの調整", "回転を上げる調整", "抑えていった", "また違う形で調整",
    "回す調整", "ベースにペラ調整",
)

JP_CHARS = re.compile(r"[ぁ-んァ-ン一-龥A-Za-z0-9]+")
CLAUSE_SPLIT = re.compile(r"[。！？!\?／/\n]+")
LEADING_BAD_CHARS = set("がをにではともやのはへし")
TRAILING_BAD_CHARS = set("がをにではともやのはへし")


def load_texts() -> list[str]:
    texts: list[str] = []

    for root in COMMENT_JSON_GLOB:
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if root.name == "comments":
                for item in (payload.get("comments") or {}).values():
                    txt = item.get("comment_today") or item.get("comment_prev") or ""
                    if txt:
                        texts.append(txt)
            elif root.name == "player_comments":
                if isinstance(payload, list):
                    for row in payload:
                        txt = row.get("comment", "")
                        if txt:
                            texts.append(txt)
                elif isinstance(payload, dict):
                    for item in (payload.get("comments") or {}).values():
                        txt = item.get("comment", "")
                        if txt:
                            texts.append(txt)
    return texts


def clause_score(text: str) -> float:
    return round(sum(item["delta"] for item in match_comment_keywords(text)), 4)


def normalize_clause(text: str) -> str:
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace("　", "").strip(" 、,")
    return text


def is_adjustment_only_clause(clause: str) -> bool:
    """
    調整作業そのものの描写は評価対象外にする。
    ただし、既存辞書の評価語が同居している場合は除外しない。
    """
    if not any(p in clause for p in ADJUSTMENT_ONLY_PATTERNS):
        return False
    return not bool(match_comment_keywords(clause))


def tokenize_with_janome(text: str) -> list[str]:
    if importlib.util.find_spec("janome") is None:
        return []
    from janome.tokenizer import Tokenizer  # type: ignore

    tokenizer = Tokenizer()
    tokens = []
    for token in tokenizer.tokenize(text):
        surface = token.surface.strip()
        base = token.base_form if token.base_form != "*" else surface
        pos = token.part_of_speech.split(",")[0]
        if pos in {"名詞", "動詞", "形容詞", "副詞"} and len(base) >= 2:
            tokens.append(base)
    return tokens


def extract_candidates_from_clause(text: str) -> list[str]:
    candidates: set[str] = set()
    norm = normalize_clause(text)
    if not norm:
        return []

    janome_tokens = tokenize_with_janome(norm)
    for token in janome_tokens:
        if any(p in token for p in TARGET_PATTERNS) and token not in STOP_PHRASES:
            candidates.add(token)

    chunks = JP_CHARS.findall(norm)
    for chunk in chunks:
        if len(chunk) < 2:
            continue
        for size in range(4, min(13, len(chunk) + 1)):
            for i in range(0, len(chunk) - size + 1):
                gram = chunk[i:i + size]
                if gram in COMMENT_KEYWORDS or gram in STOP_PHRASES:
                    continue
                if any(stop in gram for stop in STOP_PHRASES):
                    continue
                if not any(p in gram for p in TARGET_PATTERNS):
                    continue
                if gram[0] in "ぁぃぅぇぉゃゅょっん" or gram[-1] in "ぁぃぅぇぉゃゅょっん":
                    continue
                if gram[0] in LEADING_BAD_CHARS or gram[-1] in TRAILING_BAD_CHARS:
                    continue
                candidates.add(gram)

    return sorted(candidates)


def build_report(texts: list[str], min_count: int = 2) -> dict:
    scored_examples: dict[str, list[str]] = defaultdict(list)
    counters = {
        "positive": Counter(),
        "negative": Counter(),
        "neutral": Counter(),
    }
    unmatched_counter = Counter()
    unmatched_examples: dict[str, list[str]] = defaultdict(list)
    unmatched_clauses: list[str] = []

    for text in texts:
        for clause in CLAUSE_SPLIT.split(text):
            clause = normalize_clause(clause)
            if not clause:
                continue
            if clause in IGNORE_CLAUSES:
                continue
            if is_adjustment_only_clause(clause):
                continue
            score = clause_score(clause)
            matches = match_comment_keywords(clause)
            if score >= 0.08:
                polarity = "positive"
            elif score <= -0.08:
                polarity = "negative"
            else:
                polarity = "neutral"

            for cand in extract_candidates_from_clause(clause):
                counters[polarity][cand] += 1
                bucket = scored_examples[f"{polarity}:{cand}"]
                if clause not in bucket and len(bucket) < 3:
                    bucket.append(clause)

            if matches:
                continue
            if any(p in clause for p in TARGET_PATTERNS):
                if clause not in unmatched_clauses and len(unmatched_clauses) < 80:
                    unmatched_clauses.append(clause)
                for cand in extract_candidates_from_clause(clause):
                    unmatched_counter[cand] += 1
                    bucket = unmatched_examples[cand]
                    if clause not in bucket and len(bucket) < 3:
                        bucket.append(clause)

    report = {
        "source_comment_count": len(texts),
        "uses_janome": importlib.util.find_spec("janome") is not None,
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "candidates": {},
        "unmatched": {
            "clauses": unmatched_clauses,
            "terms": [],
        },
    }

    for polarity, counter in counters.items():
        rows = []
        for term, count in counter.most_common():
            if count < min_count:
                continue
            if term in COMMENT_KEYWORDS:
                continue
            pos = counters["positive"][term]
            neg = counters["negative"][term]
            neu = counters["neutral"][term]
            score_hint = round((pos - neg) / max(pos + neg + neu, 1), 3)
            rows.append({
                "term": term,
                "count": count,
                "positive": pos,
                "negative": neg,
                "neutral": neu,
                "score_hint": score_hint,
                "examples": scored_examples.get(f"{polarity}:{term}", []),
            })
        report["candidates"][polarity] = rows[:80]

    for term, count in unmatched_counter.most_common():
        if count < min_count:
            continue
        if term in COMMENT_KEYWORDS:
            continue
        report["unmatched"]["terms"].append({
            "term": term,
            "count": count,
            "examples": unmatched_examples.get(term, []),
        })
        if len(report["unmatched"]["terms"]) >= 80:
            break

    return report


def write_outputs(report: dict) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "comment_term_candidates.json"
    md_path = OUTPUT_DIR / "comment_term_candidates.md"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# コメント用語候補",
        "",
        f"- 対象コメント数: {report['source_comment_count']}",
        f"- 形態素解析: {'Janome使用' if report['uses_janome'] else '未使用（n-gram抽出）'}",
        f"- 生成日時: {report['generated_at']}",
        "",
    ]
    labels = {
        "positive": "ポジティブ候補",
        "negative": "ネガティブ候補",
        "neutral": "中立候補",
    }
    for key in ("positive", "negative", "neutral"):
        lines.append(f"## {labels[key]}")
        lines.append("")
        lines.append("| 用語 | 出現数 | +文脈 | -文脈 | 0文脈 | score_hint | 例 |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for row in report["candidates"].get(key, [])[:30]:
            example = " / ".join(row["examples"][:2]).replace("|", " ")
            lines.append(
                f"| {row['term']} | {row['count']} | {row['positive']} | {row['negative']} | "
                f"{row['neutral']} | {row['score_hint']:+.3f} | {example} |"
            )
        lines.append("")

    lines.append("## 未判定候補")
    lines.append("")
    lines.append("| 用語 | 出現数 | 例 |")
    lines.append("|---|---:|---|")
    for row in report["unmatched"].get("terms", [])[:40]:
        example = " / ".join(row["examples"][:2]).replace("|", " ")
        lines.append(f"| {row['term']} | {row['count']} | {example} |")
    lines.append("")

    lines.append("## 未判定コメント例")
    lines.append("")
    for clause in report["unmatched"].get("clauses", [])[:20]:
        lines.append(f"- {clause}")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="コメント用語候補抽出")
    parser.add_argument("--min-count", type=int, default=2, help="候補に残す最小出現数")
    args = parser.parse_args()

    texts = load_texts()
    report = build_report(texts, min_count=args.min_count)
    json_path, md_path = write_outputs(report)
    print(f"[INFO] comment terms: {json_path}")
    print(f"[INFO] comment terms: {md_path}")


if __name__ == "__main__":
    main()
