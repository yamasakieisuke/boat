# boat-forecast-viewer リデザイン ハンドオフ

このフォルダは **ここで設計 → Claude Code がローカルで実装・コミット・push** する分業を前提にした指示書パックです。

## 分業モデル

| レイヤ | 担当 |
|---|---|
| デザイン探索(プロトタイプ) | デザイン担当Claude(チャット側) |
| 差分設計(このフォルダの .md) | デザイン担当Claude |
| 実コード編集 | Claude Code(ローカル) |
| git 操作 / push | Claude Code |
| 実機確認(WP画面のスクショ) | 山崎さん |
| ビジュアルレビュー → 次指示 | デザイン担当Claude |

## 進行フェーズ

| Phase | 対象 | ステータス | ファイル |
|---|---|---|---|
| 1 | 共通デザイントークン(色/タイポ/shadow/radius) | ✅ pushed | `phase-1-tokens.md` |
| 2 | 予想一覧(archive)骨格リデザイン | ✅ pushed | `phase-2-archive.md` |
| 3 | 予想詳細(single)骨格リデザイン | ✅ pushed | `phase-3-single.md` |
| 4 | レビュー(review)骨格リデザイン | 📝 下書き | `phase-4-review.md` |
| 5 | archive 整列(カード並び/日付ヘッダ) | 📝 追補 | `phase-5-archive-align.md` |
| 6 | レビュー(review)詳細 | 📝 追補 | `phase-6-review.md` |
| 7 | レースカード(.bfv-card)密度整理 | 📝 追補 | `phase-7-race-card.md` |
| 8 | 12R早見表リデザイン | 📝 追補 | `phase-8-summary-table.md` |
| 9 | 予算/展示/コメント実データ表の統一 | 📝 追補 | `phase-9-budget-detail.md` |
| 10 | 詳細ページ ヒーロー・サイド情報磨き込み | 📝 追補 | `phase-10-hero-nav.md` |

### 進行順おすすめ
Phase 4 → 6(レビュー画面まとめ) → 7 → 8 → 9 → 10(詳細の中身を段階的に)
1 Phaseずつ Claude Code に流し、push 後に実機スクショをチャットへ戻してください。

## 原則

1. **既存の `bfv-*` / `bfva-*` / `bfrv-*` クラス名は原則維持** — JSの互換とgit差分の追跡性のため
2. **色・radius・shadow・font はトークン参照**(`var(--bfv-*)`)を優先
3. **1 Phase = 1 PR 単位**
4. HTML構造の大改造は一気にやらず、CSSで詰められるところはCSSで

## ハンドオフ .md の共通フォーマット

- **対象**: 変更するファイルと関数/行番号
- **変更方針**: デザイン意図(3〜5行)
- **具体変更**: before/after コードブロック、または差分手順
- **検証手順**: 実機で見るべき画面と確認項目
- **コミットメッセージ**: 提案文

## デザインの元ネタ

チャット側のプロジェクトに `boat-redesign.html` が存在し、4画面(会場一覧/予想詳細/アーカイブ/レビュー)の hi-fi プロトタイプが入っています。Phase ごとに、このプロトで確立したスタイルを段階的に実装へ反映していきます。
