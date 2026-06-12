#!/usr/bin/env bash
# K-Text Clock 펌웨어를 CoreS3 /flash/apps/k_text_clock/ 에 업로드.
#
# 사전조건:
#   - mpremote 설치: pip install mpremote (또는 brew install mpremote)
#   - CoreS3가 USB로 연결되어 있고 UIFlow2 IDE/WebTerminal이 닫혀 있어야 함
#
# 사용:
#   ./scripts/push.sh                          # 포트 자동 탐지
#   PORT=/dev/cu.usbmodem1401 ./scripts/push.sh  # 포트 직접 지정

set -euo pipefail

MPREMOTE="${MPREMOTE:-mpremote}"
FIRMWARE_DIR="$(cd "$(dirname "$0")/../firmware" && pwd)"

# 포트 자동 탐지 (macOS/Linux)
if [ -z "${PORT:-}" ]; then
    PORT=$(ls /dev/cu.usbmodem* /dev/ttyACM* 2>/dev/null | head -1 || true)
fi
if [ -z "${PORT:-}" ] || [ ! -e "$PORT" ]; then
    echo "[error] USB 포트를 찾을 수 없음 — CoreS3 연결 확인 후 PORT= 로 지정" >&2
    exit 1
fi
echo "[port] $PORT"

if ! "$MPREMOTE" connect "$PORT" exec "print('ok')" >/dev/null 2>&1; then
    echo "[error] mpremote raw REPL 진입 실패" >&2
    echo "  → UIFlow2 IDE/WebTerminal을 닫고 재시도" >&2
    echo "  → 또는 CoreS3 RST 버튼을 짧게 누른 뒤 재시도" >&2
    exit 2
fi

echo "[mkdir] /flash/apps/k_text_clock/"
"$MPREMOTE" connect "$PORT" exec "
import os
for d in ('/flash/apps', '/flash/apps/k_text_clock'):
    try:
        os.mkdir(d)
    except OSError:
        pass
"

for f in main.py wifi_event.py wifi_setup.py; do
    echo "[push] $f"
    "$MPREMOTE" connect "$PORT" cp "$FIRMWARE_DIR/$f" ":/flash/apps/k_text_clock/$f"
done

# wifi_event/wifi_setup은 main.py가 import하므로 /flash 루트에도 복사
for f in wifi_event.py wifi_setup.py; do
    "$MPREMOTE" connect "$PORT" cp "$FIRMWARE_DIR/$f" ":/flash/$f"
done

echo "[done] 업로드 완료 — UIFlow2 런처에서 k_text_clock 실행 또는 RST"
