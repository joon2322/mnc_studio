"""Parquet 출력 모듈"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def export_to_parquet(df: pd.DataFrame, output_path: Path) -> bool:
    """
    DataFrame을 Parquet 파일로 저장

    Args:
        df: 저장할 DataFrame (86,400행)
        output_path: 출력 파일 경로

    Returns:
        성공 여부
    """
    try:
        # 부모 디렉토리 생성
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Parquet 저장
        df.to_parquet(
            output_path,
            engine='pyarrow',
            index=False,
            compression='snappy'
        )

        logger.info(f"Parquet 저장: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Parquet 저장 실패: {output_path} - {e}")
        return False
