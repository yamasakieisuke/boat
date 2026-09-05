#!/bin/bash
# 福岡オリジナル展示のバックフィルを夜間だけ走らせる。launchd から1日1回叩かれる想定。
#
# 相手は boatrace-fukuoka.com（第三者のサーバー）。日中は当日のレース情報を
# 配信しているので、負荷をかけない時間帯に閉じる。
# racecards のバックフィルとは別ホストなので同時間帯でも競合しない。
#
# ⚠️ macOS には GNU の `timeout` が無い。停止時刻は
#    backfill_fukuoka_tenji.py の --until が自前で持つ。
set -u
cd "$(dirname "$0")/.."

LOG="logs/backfill_fukuoka_tenji.log"
H=$(date +%H)

# launchd はスリープ中に発火時刻を過ぎると起床時に実行する。
# 昼に起きて走り出さないよう、ウィンドウ外なら黙って抜ける。
if [ "$((10#$H))" -lt 1 ] || [ "$((10#$H))" -ge 7 ]; then
  echo "[$(date)] ウィンドウ外(${H}時)のためスキップ" >> "$LOG"
  exit 0
fi

echo "[$(date)] 開始" >> "$LOG"
/usr/bin/python3 scripts/backfill_fukuoka_tenji.py \
  --limit 0 --sleep 2.0 --until 07:00 >> "$LOG" 2>&1
echo "[$(date)] 終了 (exit=$?)" >> "$LOG"
