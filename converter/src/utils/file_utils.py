"""파일/폴더 처리 유틸리티"""

import re
from datetime import datetime
from typing import Tuple, Optional
from .date_utils import WEEKDAY_KR


def parse_point_folder(folder_name: str) -> Tuple[str, str]:
    """
    지점 폴더명 파싱

    지원 형식:
        - N01 첨단휴먼시아  → N-1, 첨단휴먼시아
        - N-1              → N-1, ''
        - N1               → N-1, ''
        - N-3_fusion       → N-3, fusion
        - 이동식 N01 효성  → 이동식1, 효성

    Args:
        folder_name: 폴더명

    Returns:
        (point_id, point_name) 튜플
    """
    # 이동식 지점: "이동식 N01 지점명", "이동식 01 지점명", "이동식N01"
    mobile_match = re.match(r'이동식[\s_]*N?-?(\d+)[\s_]*(.*)', folder_name)
    if mobile_match:
        num = int(mobile_match.group(1))
        name = mobile_match.group(2).strip()
        return f'이동식{num}', name

    # 일반 지점: "N01", "N-1", "N1", "N01 지점명", "N-3_fusion"
    # 패턴: N + 선택적 하이픈 + 숫자 + 선택적 구분자(공백/_) + 나머지
    normal_match = re.match(r'N-?(\d+)[\s_]*(.*)', folder_name)
    if normal_match:
        num = int(normal_match.group(1))
        name = normal_match.group(2).strip()
        return f'N-{num}', name

    # 매칭 실패 시 원본 반환
    return folder_name, ''


def generate_filename(
    site_name: str,
    point_id: str,
    date: datetime,
    weighting: str,
    round_number: Optional[str] = None
) -> str:
    """
    출력 파일명 생성 (CLAUDE.md 규칙 준수)

    형식: {위치}_{차수}_{지점}_{측정일자}_{요일}_{가중치}

    Args:
        site_name: 사이트명 (예: 광주비행장)
        point_id: 지점 ID (예: N-1, 이동식1)
        date: 측정일
        weighting: 가중치 (LAS, LCS)
        round_number: 차수 (예: "1차", None이면 생략)

    Returns:
        파일명 (확장자 제외)
        예: 광주비행장_1차_N-1_20251127_목_LAS
    """
    weekday = WEEKDAY_KR[date.weekday()]
    date_str = date.strftime('%Y%m%d')

    parts = [site_name]
    if round_number:
        parts.append(round_number)
    parts.extend([point_id, date_str, weekday, weighting])

    return '_'.join(parts)
