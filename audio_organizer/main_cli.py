#!/usr/bin/env python3
"""
MNC Audio Organizer CLI

Usage:
    # 스캔 (세션 목록 확인)
    python main_cli.py scan /path/to/source

    # 추출 (자체 폴더 구조 생성)
    python main_cli.py extract /path/to/source --location 대구비행장 --output /mnt/audio_archive/raw_audio

    # 메인시스템 세션 폴더에 추출 (권장)
    python main_cli.py extract-to-main /path/to/source --output /mnt/audio_archive/upload_drop/대구비행장

    # 옵션
    --exclude-weekend    주말 제외
    --exclude-partial    부분 데이터 제외
    --dry-run           실제 추출 없이 확인만
    --workers N         병렬 처리 (기본: 10)
"""

import argparse
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime
from multiprocessing import cpu_count
from pathlib import Path
from typing import Optional, List, Tuple, Dict

# 프로젝트 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from src.detectors.fusion_detector import FusionDetector
from src.detectors.rion_detector import RionDetector
from src.processors.fusion_processor import FusionProcessor
from src.processors.rion_processor import RionProcessor
from src.utils.session_utils import create_session_folder
from src.utils.point_utils import normalize_point_name, point_sort_key


def process_point_sessions(args_tuple):
    """
    지점별 세션 처리 (병렬 처리용 워커)

    Args:
        args_tuple: (point, sessions, output_path, location) 튜플

    Returns:
        dict: {point, success_count, fail_count, results}
    """
    point, sessions, output_path, location = args_tuple

    results = []
    success_count = 0
    fail_count = 0

    for session in sessions:
        try:
            # 출력 폴더 생성
            session_output = create_session_folder(
                output_path,
                location,
                session.point,
                session.measurement_date,
            )

            if session_output is None:
                results.append({
                    'session': session,
                    'status': 'skip',
                    'message': '이미 존재'
                })
                continue

            # 프로세서 생성 (세션별 샘플레이트)
            processor = FusionProcessor(
                measurement_date=session.measurement_date,
                sample_rate=session.sample_rate,
            )

            # 변환
            result = processor.process(
                session.source_path,
                session_output,
            )

            if result.success:
                results.append({
                    'session': session,
                    'status': 'ok',
                    'files': result.files_processed
                })
                success_count += 1
            else:
                results.append({
                    'session': session,
                    'status': 'fail',
                    'message': result.message
                })
                fail_count += 1

        except Exception as e:
            results.append({
                'session': session,
                'status': 'error',
                'message': str(e)
            })
            fail_count += 1

    return {
        'point': point,
        'success_count': success_count,
        'fail_count': fail_count,
        'results': results
    }


# 색상 활성화 여부 (TTY 자동 감지, --no-color로 비활성화 가능)
_use_color = sys.stdout.isatty()


# 색상 코드
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


def colorize(text: str, color: str) -> str:
    """텍스트에 색상 적용 (TTY가 아니거나 --no-color면 색상 없음)"""
    if _use_color:
        return f"{color}{text}{Colors.RESET}"
    return text


def get_weekday_kr(d: date) -> str:
    """요일 (한글)"""
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[d.weekday()]


def is_weekend(d: date) -> bool:
    """주말 여부"""
    return d.weekday() >= 5


def format_status(session) -> str:
    """세션 상태 포맷"""
    issues = []

    # 파일 수 체크
    if session.expected_count > 0:
        if session.file_count < session.expected_count:
            issues.append(f"부분({session.file_count}/{session.expected_count})")

    # 샘플레이트 체크
    if session.sample_rate != 25600:
        rate_khz = session.sample_rate / 1000
        issues.append(f"{rate_khz:.1f}kHz")

    # 검증 실패
    if session.skip_count > 0:
        issues.append(f"검증실패:{session.skip_count}")

    if issues:
        return colorize(" | ".join(issues), Colors.YELLOW)
    return colorize("정상", Colors.GREEN)


