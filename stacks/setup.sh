#!/usr/bin/env bash
# 初回セットアップ / 再セットアップ（systemd に stacks.service を登録）
# 二重にユニットを増やさない。既存なら上書き更新して再読み込みする。
set -euo pipefail

# shellcheck source=_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

require_files
check_location

echo "=============================================="
echo " stacks セットアップ"
echo " 配置: ${SCRIPT_DIR}"
echo "=============================================="

# ログフォルダ（stacks.py の LOG_DIR と一致）
mkdir -p "${SCRIPT_DIR}/logs"

# gpio グループ（無ければ警告のみ）
if getent group gpio >/dev/null 2>&1; then
  if id -nG "$(whoami)" | tr ' ' '\n' | grep -qx gpio; then
    echo "OK: ユーザー $(whoami) は gpio グループに入っています"
  else
    echo "警告: $(whoami) が gpio グループに入っていません。"
    echo "      必要なら: sudo usermod -aG gpio $(whoami) のあと再ログイン"
  fi
fi

if [[ -f "${UNIT_DST}" ]]; then
  echo "既に ${UNIT_DST} があります → 内容を更新します（新規の二重作成はしません）"
else
  echo "新規に ${UNIT_DST} を作成します"
fi

sudo cp "${SCRIPT_DIR}/stacks.service" "${UNIT_DST}"
sudo systemctl daemon-reload

if systemctl is-enabled --quiet "${UNIT_NAME}" 2>/dev/null; then
  echo "自動起動は既に有効です → サービスを再起動します"
  sudo systemctl restart "${UNIT_NAME}"
else
  echo "自動起動を有効にして起動します"
  sudo systemctl enable --now "${UNIT_NAME}"
fi

echo ""
echo "---- 状態 ----"
systemctl --no-pager --full status "${UNIT_NAME}" || true
echo ""
echo "セットアップ完了。"
echo "  ・監視はまだ OFF（赤LED）。本体のボタン①で監視開始。"
echo "  ・ログ確認: 同じフォルダの show-logs.sh"
echo "  ・一時停止: stop.sh / 再開: start.sh"
