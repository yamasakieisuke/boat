#!/bin/bash
# racecards のバックフィルを夜間だけ走らせる。launchd から1日1回叩かれる想定。
#
# なぜ夜間限定か:
#   日中は boatrace.jp が混んでおり 12.9秒/件 → 61.6秒/件 まで落ちて
#   read timeout が頻発した実測がある。取得は 01:00-07:00 に閉じる。
#
# ⚠️ macOS には GNU の `timeout` が無い。以前ここで
#      timeout 21000 python3 scripts/backfill_racecards.py ...
#    としていたため "timeout: command not found" で毎晩即死し、
#    3晩まるごと1件も取れていないのに動いているように見えていた（2026-08-23〜25）。
#    停止時刻は backfill_racecards.py の --until が自前で持つ。
set -u
cd "$(dirname "$0")/.."

LOG="logs/backfill_racecards.log"
H=$(date +%H)

# launchd はスリープ中に発火時刻を過ぎると「起きた時点」で実行する。
# 昼に起きて走り出さないよう、ウィンドウ外なら黙って抜ける。
if [ "$((10#$H))" -lt 1 ] || [ "$((10#$H))" -ge 7 ]; then
  echo "[$(date)] ウィンドウ外(${H}時)のためスキップ" >> "$LOG"
  exit 0
fi

echo "[$(date)] 開始" >> "$LOG"
# --refetch-empty-name: 〜v5.26 のスクレイパは race_name を 24.9% で取りこぼして
# いた。空のまま残った 725件はレース種別が unknown に落ちるので取り直す。
/usr/bin/python3 scripts/backfill_racecards.py \
  --from 20260301 --to 20260815 \
  --limit 0 --sleep 2.0 --until 07:00 --refetch-empty-name >> "$LOG" 2>&1
echo "[$(date)] 終了 (exit=$?)" >> "$LOG"
