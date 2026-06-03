#!/bin/bash
# presentation_mode.sh — プレゼン用ホットキー切替
#
# 使い方:
#   ./tools/presentation_mode.sh setup   # 全部開く（並べて待機）
#   ./tools/presentation_mode.sh close   # 全部閉じる
#
# プレゼン中は Cmd+Tab で各アプリ切替

set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

case "${1:-setup}" in
  setup)
    echo "🎬 プレゼン素材を一括起動中..."
    echo ""
    echo "📊 1/4 ダッシュボード（ブラウザ）"
    open output/dome_dashboard.html
    sleep 2

    echo "🖼 2/4 GIFインデックス（ブラウザ）"
    open docs/gif/index.html
    sleep 2

    echo "🌐 3/4 3Dインタラクティブビュー（ブラウザ）"
    open output/dome_interactive.html
    sleep 2

    echo "🎨 4/4 Blender（崩壊シーン）"
    open -a Blender output/sim/collapse.blend
    sleep 2

    echo ""
    echo "✅ 起動完了！プレゼン準備OK"
    echo ""
    echo "切替: Cmd+Tab でブラウザ ↔ Blender"
    echo "Blender操作: スペースで再生、Zキーでマテリアル表示"
    echo ""
    echo "個別動画再生コマンド:"
    echo "  open -a 'QuickTime Player' output/sim/collapse_simulation.mp4"
    echo "  open -a 'QuickTime Player' output/sim/bamboo_vinyl_snow_v2.mp4"
    echo "  open -a 'QuickTime Player' output/sim/stress_animation.mp4"
    ;;

  close)
    echo "🛑 プレゼン素材を閉じます..."
    osascript -e 'quit app "QuickTime Player"' 2>/dev/null || true
    osascript -e 'quit app "Blender"' 2>/dev/null || true
    echo "✅ Blender, QuickTimeを終了"
    echo "（ブラウザのタブは手動で閉じてください）"
    ;;

  *)
    echo "使い方: $0 [setup|close]"
    exit 1
    ;;
esac