def find_main_system_session_folder(output_base: Path, point: str, mdate: date) -> Optional[Path]:
    """
    메인시스템의 session_... 폴더 찾기

    폴더 형식: session_{timestamp}_{location}_{point}_{YYYYMMDD}_{weekday}_{index}
    예: session_20251226_131302_대구비행장_N-1_20251124_월_000

    Args:
        output_base: 출력 베이스 경로 (예: /mnt/audio_archive/upload_drop/대구비행장)
        point: 지점명 (예: N-1, N01, 이동식6 등)
        mdate: 측정 날짜

    Returns:
        매칭되는 세션 폴더 경로 또는 None
    """
    # 지점명 정규화 (N01 → N-1, 이동식6 → 이동식-6)
    normalized_point = normalize_point_name(point)

    point_dir = output_base / normalized_point
    if not point_dir.exists():
        return None

    date_str = mdate.strftime("%Y%m%d")

    for folder in point_dir.iterdir():
        if folder.is_dir() and folder.name.startswith("session_"):
            # session_{ts}_{loc}_{point}_{YYYYMMDD}_{weekday}_{idx} 형식에서 날짜 추출
            # 날짜는 _YYYYMMDD_ 패턴으로 찾기
            if f"_{date_str}_" in folder.name:
                return folder

    return None


