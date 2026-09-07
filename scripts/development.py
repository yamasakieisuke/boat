#!/usr/bin/env python3
"""展開予想モデル。「誰が勝つか」ではなく「どう勝つか」を3連単の並びに反映する。

## 何をするか

合計ポイント順に3連単を組むと、同じ1着予想でも中身の違いが表現できない。
3コースが勝つとして、**まくりで勝つのか まくり差しで勝つのか**で
1コースの艇がどこに残るかが決定的に変わる:

    3コース勝ち  まくり     → 1コースが2着 23.4%   → 3-x-1 や 3-x-x
    3コース勝ち  まくり差し  → 1コースが2着 63.5%   → 3-1-x

2コースはもっと極端:

    2コース勝ち  差し   → 1コースが2着 61.7%
    2コース勝ち  まくり → 1コースが2着 11.2% / 4着以下 72.0%

物理的にも筋が通る。まくりは外から全部まとめて連れて行くので1コースは引き波で
飛ばされる。まくり差しは2コースの外を回って1コースの内に差し込むので、
1コースは減速するが残る。

そして「まくり型か まくり差し型か」は選手の個人特性として実在する
（時系列の前半→後半で r=+0.519。build_technique_stats.py の docstring 参照）。

## 効かせ方

既存の会場別出目統計（combo_stats）を**置き換えない**。あちらは会場ごとの
実測分布で、展開モデルより広い情報を持っている。ここで実測したのは
「1コースの艇がどこに残るか」だけなので、**そこだけ動かして残りを再正規化する**。

    平均的な選手 → 既存の挙動と完全に一致（副作用ゼロ）
    まくり型の選手 → 1コースを2着から落とし、他艇に配り直す
    まくり差し型   → 1コースを2着に上げ、他艇から取る

「測っていないことは動かさない」ため、この形にしてある。

## どこまで効くか（時系列 walk-forward。2026-04-01 以前で学習、以降で評価）

評価9,518レース。比較対象は「コース別の周辺分布のみ＝展開を見ない現行相当」。

    勝ちコース      n     周辺Brier   展開Brier     改善   下げ群→上げ群の実測差
    2コース     2,980    0.24668    0.24662  +0.00006   43.0% → 45.1%  (+2.1pt)
    3コース     2,897    0.24271    0.23964  +0.00306   36.0% → 45.6%  (+9.6pt)
    4コース     2,278    0.21964    0.21896  +0.00067   30.7% → 34.0%  (+3.3pt)
    5コース     1,363    0.23651    0.23628  +0.00023   36.3% → 39.7%  (+3.4pt)
    全体        9,518    0.23754    0.23640  +0.00115   37.2% → 41.8%  (+4.6pt)

**仕事をしているのは実質3コースだけ**。全体の +4.6pt は標準誤差1.0pt に対して
約4.6σ なのでノイズではないが、控えめな効果だと理解しておくこと。

3コースが効く理由は筋が通っている。まくり/まくり差しの二択が最も綺麗に割れ、
着順への効きも最大（1号艇2着 23.4% vs 63.5% = 40pt差）。
2コースは着順への効きがもっと大きい（61.7% vs 11.2%）のに効かない。
選手特性としての安定性が弱く（r=+0.35 対 外コースの+0.52）、かつ全体差し率が
0.675 に偏っているため、縮約後にほとんど動かなくなるから。

2・4・5コースも害は無い（改善は小さいが全て正）ので残してあるが、
**この表が「効いている」の根拠なので、次に見直すときはここを測り直すこと**。

## 【重要】買い目の精度は上がらなかった（2026-09-07）

集計としての効果は本物だが、**個々のレースの買い目を良くする識別力は無い**。
8月の 1,092レースで測った結果:

    指標                    本番     tenkai   不一致
    2連単的中(1着-2着)      63.1%    63.2%    5 対 6
    条件付き2着的中          36.5%    36.2%    7 対 4
    2着の選択が変わった13件    7的中     4的中

重み(TENKAI_WEIGHT)を 0.10→0.20 に上げて変化量を4倍にしても動かなかった。
2コースを対象から外しても動かなかった。**これ以上の係数調整はしない**
（同じデータで選び続けると過学習になる）。

理由は3つあると考えている:
  1. 縮約後はほとんどの選手が平均近くに寄り、倍率が1.0付近になる
  2. 2着の選択はコース構造に支配される
     （以前の検証で「常に2号艇」34.1% が ST ベースの規則より強かった）
  3. 決まり手はその艇が勝った場合の条件付きで、勝つかどうかの不確実性が大きい

**結論: シャドーのまま置く。本番には入れない。** 毎晩のシャドー実行からも外した
（頭別2着の変化率が1.7%しかなく、1年回しても有意差が出ないため CI 時間の無駄）。
`--shadow tenkai` で手動実行はできる。

比較のため: 壁（wall）は 2,136レースで非定番的中 p=0.027 と差が出ている。

## 使い方

    dev = DevelopmentModel.load()
    if dev:
        p2, p3 = dev.c1_placement(first_waku=3, reg_no="4444")
        adj = dev.adjust_cond2(3, raw_cond2_by_waku)   # {waku: 確率} を作り直す
"""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATS_PATH = BASE_DIR / "data" / "stats" / "racer_technique.json"

