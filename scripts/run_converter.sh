#!/bin/bash
# MNC Master Converter 실행 스크립트

export DISPLAY="${DISPLAY:-:1}"

cd /opt/mnc-system/mnc_studio/converter

/opt/mnc-system/mnc_studio/venv/bin/python main.py