def create_extraction_plan(
    sessions: List,
    output_base: Path,
    location: str,
    plan_file: Path,
    exclude_weekend: bool = False,
    exclude_partial: bool = False
) -> Tuple[List[Tuple], List[Tuple], List[Tuple]]:
    """
    추출 계획 파일 생성

    Args:
        sessions: 스캔된 세션 목록
        output_base: 출력 베이스 경로
        location: 위치명 (사이트명)
        plan_file: 계획 파일 저장 경로
        exclude_weekend: 주말 제외
        exclude_partial: 부분 데이터 제외

    Returns:
        (valid_tasks, skipped, missing_target) 튜플
        - valid_tasks: (session, source_dir, target_dir, location) 리스트
        - skipped: (session, reason) 리스트
        - missing_target: (session, reason) 리스트
    """
    valid_tasks = []
    skipped = []
    missing_target = []

    for session in sessions:
        # 주말 제외
        if exclude_weekend and is_weekend(session.measurement_date):
            skipped.append((session, "주말"))
            continue

        # 부분 데이터 제외
        if exclude_partial:
            if session.expected_count > 0 and session.file_count < session.expected_count:
                skipped.append((session, "부분 데이터"))
                continue

        # 타겟 폴더 찾기
        target_dir = find_main_system_session_folder(
            output_base, session.point, session.measurement_date
        )

        if target_dir is None:
            missing_target.append((session, "타겟 폴더 없음"))
            continue

        valid_tasks.append((session, session.source_path, target_dir, location))

    # 정렬 키 함수 (point_utils.point_sort_key 사용)
    def task_sort_key(task):
        session = task[0]
        return (point_sort_key(session.point), session.measurement_date, str(task[1]))

    def session_sort_key(item):
        session = item[0]
        return (point_sort_key(session.point), session.measurement_date)

    sorted_tasks = sorted(valid_tasks, key=task_sort_key)
    skipped = sorted(skipped, key=session_sort_key)
    missing_target = sorted(missing_target, key=session_sort_key)

    # 동일 날짜 분할 세션 감지 (지점+날짜 기준 그룹화)
    from collections import defaultdict
    session_groups = defaultdict(list)
    for task in sorted_tasks:
        session, source_dir, target_dir, _ = task  # location은 모든 task에서 동일
        key = (session.point, session.measurement_date)
        session_groups[key].append(task)

    # 분할 세션 목록
    split_sessions = {k: v for k, v in session_groups.items() if len(v) > 1}

    # 고유 타겟 세션 수 (실제 출력 세션 수)
    unique_targets = len(session_groups)

    # 계획 파일 작성
    with open(plan_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("MNC Audio Organizer - 추출 계획서\n")
        f.write("=" * 80 + "\n")
        f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"출력 베이스: {output_base}\n")
        f.write("\n")

        # 장비별 개수 계산
        fusion_tasks = [t for t in valid_tasks if getattr(t[0], 'equipment_type', 'fusion') == 'fusion']
        rion_tasks = [t for t in valid_tasks if getattr(t[0], 'equipment_type', 'rion') == 'rion']

        # 요약
        f.write("-" * 80 + "\n")
        f.write("요약\n")
        f.write("-" * 80 + "\n")
        f.write(f"원본 추출 대상: {len(valid_tasks)}개 폴더\n")
        if fusion_tasks:
            f.write(f"  - Fusion: {len(fusion_tasks)}개 (BID → WAV 변환)\n")
        if rion_tasks:
            f.write(f"  - Rion: {len(rion_tasks)}개 (WAV 복사)\n")
        f.write(f"출력 세션: {unique_targets}개 (동일 날짜 분할: {len(split_sessions)}건)\n")
        f.write(f"스킵: {len(skipped)}개 (주말/부분 데이터)\n")
        f.write(f"타겟 없음: {len(missing_target)}개\n")
        f.write("\n")

        # 분할 세션 안내
        if split_sessions:
            f.write("-" * 80 + "\n")
            f.write(f"※ 동일 날짜 분할 세션 ({len(split_sessions)}건)\n")
            f.write("-" * 80 + "\n")
            sorted_split = sorted(split_sessions.items(), key=lambda x: (point_sort_key(x[0][0]), x[0][1]))
            for (point, mdate), tasks in sorted_split:
                weekday = get_weekday_kr(mdate)
                date_str = mdate.strftime("%Y-%m-%d")
                total_files = sum(t[0].file_count for t in tasks)
                f.write(f"  {point} {date_str}({weekday}): {len(tasks)}개 폴더 → {total_files}개 BID\n")
                for i, (session, source_dir, target_dir, _) in enumerate(tasks, 1):
                    folder_name = source_dir.parent.name  # 날짜_시간 폴더명
                    f.write(f"      [{i}] {folder_name} ({session.file_count}개)\n")
            f.write("\n")

        # 추출 목록 표 (상단)
        if valid_tasks:
            f.write("=" * 100 + "\n")
            f.write("추출 목록\n")
            f.write("=" * 100 + "\n")
            f.write(f"{'번호':<6} {'지점':<10} {'측정일':<12} {'요일':<4} {'장비':<8} {'파일':<5} {'입력폴더':<24} {'출력세션'}\n")
            f.write("-" * 100 + "\n")

            for idx, (session, source_dir, target_dir, _) in enumerate(sorted_tasks, 1):
                weekday = get_weekday_kr(session.measurement_date)
                date_str = session.measurement_date.strftime("%Y-%m-%d")
                session_folder = target_dir.name[-30:]  # 세션폴더 끝부분
                equipment = getattr(session, 'equipment_type', 'fusion')
                equip_display = "Fusion" if equipment == 'fusion' else "Rion"

                # 입력 폴더명 (Fusion: Audio 상위, Rion: 장비폴더)
                if equipment == 'rion':
                    input_folder = source_dir.name  # NX-42RT 등
                else:
                    input_folder = source_dir.parent.name  # 날짜_시간 폴더명

                # 분할 세션 표시
                key = (session.point, session.measurement_date)
                if key in split_sessions:
                    split_idx = [t[1] for t in split_sessions[key]].index(source_dir) + 1
                    split_mark = f"[{split_idx}/{len(split_sessions[key])}]"
                else:
                    split_mark = ""

                f.write(f"{idx:<6} {session.point:<10} {date_str:<12} {weekday:<4} {equip_display:<8} {session.file_count:<5} {input_folder:<24} ...{session_folder[-22:]}{split_mark}\n")

            f.write("-" * 100 + "\n")
            f.write("\n")

        # 스킵 목록 (주말/부분)
        if skipped:
            f.write("-" * 80 + "\n")
            f.write(f"스킵 ({len(skipped)}개)\n")
            f.write("-" * 80 + "\n")
            for session, reason in skipped:
                weekday = get_weekday_kr(session.measurement_date)
                date_str = session.measurement_date.strftime("%Y-%m-%d")
                f.write(f"  {session.point} {date_str}({weekday}): {reason}\n")
            f.write("\n")

        # 타겟 없음 목록
        if missing_target:
            f.write("-" * 80 + "\n")
            f.write(f"타겟 폴더 없음 ({len(missing_target)}개) - 메인시스템에서 세션 생성 필요\n")
            f.write("-" * 80 + "\n")
            for session, reason in missing_target:
                weekday = get_weekday_kr(session.measurement_date)
                date_str = session.measurement_date.strftime("%Y-%m-%d")
                f.write(f"  {session.point} {date_str}({weekday})\n")
            f.write("\n")

        # 세부 정보 (하단)
        if valid_tasks:
            f.write("\n")
            f.write("=" * 80 + "\n")
            f.write("세부 경로 정보\n")
            f.write("=" * 80 + "\n")

            for idx, (session, source_dir, target_dir, _) in enumerate(sorted_tasks, 1):
                weekday = get_weekday_kr(session.measurement_date)
                date_str = session.measurement_date.strftime("%Y-%m-%d")

                f.write(f"\n[{idx}] {session.point} {date_str}({weekday}) - {session.file_count}개 BID\n")
                f.write(f"    입력: {source_dir}\n")
                f.write(f"    출력: {target_dir}\n")

            f.write("\n")

        f.write("=" * 80 + "\n")

    return valid_tasks, skipped, missing_target


