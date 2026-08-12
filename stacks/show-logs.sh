#!/usr/bin/env bash
# エラー確認用: サービスの状態と直近ログを表示
set -euo pipefail

# shellcheck source=_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

echo "=============================================="
echo " stacks.service 状態"
echo "=============================================="
if [[ -f "${UNIT_DST}" ]]; then
  systemctl --no-pager --full status "${UNIT_NAME}" || true
else
  echo "（未セットアップ: ${UNIT_DST} がありません。setup.sh を実行してください）"
fi

echo ""
echo "=============================================="
echo " journalctl 直近 80 行"
echo "=============================================="
journalctl -u "${UNIT_NAME}" -n 80 --no-pager || true

echo ""
echo "=============================================="
echo " CSV ログ（${SCRIPT_DIR}/logs）"
echo "=============================================="
if [[ -d "${SCRIPT_DIR}/logs" ]]; then
  ls -lt "${SCRIPT_DIR}/logs" | head -n 15 || true
  latest="$(ls -t "${SCRIPT_DIR}/logs"/wafer_log_*.csv 2>/dev/null | head -n 1 || true)"
  if [[ -n "${latest}" ]]; then
    echo ""
    echo "---- 最新 CSV 末尾 ----"
    echo "${latest}"
    tail -n 20 "${latest}" || true
  fi
else
  echo "logs フォルダがまだありません。"
fi

echo ""
echo "リアルタイムで追う場合:"
echo "  journalctl -u ${UNIT_NAME} -f"
