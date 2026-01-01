#!/bin/bash
# MNC Audio Copier 실행 스크립트

export DISPLAY="${DISPLAY:-:1}"

cd /opt/mnc-system/mnc_studio/audio_copier

/opt/mnc-system/mnc_studio/venv/bin/python main.py
