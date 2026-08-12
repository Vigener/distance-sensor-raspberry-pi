#!/usr/bin/env bash
# 一時停止したあと、プログラムを再度起動するとき
set -euo pipefail

# shellcheck source=_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

if [[ ! -f "${UNIT_DST}" ]]; then
  die "${UNIT_NAME} が未登録です。先に setup.sh を実行してください。"
fi

echo "stacks.service を開始します..."
sudo systemctl start "${UNIT_NAME}"
systemctl --no-pager --full status "${UNIT_NAME}" || true
echo "完了。監視開始は本体のボタン①です。"
