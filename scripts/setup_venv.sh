#!/bin/bash
# MNC Studio 가상환경 설정 스크립트

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STUDIO_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== MNC Studio 환경 설정 ==="

# 가상환경 생성
if [ ! -d "$STUDIO_DIR/venv" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv "$STUDIO_DIR/venv"
fi

# 활성화
source "$STUDIO_DIR/venv/bin/activate"

# 패키지 설치
echo "패키지 설치 중..."
pip install --upgrade pip

# 각 도구의 requirements 설치
for tool in audio_organizer audio_copier converter; do
    if [ -f "$STUDIO_DIR/$tool/requirements.txt" ]; then
        echo "  - $tool 의존성 설치..."
        pip install -r "$STUDIO_DIR/$tool/requirements.txt"
    fi
done

echo ""
echo "=== 설정 완료 ==="
echo "실행 방법:"
echo "  bash $STUDIO_DIR/scripts/run_audio_organizer.sh"
echo "  bash $STUDIO_DIR/scripts/run_audio_copier.sh"
echo "  bash $STUDIO_DIR/scripts/run_converter.sh"