# 決まり手の混合をどのコースまで信じるか。
#
# 6コース: まくり33.8% / まくり差し38.7% とほぼ差が無く（n=456/664）動かす根拠が無い。
#
# 2コース: **外した**。着順への効きは最大（1号艇2着 差し61.7% vs まくり11.2%）だが、
#   選手特性としての安定性が最も弱い（r=+0.35。外コースは+0.52）。しかも全体差し率が
#   0.675 に偏っているので縮約後はほとんど動かない。
#   walk-forward の Brier 改善も +0.00006 とゼロに等しかった（3コースは +0.00306）。
#   **信頼できない推定に大きな倍率を掛ける**組み合わせで、ノイズを増幅するだけ。
TARGET_COURSES = (3, 4, 5)

# 展開モデルが1コースの着順確率を動かせる幅の上限（絶対値）。
# 縮約済みの選手傾向でも、極端な選手×効果の大きいコースだと
# ±0.25 くらい動く。それ以上は元の分布を壊すので頭を押さえる。
MAX_SHIFT = 0.25

# 2着分布に掛ける倍率の上限。縮約済みでも極端な選手×効果の大きいコースだと
# 1.6倍ほどになる。それ以上は会場別の実測分布を壊すので頭を押さえる。
MAX_RATIO = 1.8