def process_main_system_session(args_tuple):
    """
    메인시스템 세션 처리 워커 (병렬 처리용)

    Args:
        args_tuple: (session, source_dir, target_dir, location) 튜플

    Returns:
        dict: 처리 결과
    """
    session, source_dir, target_dir, location = args_tuple
    weekday = get_weekday_kr(session.measurement_date)
    equipment_type = getattr(session, 'equipment_type', 'fusion')

    try:
        if equipment_type == 'rion':
            # Rion: WAV 복사
            processor = RionProcessor(
                measurement_date=session.measurement_date,
            )
            result = processor.process(source_dir, target_dir)
            files_count = result.files_processed
            device_model = getattr(session, 'device_model', 'NX-42RT')
        else:
            # Fusion: BID → WAV 변환
            processor = FusionProcessor(
                measurement_date=session.measurement_date,
                sample_rate=session.sample_rate,
            )
            result = processor.process(source_dir, target_dir)
            files_count = result.files_processed
            device_model = None

        return {
            'point': session.point,
            'date': session.measurement_date.strftime("%Y-%m-%d"),
            'weekday': weekday,
            'equipment': equipment_type,
            'success': result.success,
            'files': files_count,
            'message': result.message if not result.success else None
        }
    except Exception as e:
        return {
            'point': session.point,
            'date': session.measurement_date.strftime("%Y-%m-%d"),
            'weekday': weekday,
            'equipment': equipment_type,
            'success': False,
            'files': 0,
            'message': str(e)
        }


