"""CSV 출력 모듈 (검증용)"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from ..utils.file_utils import generate_filename


class CSVExporter:
    """CSV 파일 출력 (검증용)"""

    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: 출력 디렉토리
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        df: pd.DataFrame,
        site_name: str,
        point_id: str,
        date: datetime,
        weighting: str,
        round_number: str = None
    ) -> Path:
        """
        DataFrame을 CSV 파일로 저장

        Args:
            df: 저장할 DataFrame
            site_name: 사이트명
            point_id: 지점 ID
            date: 측정일
            weighting: 가중치 (LAS, LCS)
            round_number: 차수 (선택적)

        Returns:
            저장된 파일 경로
        """
        filename = generate_filename(
            site_name, point_id, date, weighting, round_number
        )
        output_path = self.output_dir / f"{filename}.csv"

        # CSV 저장 (한글 호환을 위해 utf-8-sig 사용)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        return output_path

    def export_batch(
        self,
        data_dict: Dict[str, pd.DataFrame],
        site_name: str,
        point_id: str,
        weighting: str,
        round_number: str = None
    ) -> List[Path]:
        """
        여러 날짜 데이터 일괄 저장

        Args:
            data_dict: {날짜문자열: DataFrame}
            site_name: 사이트명
            point_id: 지점 ID
            weighting: 가중치
            round_number: 차수 (선택적)

        Returns:
            저장된 파일 경로 목록
        """
        saved_files = []

        for date_key, df in sorted(data_dict.items()):
            date = datetime.strptime(date_key, '%Y%m%d')
            path = self.export(df, site_name, point_id, date, weighting, round_number)
            saved_files.append(path)

        return saved_files
