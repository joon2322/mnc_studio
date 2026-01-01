#!/bin/bash
# MNC Audio Organizer 실행 스크립트

export DISPLAY="${DISPLAY:-:1}"

cd /opt/mnc-system/mnc_studio/audio_organizer

/opt/mnc-system/mnc_studio/venv/bin/python main.py
