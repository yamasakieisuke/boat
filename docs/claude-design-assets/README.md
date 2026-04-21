# boat × Claude Design 投入素材

Claude Design（https://claude.ai/design）でboatブランドのデザインシステムを登録する際に投入する素材を集約する。

## ディレクトリ構成

```
docs/claude-design-assets/
├── README.md                    ← このファイル（投入手順）
├── product-description.md       ← Claude Designに貼り付ける製品概要
├── brand/
│   └── brand-guide.md           ← トンマナ言語化（未記入 → 実サイトから抽出後に埋める）
├── logo/
│   └── boat-favicon.svg         ← ロゴ登録用
└── screenshots/
    ├── forecast-sample.png      ← 予想ページスクショ
    └── archive-sample.png       ← アーカイブページスクショ
```

## Claude Design への登録手順

### 前提
- Claude **Pro / Max / Team / Enterprise** 契約
- `claude.ai/design` にアクセスできる

### 手順

1. `claude.ai/design` → サイドバー **+ New design system** → 名前「**boat**」
2. Brand assets に以下を投入：

| 項目 | 値 |
|---|---|
| Website URL | `https://ask11.jp/web/boat/` |
| Logo | `logo/boat-favicon.svg` をドラッグ&ドロップ |
| Screenshots | `screenshots/` 配下のPNGを全てドラッグ&ドロップ |
| Documents | `product-description.md` の内容をコピペ |

3. 自動抽出結果を確認（色・フォント・レイアウト）
4. 誤抽出は Tweaks スライダー or インラインコメントで調整
5. `brand/brand-guide.md` に抽出結果を転記（再現性のため）
6. **Published トグル ON** → 以降「boat」指定プロジェクトに自動適用

## スクショ追加方針

- 新規ページを作ったら `screenshots/` に PNG を追加
- ファイル名は `<ページ名>-<用途>.png`（例: `results-pc.png`, `results-mobile.png`）
- PC/モバイル両方あると Claude の抽出精度が上がる

## 注意

- Claude Design は private GitHub を直接参照しない → **手動アップロード必須**
- 本ディレクトリのファイルは Git 管理する（他Mac・他契約でも再現）
- センシティブ情報（個人情報・顧客データ等）は投入しない（boat は予想データのみなので問題なし）
- 仕様は研究プレビュー版（2026-04-17 リリース）。変更があれば本READMEを更新
