#!/bin/bash
# MNC Audio Organizer 실행 스크립트

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STUDIO_DIR="$(dirname "$SCRIPT_DIR")"

export DISPLAY="${DISPLAY:-:1}"

cd "$STUDIO_DIR/audio_organizer"

# 가상환경 활성화
if [ -f "$STUDIO_DIR/venv/bin/activate" ]; then
    source "$STUDIO_DIR/venv/bin/activate"
fi

python main.py
