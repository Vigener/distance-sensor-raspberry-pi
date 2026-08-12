# stacks 用シェルの共通処理（直接実行しない）
# shellcheck shell=bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPECTED_DIR="${HOME}/Desktop/stacks"
UNIT_NAME="stacks.service"
UNIT_DST="/etc/systemd/system/${UNIT_NAME}"

die() {
  echo "エラー: $*" >&2
  exit 1
}

require_files() {
  [[ -f "${SCRIPT_DIR}/stacks.py" ]] || die "stacks.py が見つかりません: ${SCRIPT_DIR}"
  [[ -f "${SCRIPT_DIR}/stacks.service" ]] || die "stacks.service が見つかりません: ${SCRIPT_DIR}"
}

check_location() {
  if [[ "${SCRIPT_DIR}" != "${EXPECTED_DIR}" ]]; then
    echo "警告: 想定配置は ${EXPECTED_DIR} です。現在: ${SCRIPT_DIR}"
    echo "      USB から ${EXPECTED_DIR} へコピーしてから実行してください。"
  fi
}