class DevelopmentModel:
    def __init__(self, stats: dict):
        self.meta = stats.get("meta") or {}
        self.marginal = stats.get("marginal") or {}
        self.second_dist = stats.get("second_dist") or {}
        self.second_marginal = stats.get("second_marginal") or {}
        self.payload = stats.get("payload") or {}
        self.racers = stats.get("racers") or {}
        self.base_makuri = float(self.meta.get("base_makuri_outer") or 0.4963)
        self.base_sashi = float(self.meta.get("base_sashi_c2") or 0.6754)

    @classmethod
    def load(cls, path: Path | None = None) -> "DevelopmentModel | None":
        p = path or STATS_PATH
        try:
            stats = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not stats.get("payload") or not stats.get("marginal"):
            return None
        return cls(stats)

    # ── 決まり手の混合 ────────────────────────────────────────
    def _tech_mix(self, course: int, reg_no: str) -> tuple[dict, dict]:
        """(その選手の決まり手分布, 全体平均の決まり手分布) を返す。

        2コースは 差し/まくり、3コース以遠は まくり/まくり差し の2択で見る。
        抜き・恵まれは選手特性として扱わない（起きるかどうかが他艇次第）。
        """
        e = self.racers.get(str(reg_no)) or {}
        if course == 2:
            r = e.get("sashi_rate")
            r = self.base_sashi if r is None else float(r)
            return ({"差し": r, "まくり": 1.0 - r},
                    {"差し": self.base_sashi, "まくり": 1.0 - self.base_sashi})
        r = e.get("makuri_rate")
        r = self.base_makuri if r is None else float(r)
        return ({"まくり": r, "まくり差し": 1.0 - r},
                {"まくり": self.base_makuri, "まくり差し": 1.0 - self.base_makuri})

    def c1_placement(self, first_waku: int, reg_no: str) -> tuple[float, float] | None:
        """1着が first_waku のとき、1コース(=1号艇)が2着/3着に入る確率。

        戻り値 None は「この展開モデルでは動かさない」の意味。
        """
        if first_waku not in TARGET_COURSES:
            return None
        marg = self.marginal.get(str(first_waku))
        if not marg:
            return None

        mine, avg = self._tech_mix(first_waku, reg_no)
        acc2 = acc3 = 0.0
        avg2 = avg3 = 0.0
        for tech, p in mine.items():
            row = self.payload.get(f"{first_waku}|{tech}")
            if not row:
                return None      # 片方でも欠けたら混合が歪むので降りる
            acc2 += p * row["c1_2nd"]
            acc3 += p * row["c1_3rd"]
            avg2 += avg[tech] * row["c1_2nd"]
            avg3 += avg[tech] * row["c1_3rd"]

        # 平均的な選手なら周辺分布そのまま＝既存挙動と一致する
        d2 = max(-MAX_SHIFT, min(MAX_SHIFT, acc2 - avg2))
        d3 = max(-MAX_SHIFT, min(MAX_SHIFT, acc3 - avg3))
        p2 = min(0.95, max(0.01, marg["c1_2nd"] + d2))
        p3 = min(0.95, max(0.01, marg["c1_3rd"] + d3))
        return (p2, p3)

    # ── 条件付き確率の作り直し ─────────────────────────────────
    def second_ratio(self, first_waku: int, reg_no: str) -> dict[int, float] | None:
        """2着コースごとの「平均的な選手と比べた倍率」。

        1コース艇の位置だけ動かす方式では、
        「4コースがまくったとき2着=5が34.4%（周辺23.8%）に跳ねる」
        構造を表現できなかった。まくりは外へ大きく張るので勝った艇のすぐ外が
        付いてくる（3まくり→4,5 / 4まくり→5,6 / 5まくり→6）。
        まくり差しは内を通すので1コースが残る。

        平均的な選手なら全て 1.0 を返す＝既存挙動と一致する。
        """
        if first_waku not in TARGET_COURSES:
            return None
        marg = self.second_marginal.get(str(first_waku))
        if not marg:
            return None
        mine, avg = self._tech_mix(first_waku, reg_no)
        rows = {t: self.second_dist.get(f"{first_waku}|{t}") for t in mine}
        if any(r is None for r in rows.values()):
            return None
        out: dict[int, float] = {}
        for c in range(1, 7):
            k = str(c)
            m = marg.get(k, 0.0)
            if m < 0.01:      # 母数が薄いところは動かさない
                continue
            mine_p = sum(mine[t] * rows[t].get(k, 0.0) for t in mine)
            avg_p = sum(avg[t] * rows[t].get(k, 0.0) for t in avg)
            if avg_p < 1e-6:
                continue
            r = mine_p / avg_p
            out[c] = max(1.0 / MAX_RATIO, min(MAX_RATIO, r))
        return out or None

    def adjust_cond2(self, first_waku: int, reg_no: str,
                     raw: dict[int, float]) -> dict[int, float]:
        """{2着候補枠: 確率} を展開ぶん作り直す。

        会場別の実測分布に倍率を掛けて再正規化する。会場ごとの癖は残しつつ、
        その選手の決まり手傾向ぶんだけ形を変える。
        """
        ratio = self.second_ratio(first_waku, reg_no)
        if not ratio:
            return raw
        total = sum(raw.values())
        if total <= 0:
            return raw
        adj = {w: v * ratio.get(w, 1.0) for w, v in raw.items()}
        t2 = sum(adj.values())
        if t2 <= 0:
            return raw
        scale = total / t2          # 元の合計を保つ（cond2 は加点として使われる）
        return {w: v * scale for w, v in adj.items()}

    @staticmethod
    def _reweight(dist: dict[int, float], target_waku: int, target_p: float) -> dict[int, float]:
        """dist の target_waku だけ target_p に固定し、残りを比例配分し直す。"""
        if target_waku not in dist:
            return dist
        total = sum(dist.values())
        if total <= 0:
            return dist
        others = total - dist[target_waku]
        if others <= 0:
            return dist
        target_abs = min(target_p * total, total * 0.95)
        scale = (total - target_abs) / others
        out = {w: v * scale for w, v in dist.items() if w != target_waku}
        out[target_waku] = target_abs
        return out

    def adjust_cond3(self, first_waku: int, second_waku: int, reg_no: str,
                     raw: dict[int, float]) -> dict[int, float]:
        """3着ぶん。(勝ち,決まり手,2着) 別の完全分布は疎すぎるので、
        1号艇が3着に来る確率だけを動かす。2着が既に1号艇なら素通し。"""
        if second_waku == 1 or 1 not in raw:
            return raw
        pl = self.c1_placement(first_waku, reg_no)
        if pl is None:
            return raw
        return self._reweight(raw, 1, pl[1])

    def describe(self, first_waku: int, reg_no: str) -> str:
        """予想の根拠として出す1行。何も動かさないときは空文字。"""
        pl = self.c1_placement(first_waku, reg_no)
        if pl is None:
            return ""
        marg = self.marginal.get(str(first_waku)) or {}
        mine, _ = self._tech_mix(first_waku, reg_no)
        label = max(mine, key=mine.get)
        d = pl[0] - float(marg.get("c1_2nd", pl[0]))
        if abs(d) < 0.02:
            return ""
        arrow = "残りやすい" if d > 0 else "飛びやすい"
        return (f"{first_waku}号艇は{label}型({mine[label]*100:.0f}%)→"
                f"1号艇が2着に{arrow} {pl[0]*100:.0f}%"
                f"(平均{marg.get('c1_2nd', 0)*100:.0f}%)")


if __name__ == "__main__":
    dev = DevelopmentModel.load()
    if not dev:
        raise SystemExit("racer_technique.json が読めない。"
                         "python3 scripts/build_technique_stats.py --write")
    print(f"読み込み: {len(dev.racers):,}人 / {dev.meta.get('races'):,}レース")
    print(f"全体まくり率(外)={dev.base_makuri:.3f} 全体差し率(2C)={dev.base_sashi:.3f}\n")
    # 極端な選手を見てみる
    for key, label in (("makuri_rate", "まくり型"), ("sashi_rate", "2C差し型")):
        rows = [(r, e[key], e.get("outer_n") or e.get("c2_n"))
                for r, e in dev.racers.items() if key in e]
        rows.sort(key=lambda x: x[1])
        print(f"■ {label} の両端")
        for r, v, n in rows[:3] + rows[-3:]:
            c = 3 if key == "makuri_rate" else 2
            print(f"  {r} {key}={v:.3f} n={n:<3} → {dev.describe(c, r) or '(動かさない)'}")
        print()
