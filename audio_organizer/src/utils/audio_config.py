"""Fusion 오디오 설정 파싱"""

import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 기본 샘플레이트
DEFAULT_SAMPLE_RATE = 25600


def get_sampling_frequency(session_path: Path) -> int:
    """
    세션의 샘플레이트 읽기

    Fusion 장비의 settings/configuration/*.xml에서
    <SamplingFrequency> 값을 파싱합니다.

    여러 XML 파일이 있을 경우 최신 수정 시간 파일을 우선합니다.

    Args:
        session_path: 세션 폴더 경로 (예: .../20251124_000000_000000/)

    Returns:
        샘플레이트 (Hz), 기본값 25600
    """
    config_dir = session_path / "settings" / "configuration"

    if not config_dir.exists():
        logger.debug(f"설정 폴더 없음, 기본값 사용: {session_path.name}")
        return DEFAULT_SAMPLE_RATE

    # XML 파일 목록 (최신 수정 시간 순으로 정렬)
    xml_files: List[Path] = list(config_dir.glob("*.xml"))
    if not xml_files:
        logger.debug(f"XML 파일 없음, 기본값 사용: {session_path.name}")
        return DEFAULT_SAMPLE_RATE

    xml_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    for xml_file in xml_files:
        try:
            sample_rate = _parse_xml_sample_rate(xml_file)
            if sample_rate:
                logger.debug(f"샘플레이트 감지: {sample_rate} Hz ({xml_file.name})")
                return sample_rate
        except Exception as e:
            logger.warning(f"XML 파싱 실패: {xml_file.name} - {e}")
            continue

    logger.debug(f"샘플레이트 미발견, 기본값 사용: {session_path.name}")
    return DEFAULT_SAMPLE_RATE


def _parse_xml_sample_rate(xml_file: Path) -> Optional[int]:
    """
    XML 파일에서 SamplingFrequency 파싱

    Args:
        xml_file: XML 파일 경로

    Returns:
        샘플레이트 (Hz) 또는 None
    """
    content = xml_file.read_bytes()

    # 인코딩 감지 및 디코딩
    text = _decode_xml_content(content)

    # <SamplingFrequency>25.6</SamplingFrequency> 패턴 찾기
    # 공백/개행 허용: <SamplingFrequency> 25.6 </SamplingFrequency>
    match = re.search(
        r'<SamplingFrequency>\s*([\d.]+)\s*</SamplingFrequency>',
        text,
        re.IGNORECASE
    )

    if match:
        freq_khz = float(match.group(1))
        return int(freq_khz * 1000)  # kHz → Hz

    return None


def _decode_xml_content(content: bytes) -> str:
    """
    XML 바이트를 문자열로 디코딩

    지원 인코딩:
    - UTF-16 LE BOM (\\xff\\xfe)
    - UTF-16 BE BOM (\\xfe\\xff)
    - UTF-8 BOM (\\xef\\xbb\\xbf)
    - UTF-8 (기본)

    Args:
        content: XML 파일 바이트

    Returns:
        디코딩된 문자열
    """
    # UTF-16 LE BOM
    if content[:2] == b'\xff\xfe':
        return content.decode('utf-16-le')

    # UTF-16 BE BOM
    if content[:2] == b'\xfe\xff':
        return content.decode('utf-16-be')

    # UTF-8 BOM
    if content[:3] == b'\xef\xbb\xbf':
        return content[3:].decode('utf-8', errors='replace')

    # UTF-8 (기본)
    return content.decode('utf-8', errors='replace')


def format_sample_rate(sample_rate: int) -> str:
    """
    샘플레이트를 표시용 문자열로 변환

    Args:
        sample_rate: 샘플레이트 (Hz)

    Returns:
        표시용 문자열 (예: "25.6k")
    """
    if sample_rate >= 1000:
        return f"{sample_rate / 1000:.1f}k"
    return f"{sample_rate}"
