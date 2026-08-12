#!/usr/bin/env bash
# 検証などで一時的に止めたいとき（再起動後の自動起動設定は残る）
set -euo pipefail

# shellcheck source=_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

if [[ ! -f "${UNIT_DST}" ]]; then
  die "${UNIT_NAME} が未登録です。先に setup.sh を実行してください。"
fi

echo "stacks.service を停止します..."
sudo systemctl stop "${UNIT_NAME}"
systemctl --no-pager --full status "${UNIT_NAME}" || true
echo "完了。再開するときは start.sh を実行してください。"
