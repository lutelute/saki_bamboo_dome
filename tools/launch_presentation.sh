#!/bin/bash
# launch_presentation.sh — プレゼン用ランチャー
#
# 使い方:
#   ./tools/launch_presentation.sh            # メニュー表示
#   ./tools/launch_presentation.sh all        # 全部表示
#   ./tools/launch_presentation.sh dashboard  # ダッシュボードのみ
#   ./tools/launch_presentation.sh videos     # 全動画再生
#   ./tools/launch_presentation.sh blender    # Blender (崩壊)
#   ./tools/launch_presentation.sh gifs       # GIF表示
#
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

show_menu() {
  cat <<EOF
🎍 竹ジオデシックドーム プレゼン素材ランチャー
================================================

使い方: $0 <コマンド>

  all          すべて起動（ダッシュボード+動画+Blender）
  dashboard    ダッシュボード（HTML）
  interactive  3Dインタラクティブビュー
  videos       全動画を順次再生（QuickTime）
  main         メインの崩壊動画のみ
  blender      Blender で崩壊シミュ
  blender-bvs  Blender で雪積もり
  blender-stress  Blender で応力アニメ
  gifs         GIF をブラウザで一覧表示
  list         全成果物のリスト

EOF
}

case "${1:-menu}" in
  menu|help|--help|-h)
    show_menu
    ;;

  all)
    echo "📊 ダッシュボードを開きます..."
    open output/dome_dashboard.html
    sleep 1
    echo "🎬 メイン動画を再生..."
    open -a "QuickTime Player" output/sim/collapse_simulation.mp4
    sleep 1
    echo "🎨 Blenderで崩壊シーンを開きます..."
    open -a Blender output/sim/collapse.blend
    ;;

  dashboard)
    echo "📊 ダッシュボードを開きます..."
    open output/dome_dashboard.html
    ;;

  interactive)
    echo "🌐 インタラクティブ3Dビューを開きます..."
    open output/dome_interactive.html
    ;;

  videos)
    echo "🎬 全動画を順次再生（5秒ずつ）..."
    for v in \
      output/sim/snow_accumulation.mp4 \
      output/sim/bamboo_vinyl_snow_v2.mp4 \
      output/sim/stress_animation.mp4 \
      output/sim/collapse_simulation.mp4 \
      output/sim/presentation.mp4 \
      output/sim/wind_cfd.mp4
    do
      echo "  ▶ $v"
      open -a "QuickTime Player" "$v"
      sleep 6
    done
    ;;

  main|collapse)
    echo "🎬 メイン崩壊動画を再生..."
    open -a "QuickTime Player" output/sim/collapse_simulation.mp4
    ;;

  blender|blender-collapse)
    echo "🎨 Blender: 崩壊シーン"
    open -a Blender output/sim/collapse.blend
    ;;

  blender-bvs|blender-snow)
    echo "🎨 Blender: 雪積もりシーン"
    open -a Blender output/sim/bvs2.blend
    ;;

  blender-stress)
    echo "🎨 Blender: 応力アニメ"
    open -a Blender output/sim/stress.blend
    ;;

  blender-color)
    echo "🎨 Blender: 色つき雪積もり (シンプル版)"
    open -a Blender output/sim/snow_color.blend
    ;;

  gifs)
    echo "🖼 GIFビューアをブラウザで開きます..."
    open docs/gif/index.html 2>/dev/null || open docs/gif/
    ;;

  list)
    cat <<EOF
🎍 竹ジオデシックドーム 成果物リスト
================================================

📊 ダッシュボード:
  output/dome_dashboard.html       11構成の比較ダッシュボード
  output/dome_interactive.html     3Dインタラクティブビュー

🎬 動画 (QT互換mp4):
  output/sim/collapse_simulation.mp4    ⭐ 雪→崩壊（メイン）
  output/sim/bamboo_vinyl_snow_v2.mp4   竹ビニール雪積もり
  output/sim/stress_animation.mp4       応力色変化
  output/sim/snow_accumulation.mp4      シンプル雪積もり
  output/sim/wind_cfd.mp4                風CFD（流れ）
  output/sim/presentation.mp4           統合プレゼン版

🎨 Blender (.blend):
  output/sim/collapse.blend           ⭐ 崩壊シーン
  output/sim/bvs2.blend               雪積もり（ビニール付）
  output/sim/stress.blend             応力アニメ
  output/sim/snow_color.blend         色つき雪積もり
  output/sim/snow_final.blend         旧雪積もり

🖼 GIF (docs/gif/):
  collapse_simulation.gif        崩壊
  bamboo_vinyl_snow_v2.gif       雪積もり
  stress_animation.gif           応力
  presentation_highlight.gif     ハイライト

📚 ドキュメント:
  docs/MANUAL.md                Blender操作マニュアル
  docs/PRESENTATION.md          プレゼンストーリー
  README.md                     プロジェクト全体

EOF
    ;;

  *)
    echo "❌ 不明なコマンド: $1"
    echo ""
    show_menu
    exit 1
    ;;
esac
