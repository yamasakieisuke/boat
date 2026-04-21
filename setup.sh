#!/bin/bash
# ==========================================================
# ボートレース予想システム セットアップ & 初回データ取得
# Cowork上でこのスクリプトを実行してください
# ==========================================================

echo "======================================"
echo " ボートレース予想システム セットアップ"
echo "======================================"

# 作業ディレクトリ
cd "$(dirname "$0")"

# 1. ライブラリインストール
echo ""
echo "[1/3] ライブラリをインストール中..."
pip install -r requirements.txt --quiet

# 2. データフォルダ作成
echo ""
echo "[2/3] フォルダ構成を作成中..."
mkdir -p data/results_raw
mkdir -p data/results_csv
mkdir -p data/racecards
mkdir -p data/players
mkdir -p data/motors
mkdir -p data/weather
mkdir -p data/odds
mkdir -p data/results
mkdir -p data/raw
mkdir -p data/venues
mkdir -p logs
mkdir -p output
echo "  フォルダ作成完了"

# 3. 過去データ取得
echo ""
echo "[3/3] 過去3年分の競走成績を取得します..."
echo "  ※ 約30〜40分かかります（サーバー負荷配慮のため1.5秒間隔）"
echo "  ※ 途中で止めても再実行すると続きから取得します"
echo ""
python scripts/fetch_results.py --years 3

echo ""
echo "======================================"
echo " セットアップ完了！"
echo " data/results_csv/ にCSVが保存されました"
echo "======================================"
