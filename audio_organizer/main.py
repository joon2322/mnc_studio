#!/usr/bin/env python3
"""MNC Audio Organizer v1.0 - 진입점"""

import sys
from pathlib import Path

# src 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from src.app import main

if __name__ == "__main__":
    main()