def cmd_extract_to_main(args):
    """extract-to-main 명령어: 메인시스템 세션 폴더에 오디오 추출"""
    source_path = Path(args.source).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    workers = getattr(args, 'workers', 10)

    if not source_path.exists():
        print(colorize(f"[ERROR] 소스 경로 없음: {source_path}", Colors.RED))
        return 1

    if not output_path.exists():
        print(colorize(f"[ERROR] 출력 경로 없음: {output_path}", Colors.RED))
        return 1

    print(colorize(f"\n[스캔] {source_path}", Colors.BOLD))
    print(f"  출력: {output_path}")
    print()

    # Fusion + Rion 동시 스캔
    fusion_detector = FusionDetector()
    rion_detector = RionDetector()

    sessions = []
    fusion_count = 0
    rion_count = 0

    # Fusion 스캔
    if fusion_detector.detect(source_path):
        fusion_sessions = fusion_detector.scan(source_path)
        fusion_count = len(fusion_sessions)
        sessions.extend(fusion_sessions)

    # Rion 스캔
    if rion_detector.detect(source_path):
        rion_sessions = rion_detector.scan(source_path)
        rion_count = len(rion_sessions)
        sessions.extend(rion_sessions)

    if not sessions:
        print(colorize("[ERROR] 세션 없음 (Fusion/Rion 데이터 감지 안됨)", Colors.RED))
        return 1

    print(f"스캔 완료: {len(sessions)}개 세션 발견")
    if fusion_count > 0:
        print(f"  Fusion: {colorize(str(fusion_count), Colors.CYAN)}개")
    if rion_count > 0:
        print(f"  Rion: {colorize(str(rion_count), Colors.CYAN)}개")
    print()

    # 위치명 추출 (출력 폴더명에서)
    location = output_path.name

    # 추출 계획 파일 생성 (최신 1개만 유지)
    plan_file = output_path / "extraction_plan.txt"

    # 주말 제외가 기본값 (--include-weekend로 포함 가능)
    exclude_weekend = not getattr(args, 'include_weekend', False)

    valid_tasks, skipped, missing_target = create_extraction_plan(
        sessions=sessions,
        output_base=output_path,
        location=location,
        plan_file=plan_file,
        exclude_weekend=exclude_weekend,
        exclude_partial=args.exclude_partial,
    )

    print(colorize(f"[추출 계획 생성 완료]", Colors.BOLD))
    print(f"  파일: {plan_file}")
    print()
    print(f"  추출 대상: {colorize(str(len(valid_tasks)), Colors.GREEN)}개 세션")
    if skipped:
        print(f"  스킵: {colorize(str(len(skipped)), Colors.DIM)}개")
    if missing_target:
        print(f"  타겟 없음: {colorize(str(len(missing_target)), Colors.YELLOW)}개")
    print()

    if len(valid_tasks) == 0:
        print(colorize("[WARN] 추출할 세션이 없습니다.", Colors.YELLOW))
        return 0

    # 사용자 확인
    print("-" * 60)
    print(colorize("추출 계획 파일을 확인하신 후 진행해 주세요.", Colors.CYAN))
    print(f"  {plan_file}")
    print("-" * 60)
    print()

    try:
        confirm = input("추출을 시작하시겠습니까? (y/n): ").strip().lower()
    except EOFError:
        confirm = 'n'

    if confirm != 'y':
        print(colorize("\n[취소됨] 추출이 취소되었습니다.", Colors.YELLOW))
        return 0

    # 추출 시작
    print()
    print(colorize(f"[추출 시작] Workers: {workers}", Colors.BOLD))
    print("-" * 60)

    success_count = 0
    fail_count = 0

    # 추출 결과 수집
    extraction_results = []
    start_time = datetime.now()

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_main_system_session, task): task for task in valid_tasks}

        completed = 0
        for future in as_completed(futures):
            completed += 1
            r = future.result()

            if r['success']:
                success_count += 1
                status = colorize(f"OK ({r['files']} files)", Colors.GREEN)
            else:
                fail_count += 1
                status = colorize(f"FAIL: {r['message']}", Colors.RED)

            print(f"[{completed}/{len(valid_tasks)}] {r['point']} {r['date']}({r['weekday']}) -> {status}")
            extraction_results.append(r)

    end_time = datetime.now()
    elapsed = end_time - start_time

    print("-" * 60)
    print()
    print(colorize("[완료]", Colors.BOLD))
    print(f"  성공: {colorize(str(success_count), Colors.GREEN)}")
    if fail_count:
        print(f"  실패: {colorize(str(fail_count), Colors.RED)}")
    print(f"  소요: {elapsed.total_seconds():.1f}초")
    print("=" * 60)

    # 로그 파일 생성 (최신 1개만 유지)
    log_file = output_path / "extraction_log.txt"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("MNC Audio Organizer - 추출 로그\n")
        f.write("=" * 80 + "\n")
        f.write(f"시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"완료: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"소요: {elapsed.total_seconds():.1f}초\n")
        f.write(f"성공: {success_count}개\n")
        f.write(f"실패: {fail_count}개\n")
        f.write("\n")

        # 세션별 결과
        f.write("-" * 80 + "\n")
        f.write("세션별 결과\n")
        f.write("-" * 80 + "\n")

        # 지점+날짜 순 정렬
        sorted_results = sorted(extraction_results, key=lambda x: (point_sort_key(x['point']), x['date']))

        for r in sorted_results:
            status = "OK" if r['success'] else "FAIL"
            files_info = f"{r['files']} files" if r['success'] else r['message']
            f.write(f"{r['point']:<10} {r['date']} ({r['weekday']}) [{r['equipment']}] -> {status} ({files_info})\n")

        f.write("-" * 80 + "\n")

    return 0 if fail_count == 0 else 1


