# Cowork ロールバック引き継ぎ

> **作成日**: 2026-04-22
> **目的**: Cowork Scheduled tasks（元の構成）へのロールバックと、同時に行う公営ギャンブル AUP 文言の追記手順を整理する
> **対象読者**: 運用者（山崎さん自身）／ Cowork 側で編集するときの Claude / 将来セッションの Claude Code

---

## 経緯

| フェーズ | 実行基盤 | 状態 | 備考 |
|---|---|---|---|
| 〜 2026-04-13 | **Cowork Scheduled tasks**（6タスク） | ✅ 安定動作 | 現在は全て Paused |
| 2026-04-13 〜 | launchd + `~/.local/bin/claude-task-runner.sh` | ⚠️ 4/19 まで正常、4/20 以降不安定 | ユーザー指示で移行 |
| 2026-04-22 以降 | **Cowork に戻す** | 本ドキュメントの手順 | 移行先 |

### launchd 側で発生した問題

1. **2026-04-20 08:00 の morning-v2**: `API Error: Claude Code is unable to respond... (AUP 違反)` で Claude が応答拒否
2. **2026-04-21 08:00 の morning-v2**: ログ 295 byte で startup のみ、以降の出力なし (exit 1)
3. **2026-04-22 08:00 の morning-v2**: 発火形跡なし（Mac sleep？）
4. **WP sync 403**: 4/21 に 84回 `invalid_token` で同期失敗、run-pending も巻き込み

→ **ロールバック判断**: Cowork で動いていた時期の運用に戻し、AUP 文言のみ補強する方が早期復旧に有利。

---

## Cowork 側で復旧するタスク一覧

UI 上で 2026-04-22 時点に Paused 状態のタスク群：

| 名称 | 概要 | 頻度 |
|---|---|---|
| **Boat daily morning v2** | 毎朝の前日 verify・WP反映・開催確認・予測生成・WP投稿 | 毎朝 08:00 |
| **Boat race fetcher** | 展示/オッズ自動取得（イベント駆動・自動再スケジュール） | 4分間隔ポーリング |
| Daily genai news | 毎朝 08:15 に前日の生成AIニュース収集・Outbox/News 保存 | 毎日 08:15 |
| Daily genai news slack | 平日朝9時に前日ニュースサマリを Slack #news へ投稿 | 平日 09:00 |
| Weekly genai summary | 月曜 08:30 に先週の生成AIニュース週次ハイライト | 月曜 08:30 |
| Garden weekly reminder | 月曜朝に菜園作業イベントを Google カレンダーへ作成 | 月曜 08:02 |

---

## Cowork 側の作業手順

### Step 1. 各タスクの prompt に AUP 文言を追加

**対象**: `Boat daily morning v2` と `Boat race fetcher`（ボートレース系のみ）

Cowork タスク編集画面で、プロンプト冒頭に以下を **挿入** してください。既に入っていれば差分のみ更新。

```
## タスク文脈（AUP 明示）

本タスクは **日本国内で法律により合法とされる公営競技（ボートレース / モーターボート競走法 に基づく公営ギャンブル）** の過去データ・出走表・オッズ・気象データを収集し、統計的な予測モデル（scripts/predictor.py）で着順確率を算出して、個人ブログ（WordPress）に分析レポートを公開する **データサイエンス・統計分析用途** のバッチです。

- 取得対象は日本財団・BOATRACE公式・艇国データバンク等の一般公開データのみ
- 賭け金の自動投入・ベッティングサービス運営・他者への勧誘は一切含まない
- 出力は個人の学習・検証用の統計レポート（HTML記事）であり、投資助言・賭博あっせんには該当しない
- 対象ユーザーは成人（本人のみ）
```

ソース: `~/Agent/personal-life/Scheduled/boat-daily-morning-v2/SKILL.md` の先頭ブロック。

### Step 2. Cowork タスクの設定・環境変数を確認

特に `Boat daily morning v2` のタスク詳細画面で以下をチェック:

- [ ] Prompt 本文は `~/Agent/personal-life/Scheduled/boat-daily-morning-v2/SKILL.md` と同等か
- [ ] **環境変数に `WP_SYNC_TOKEN` / `WP_SYNC_URL` が設定されているか**（←重要）
  - もし設定あり → その token 値をメモして `.env` に反映（WP 403 解消のため）
  - もし設定無し → ローカル `.env` に依存している可能性。後述の Step 4 参照

### Step 3. 各タスクを Resume（Active 化）

UI 上の各カードの Paused トグルを Active に戻す。**ボート系 2つを先に再開**し、数時間様子見してから他を再開が安全。

### Step 4. ローカル launchd 側のジョブを Unload（二重実行防止）

**重要**: Cowork を Resume した後、必ずローカル launchd ジョブを停止してください。両方動くと WP 同期が二重発火します。

