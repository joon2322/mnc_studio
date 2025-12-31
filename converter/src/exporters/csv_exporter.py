"""CSV 출력 모듈"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def export_to_csv(df: pd.DataFrame, output_path: Path) -> bool:
    """
    DataFrame을 CSV 파일로 저장

    Args:
        df: 저장할 DataFrame (86,400행)
        output_path: 출력 파일 경로

    Returns:
        성공 여부
    """
    try:
        # 부모 디렉토리 생성
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # CSV 저장 (UTF-8 BOM for Excel compatibility)
        df.to_csv(
            output_path,
            index=False,
            encoding='utf-8-sig'
        )

        logger.info(f"CSV 저장: {output_path}")
        return True

    except Exception as e:
        logger.error(f"CSV 저장 실패: {output_path} - {e}")
        return False
