"""
지점명 정규화 유틸리티

모든 장비(Fusion, Rion)에서 동일한 정규화 로직 사용
"""

import re


def normalize_point_name(point: str) -> str:
    """
    지점명 정규화 (메인시스템 형식으로 변환)

    규칙:
        - N01, N1, N-1 → N-1
        - N10, N-10 → N-10
        - 이동식 N-1, 이동식N1, 이동식1, 이동식-1 → 이동식-1
        - 이동식 N-10, 이동식10 → 이동식-10

    Args:
        point: 원본 지점명

    Returns:
        정규화된 지점명
    """
    name = point.strip()

    # 이동식 패턴: 이동식 N-1, 이동식N1, 이동식1, 이동식-1 등
    # 공백, N, 하이픈 모두 선택적
    match = re.match(r'이동식\s*N?-?0*(\d+)', name, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        return f"이동식-{num}"

    # N 패턴: N01, N1, N-1, N10, N-10 등
    match = re.match(r'N[-]?0*(\d+)', name, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        return f"N-{num}"

    # 기타는 그대로
    return name


def extract_point_from_folder(folder_name: str) -> str:
    """
    폴더명에서 지점명 추출 및 정규화

    Args:
        folder_name: 폴더명 (예: "N-1", "이동식 N-1", "N01 지점명")

    Returns:
        정규화된 지점명
    """
    name = folder_name.strip()

    # 이동식 패턴
    match = re.match(r'(이동식\s*N?-?\d+)', name, re.IGNORECASE)
    if match:
        return normalize_point_name(match.group(1))

    # N 패턴 (뒤에 공백+설명이 있을 수 있음)
    match = re.match(r'(N[-]?0*\d+)', name, re.IGNORECASE)
    if match:
        return normalize_point_name(match.group(1))

    # 매칭 안되면 전체 정규화 시도
    return normalize_point_name(name)


def point_sort_key(point: str) -> int:
    """
    지점명 정렬 키 (숫자 순서: N-1, N-2, ..., N-10, 이동식-1, ...)

    Args:
        point: 지점명

    Returns:
        정렬 키 (정수)
    """
    # 정규화 후 숫자 추출
    normalized = normalize_point_name(point)

    match = re.search(r'(\d+)', normalized)
    num = int(match.group(1)) if match else 0

    # 이동식은 1000 이상으로
    if normalized.startswith('이동식'):
        return 1000 + num
    else:
        return num
