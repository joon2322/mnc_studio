#!/bin/bash
# MNC Audio Organizer CLI
# Usage: audio-cli scan /path/to/source
#        audio-cli extract /path/to/source --location 대구비행장 --output /path/to/output

cd /opt/mnc-system/mnc_studio/audio_organizer
source /opt/mnc-system/mnc_studio/venv/bin/activate
python main_cli.py "$@"