def cmd_scan(args):
    """scan 명령어: 세션 목록 스캔"""
    source_path = Path(args.source).expanduser().resolve()

    if not source_path.exists():
        print(colorize(f"[ERROR] 경로 없음: {source_path}", Colors.RED))
        return 1

    print(colorize(f"\n[스캔] {source_path}\n", Colors.BOLD))

    detector = FusionDetector()

    if not detector.detect(source_path):
        print(colorize("[WARN] Fusion 데이터 감지 안됨", Colors.YELLOW))
        return 1

    sessions = detector.scan(source_path)

    if not sessions:
        print(colorize("[WARN] 세션 없음", Colors.YELLOW))
        return 1

    # 통계
    total_count = len(sessions)
    weekend_count = sum(1 for s in sessions if is_weekend(s.measurement_date))
    partial_count = sum(1 for s in sessions if s.expected_count > 0 and s.file_count < s.expected_count)
    non_standard_hz = sum(1 for s in sessions if s.sample_rate != 25600)

    # 헤더
    header = f"{'지점':<12} {'측정일':<12} {'요일':<4} {'파일수':<10} {'Hz':<8} {'상태'}"
    print(colorize(header, Colors.BOLD))
    print("-" * 70)

    # 세션 목록
    for session in sessions:
        point = session.point
        date_str = session.measurement_date.strftime("%Y-%m-%d")
        weekday = get_weekday_kr(session.measurement_date)

        # 파일 수
        if session.expected_count > 0:
            file_count = f"{session.file_count}/{session.expected_count}"
        else:
            file_count = str(session.file_count)

        # 샘플레이트
        rate_khz = session.sample_rate / 1000
        hz_str = f"{rate_khz:.1f}k"

        # 상태
        status = format_status(session)

        # 주말 표시
        if is_weekend(session.measurement_date):
            weekday = colorize(weekday, Colors.DIM)
            date_str = colorize(date_str, Colors.DIM)

        # 비표준 Hz 강조
        if session.sample_rate != 25600:
            hz_str = colorize(hz_str, Colors.CYAN)

        print(f"{point:<12} {date_str:<12} {weekday:<4} {file_count:<10} {hz_str:<8} {status}")

    # 요약
    print("-" * 70)
    print(f"\n총 {colorize(str(total_count), Colors.BOLD)}개 세션")

    if weekend_count:
        print(f"  - 주말: {colorize(str(weekend_count), Colors.DIM)}개")
    if partial_count:
        print(f"  - 부분 데이터: {colorize(str(partial_count), Colors.YELLOW)}개")
    if non_standard_hz:
        print(f"  - 비표준 Hz: {colorize(str(non_standard_hz), Colors.CYAN)}개")

    print()
    return 0