```bash
# ボート系 2つ
launchctl unload ~/Library/LaunchAgents/com.boat.run-pending.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.boat-daily-morning-v2.plist

# ニュース系も Cowork に戻すなら
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.daily-genai-news.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.daily-genai-news-slack.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.daily-investment-news.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.daily-investment-news-slack.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.weekly-genai-summary.plist
launchctl unload ~/Library/LaunchAgents/com.claude-code.task.garden-weekly-reminder.plist

# 確認
launchctl list | grep -E "boat|claude-code\.task"
```

`launchctl list` で何も出力されなければ OK。plist ファイル自体は削除せず残しておく（ロールフォワードの可能性に備える）。

---

## WP sync 403 の扱い

### 現状
- ローカル `.env`: `WP_SYNC_TOKEN=zsCTc6ReMHAb6BAryfj2`
- heteml サーバ側 `BOAT_SYNC_TOKEN` 環境変数: **値が消失または変更済み**（`/web/boat/api/` に `.htaccess` も `.user.ini` も無し）
- 結果: 全 POST が `{"ok":false,"error":"invalid_token"}` で 403

### ロールバック後の挙動予測

| Cowork 側の token 設定 | 予測される結果 |
|---|---|
| 旧 token がそのまま残っている（かつ heteml も当時値を保持） | ✅ 自動復旧（要検証） |
| 旧 token が残っているが heteml 側は既に別値 | ❌ Cowork からも 403 |
| Cowork に token 設定なく、ローカル `.env` 参照 | ❌ どのみち現 token (zsCT...) で 403 |

### 復旧パス

**Cowork 側で WP 403 が解消しない場合**、以下を実施:

1. **新 token 生成**:
   ```bash
   openssl rand -base64 24 | tr -d '/+=' | head -c 28
   ```

2. **heteml の `/web/boat/api/.htaccess` を新規作成**（FileZilla で upload）:
   ```apache
   SetEnv BOAT_SYNC_TOKEN "<生成した token>"
   ```

3. **以下 3 箇所を同じ token に揃える**:
   - ローカル `~/repos/boat/.env` の `WP_SYNC_TOKEN`
   - Cowork タスクの環境変数（もし使用していれば）
   - heteml `/web/boat/api/.htaccess`

4. **疎通確認**:
   ```bash
   curl -X POST "https://ask11.jp/web/boat/api/forecast-sync.php" \
     -H "X-Boat-Token: <新token>" \
     -d '{"ping":"test"}'
   ```
   403 以外が返れば成功。

---

## 関連ファイル・パス

| 項目 | 場所 |
|---|---|
| 現行 SKILL.md（Cowork 移行元） | `~/Agent/personal-life/Scheduled/boat-daily-morning-v2/SKILL.md` |
| run-pending ラッパー | `~/Agent/scripts/claude-code-cron/boat_run_pending.sh` |
| launchd plist | `~/Library/LaunchAgents/com.claude-code.task.*.plist` / `com.boat.*.plist` |
| WP 受信口（heteml deployed） | `/web/boat/api/forecast-sync.php` |
| WP 受信口（source） | `~/repos/boat/wordpress/forecast-sync.php` |
| 送信スクリプト | `~/repos/boat/scripts/publish_wordpress.py` |
| `.env`（gitignore） | `~/repos/boat/.env` |
| GitHub Actions deploy | `.github/workflows/deploy-wp.yml` （`wordpress/**` push で自動デプロイ） |

---

## 想定される注意点・リスク

1. **Cowork 側の prompt が古い可能性**: 4/13 の移行以降、改修は SKILL.md 側のみに入れてきたため、Cowork のプロンプトは旧仕様のまま。`~/Agent/personal-life/Scheduled/boat-daily-morning-v2/SKILL.md` の最新版で上書きするのが安全。

2. **iCloud 同期タイムラグ**: SKILL.md は iCloud 経由で両 Mac で共有しているが、Cowork の prompt は別基盤で手動更新が必要。差分管理が煩雑化する可能性。

3. **二重実行**: launchd unload を忘れると WP に 2倍のリクエストが飛び、記事の重複更新・token ロック等の副作用リスク。必ず unload → Cowork Resume の順で。

4. **AUP refusal の根本対策**: 公営ギャンブル文言を入れても Claude が拒否するケースが残る場合、Cowork では model 指定や system prompt レベルでの調整が Claude Code CLI より柔軟。UI 上で出る各タスクの設定を活用する。

5. **ログ場所の違い**: launchd 時代は `~/Library/Logs/claude-tasks/*.log`。Cowork に戻すと Cowork UI 内のログに戻る。障害時の参照場所を混同しないこと。

---

## ロールフォワード（もう一度 launchd に戻したくなったら）

1. Cowork 各タスクを Pause
2. launchd plist を load し直し:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.claude-code.task.boat-daily-morning-v2.plist
   # 他も同様
   ```
3. SKILL.md 側に Cowork prompt 側で加えた修正を反映（差分管理）
4. AUP refusal 対策の追加検討
