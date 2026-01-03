#!/usr/bin/env python3
"""
대구비행장 32-bit 추출 스크립트

이전 추출 로그 기준:
- 10개 고정식 지점 (N-1 ~ N-10)
- 5일 (2025-11-24, 25, 26, 27, 12-01) - 주말 제외
- 총 50개 세션

메인 시스템 폴더에 WAV 파일 출력
"""

import sys
from pathlib import Path
from datetime import date
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
from src.processors.fusion_processor import FusionProcessor

# === 설정 ===
SOURCE_BASE = Path("/media/joonwon/24~26년 군용역 1차조사1/2024~26년 1차조사 군용역/공_05_대구비행장_(K-2)_형주(완)/01_원본데이터(오디오제외)")
OUTPUT_BASE = Path("/mnt/audio_archive/upload_drop/대구비행장")

# 추출 대상 (이전 로그 기준)
POINTS = ["N-1", "N-2", "N-3", "N-4", "N-5", "N-6", "N-7", "N-8", "N-9", "N-10"]
DATES = [
    date(2025, 11, 24),  # 월
    date(2025, 11, 25),  # 화
    date(2025, 11, 26),  # 수
    date(2025, 11, 27),  # 목
    date(2025, 12, 1),   # 월
]
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
SAMPLE_RATE = 25600


def find_source_audio_folder(point: str, mdate: date) -> Path:
    """소스 Audio 폴더 찾기"""
    point_dir = SOURCE_BASE / point
    if not point_dir.exists():
        return None

    date_str = mdate.strftime("%Y%m%d")

    for folder in point_dir.iterdir():
        if folder.is_dir() and folder.name.startswith(date_str):
            audio_dir = folder / "Audio"
            if audio_dir.exists():
                return audio_dir
    return None


def find_target_session_folder(point: str, mdate: date) -> Path:
    """메인 시스템 세션 폴더 찾기"""
    point_dir = OUTPUT_BASE / point
    if not point_dir.exists():
        return None

    date_str = mdate.strftime("%Y%m%d")

    for folder in point_dir.iterdir():
        if folder.is_dir() and f"_{date_str}_" in folder.name:
            return folder
    return None


def process_session(args):
    """세션 처리 워커"""
    point, mdate, source_dir, target_dir = args
    weekday = WEEKDAY_KR[mdate.weekday()]

    try:
        processor = FusionProcessor(
            measurement_date=mdate,
            sample_rate=SAMPLE_RATE,
        )
        result = processor.process(source_dir, target_dir)

        return {
            'point': point,
            'date': mdate.strftime("%Y-%m-%d"),
            'weekday': weekday,
            'success': result.success,
            'files': result.files_processed,
            'message': result.message if not result.success else None
        }
    except Exception as e:
        return {
            'point': point,
            'date': mdate.strftime("%Y-%m-%d"),
            'weekday': weekday,
            'success': False,
            'files': 0,
            'message': str(e)
        }


def main():
    print("=" * 60)
    print("대구비행장 32-bit 오디오 추출")
    print("=" * 60)
    print()

    # 작업 목록 생성
    tasks = []
    missing_source = []
    missing_target = []

    for point in POINTS:
        for mdate in DATES:
            source_dir = find_source_audio_folder(point, mdate)
            target_dir = find_target_session_folder(point, mdate)

            if not source_dir:
                missing_source.append(f"{point} {mdate}")
                continue
            if not target_dir:
                missing_target.append(f"{point} {mdate}")
                continue

            tasks.append((point, mdate, source_dir, target_dir))

    print(f"추출 대상: {len(tasks)}개 세션")
    print(f"소스 없음: {len(missing_source)}개")
    print(f"타겟 없음: {len(missing_target)}개")
    print()

    if missing_source:
        print("[소스 없음]")
        for m in missing_source[:5]:
            print(f"  {m}")
        print()

    if len(tasks) == 0:
        print("추출할 세션이 없습니다.")
        return

    # 병렬 추출
    print(f"[추출 시작] Workers: 10")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    with ProcessPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_session, task): task for task in tasks}

        completed = 0
        for future in as_completed(futures):
            completed += 1
            r = future.result()

            if r['success']:
                success_count += 1
                status = f"OK ({r['files']} files)"
            else:
                fail_count += 1
                status = f"FAIL: {r['message']}"

            print(f"[{completed}/{len(tasks)}] {r['point']} {r['date']}({r['weekday']}) -> {status}")

    print("-" * 60)
    print()
    print(f"[완료]")
    print(f"  성공: {success_count}")
    print(f"  실패: {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