def cmd_extract(args):
    """extract 명령어: 오디오 추출"""
    source_path = Path(args.source).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    location = args.location

    if not source_path.exists():
        print(colorize(f"[ERROR] 소스 경로 없음: {source_path}", Colors.RED))
        return 1

    if not location:
        print(colorize("[ERROR] --location 필수", Colors.RED))
        return 1

    # 워커 수 결정
    workers = getattr(args, 'workers', 1)
    if workers <= 0:
        workers = max(1, cpu_count() - 1)  # CPU 코어 - 1

    print(colorize(f"\n[추출] {source_path}", Colors.BOLD))
    print(f"  출력: {output_path}")
    print(f"  위치: {location}")

    if workers > 1:
        print(f"  병렬: {colorize(f'{workers} workers', Colors.CYAN)}")

    if args.dry_run:
        print(colorize("  [DRY-RUN 모드]", Colors.YELLOW))

    print()

    # 스캔
    detector = FusionDetector()

    if not detector.detect(source_path):
        print(colorize("[ERROR] Fusion 데이터 감지 안됨", Colors.RED))
        return 1

    sessions = detector.scan(source_path)

    if not sessions:
        print(colorize("[ERROR] 세션 없음", Colors.RED))
        return 1

    # 필터링
    filtered_sessions = []
    skipped_sessions = []  # (session, reason) 튜플 리스트

    for session in sessions:
        # 주말 제외
        if args.exclude_weekend and is_weekend(session.measurement_date):
            skipped_sessions.append((session, "주말"))
            continue

        # 부분 데이터 제외
        if args.exclude_partial:
            if session.expected_count > 0 and session.file_count < session.expected_count:
                skipped_sessions.append((session, "부분 데이터"))
                continue

        filtered_sessions.append(session)

    # 지점별 그룹화
    sessions_by_point = defaultdict(list)
    for session in filtered_sessions:
        sessions_by_point[session.point].append(session)

    points = sorted(sessions_by_point.keys())

    print(f"처리 대상: {len(filtered_sessions)}개 세션 / {len(points)}개 지점")
    if skipped_sessions:
        print(f"  스킵: {len(skipped_sessions)}개")
    print()

    # 추출
    success_count = 0
    fail_count = 0

    # Dry-run 모드
    if args.dry_run:
        for idx, session in enumerate(filtered_sessions, 1):
            point = session.point
            date_str = session.measurement_date.strftime("%Y-%m-%d")
            weekday = get_weekday_kr(session.measurement_date)
            rate_khz = session.sample_rate / 1000

            prefix = f"[{idx}/{len(filtered_sessions)}]"
            info = f"{point} {date_str}({weekday}) @ {rate_khz:.1f}kHz"
            print(f"{prefix} {info} {colorize('→ SKIP (dry-run)', Colors.DIM)}")
            success_count += 1

    # 병렬 처리 모드
    elif workers > 1 and len(points) > 1:
        print(colorize(f"[병렬 처리 시작] {len(points)}개 지점 × {workers} workers", Colors.CYAN))
        print()

        # 작업 준비
        tasks = [
            (point, sessions_by_point[point], output_path, location)
            for point in points
        ]

        # 병렬 실행
        with ProcessPoolExecutor(max_workers=min(workers, len(points))) as executor:
            futures = {executor.submit(process_point_sessions, task): task[0] for task in tasks}

            for future in as_completed(futures):
                point = futures[future]
                try:
                    result = future.result()
                    success_count += result['success_count']
                    fail_count += result['fail_count']

                    # 결과 출력
                    status = colorize("OK", Colors.GREEN) if result['fail_count'] == 0 else colorize("FAIL", Colors.RED)
                    sessions_done = result['success_count'] + result['fail_count']
                    print(f"  {point}: {status} ({result['success_count']}/{sessions_done} sessions)")

                except Exception as e:
                    print(colorize(f"  {point}: ERROR - {e}", Colors.RED))
                    fail_count += len(sessions_by_point[point])

    # 순차 처리 모드
    else:
        for idx, session in enumerate(filtered_sessions, 1):
            point = session.point
            date_str = session.measurement_date.strftime("%Y-%m-%d")
            weekday = get_weekday_kr(session.measurement_date)
            rate_khz = session.sample_rate / 1000

            prefix = f"[{idx}/{len(filtered_sessions)}]"
            info = f"{point} {date_str}({weekday}) @ {rate_khz:.1f}kHz"

            print(f"{prefix} {info}", end=" ", flush=True)

            try:
                # 출력 폴더 생성
                session_output = create_session_folder(
                    output_path,
                    location,
                    session.point,
                    session.measurement_date,
                )

                if session_output is None:
                    print(colorize("→ SKIP (이미 존재)", Colors.YELLOW))
                    continue

                # 프로세서 생성 (세션별 샘플레이트)
                processor = FusionProcessor(
                    measurement_date=session.measurement_date,
                    sample_rate=session.sample_rate,
                )

                # 변환
                result = processor.process(
                    session.source_path,
                    session_output,
                )

                if result.success:
                    print(colorize(f"→ OK ({result.files_processed} files)", Colors.GREEN))
                    success_count += 1
                else:
                    print(colorize(f"→ FAIL: {result.message}", Colors.RED))
                    fail_count += 1

            except Exception as e:
                print(colorize(f"→ ERROR: {e}", Colors.RED))
                fail_count += 1

    # 스킵된 세션 표시
    if skipped_sessions and not args.quiet:
        print(colorize("\n[스킵된 세션]", Colors.DIM))
        for session, reason in skipped_sessions:
            date_str = session.measurement_date.strftime("%Y-%m-%d")
            print(colorize(f"  {session.point} {date_str}: {reason}", Colors.DIM))

    # 결과 요약
    print(colorize(f"\n[완료]", Colors.BOLD))
    print(f"  성공: {colorize(str(success_count), Colors.GREEN)}")
    if fail_count:
        print(f"  실패: {colorize(str(fail_count), Colors.RED)}")
    if skipped_sessions:
        print(f"  스킵: {colorize(str(len(skipped_sessions)), Colors.DIM)}")

    print()
    return 0 if fail_count == 0 else 1


def main():
    global _use_color

    parser = argparse.ArgumentParser(
        description="MNC Audio Organizer CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 스캔
  python main_cli.py scan /media/joonwon/대구비행장/01_원본데이터

  # 추출
  python main_cli.py extract /media/joonwon/대구비행장/01_원본데이터 \\
      --location 대구비행장 \\
      --output /mnt/audio_archive/raw_audio

  # 주말/부분 제외
  python main_cli.py extract /path/to/source \\
      --location 사이트명 \\
      --output /path/to/output \\
      --exclude-weekend \\
      --exclude-partial

  # 미리보기
  python main_cli.py extract /path/to/source \\
      --location 사이트명 \\
      --output /path/to/output \\
      --dry-run

  # 색상 없이 (파이프/로그용)
  python main_cli.py --no-color scan /path/to/source
        """
    )

    # 공통 옵션
    parser.add_argument("--no-color", action="store_true", help="색상 출력 비활성화")

    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # scan 명령어
    scan_parser = subparsers.add_parser("scan", help="세션 목록 스캔")
    scan_parser.add_argument("source", help="소스 폴더 경로")

    # extract 명령어
    extract_parser = subparsers.add_parser("extract", help="오디오 추출 (자체 폴더 구조)")
    extract_parser.add_argument("source", help="소스 폴더 경로")
    extract_parser.add_argument("--location", "-l", required=True, help="위치명 (예: 대구비행장)")
    extract_parser.add_argument("--output", "-o", required=True, help="출력 폴더 경로")
    extract_parser.add_argument("--exclude-weekend", action="store_true", help="주말 제외")
    extract_parser.add_argument("--exclude-partial", action="store_true", help="부분 데이터 제외")
    extract_parser.add_argument("--dry-run", action="store_true", help="실제 추출 없이 확인만")
    extract_parser.add_argument("--quiet", "-q", action="store_true", help="스킵 세션 상세 출력 안함")
    extract_parser.add_argument("--workers", "-w", type=int, default=1,
                               help="병렬 처리 워커 수 (0=자동, 기본=1 순차)")

    # extract-to-main 명령어 (메인시스템 세션 폴더에 추출)
    extract_main_parser = subparsers.add_parser(
        "extract-to-main",
        help="메인시스템 세션 폴더에 오디오 추출 (권장)"
    )
    extract_main_parser.add_argument("source", help="소스 폴더 경로 (BID 파일 위치)")
    extract_main_parser.add_argument("--output", "-o", required=True,
                                     help="출력 폴더 경로 (메인시스템 위치 폴더, 예: /mnt/audio_archive/upload_drop/대구비행장)")
    extract_main_parser.add_argument("--include-weekend", action="store_true", help="주말 포함 (기본: 주말 제외)")
    extract_main_parser.add_argument("--exclude-partial", action="store_true", help="부분 데이터 제외")
    extract_main_parser.add_argument("--workers", "-w", type=int, default=10,
                                     help="병렬 처리 워커 수 (기본=10)")

    args = parser.parse_args()

    # --no-color 처리
    if args.no_color:
        _use_color = False

    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "extract":
        return cmd_extract(args)
    elif args.command == "extract-to-main":
        return cmd_extract_to_main(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
