"""Rion 장비 (.rnd) 파서

지원 장비: NX-42RT
파일 형식: CSV (첫 줄 "CSV" 스킵)
폴더 구조: Auto_*/AUTO_LP/ 또는 직접 AUTO_LP/
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from .base_parser import BaseParser
from ..utils.round_utils import round_half_up


class RionParser(BaseParser):
    """Rion NX-42RT 장비 파서"""

    # 지원 장비 모델 접두사
    SUPPORTED_PREFIXES = ['NL-', 'NX-']

    # 주파수 컬럼 매핑 (Rion CSV → 표준)
    FREQ_MAPPING = {
        '12.5 Hz': '12.5Hz', '16 Hz': '16Hz', '20 Hz': '20Hz',
        '25 Hz': '25Hz', '31.5 Hz': '31.5Hz', '40 Hz': '40Hz',
        '50 Hz': '50Hz', '63 Hz': '63Hz', '80 Hz': '80Hz',
        '100 Hz': '100Hz', '125 Hz': '125Hz', '160 Hz': '160Hz',
        '200 Hz': '200Hz', '250 Hz': '250Hz', '315 Hz': '315Hz',
        '400 Hz': '400Hz', '500 Hz': '500Hz', '630 Hz': '630Hz',
        '800 Hz': '800Hz', '1 kHz': '1000Hz', '1.25 kHz': '1250Hz',
        '1.6 kHz': '1600Hz', '2 kHz': '2000Hz', '2.5 kHz': '2500Hz',
        '3.15 kHz': '3150Hz', '4 kHz': '4000Hz', '5 kHz': '5000Hz',
        '6.3 kHz': '6300Hz', '8 kHz': '8000Hz', '10 kHz': '10000Hz',
        '12.5 kHz': '12500Hz', '16 kHz': '16000Hz', '20 kHz': '20000Hz',
    }

    # 인코딩 fallback 순서
    ENCODINGS = ['utf-8', 'utf-8-sig', 'cp949']

    def detect(self, folder_path: Path) -> bool:
        """
        Rion 장비 폴더 감지

        Args:
            folder_path: 확인할 폴더 경로

        Returns:
            Rion 장비 폴더면 True
        """
        try:
            for child in folder_path.iterdir():
                if child.is_dir():
                    if any(child.name.startswith(p) for p in self.SUPPORTED_PREFIXES):
                        return True
        except PermissionError:
            pass
        return False

    def find_auto_lp_folders(self, device_folder: Path) -> List[Path]:
        """
        AUTO_LP 폴더들 찾기

        지원 구조:
        1. device_folder/Auto_*/AUTO_LP/
        2. device_folder/AUTO_LP/ (직접)

        Args:
            device_folder: 장비 폴더 경로

        Returns:
            AUTO_LP 폴더 목록
        """
        lp_folders = []

        # 구조 1: Auto_*/AUTO_LP/
        try:
            for auto_folder in device_folder.glob('Auto_*'):
                lp_folder = auto_folder / 'AUTO_LP'
                if lp_folder.exists() and lp_folder.is_dir():
                    lp_folders.append(lp_folder)
        except PermissionError:
            pass

        # 구조 2: 직접 AUTO_LP/
        direct_lp = device_folder / 'AUTO_LP'
        if direct_lp.exists() and direct_lp.is_dir():
            if direct_lp not in lp_folders:
                lp_folders.append(direct_lp)

        return lp_folders

    def _read_csv_with_fallback(self, file_path: Path) -> pd.DataFrame:
        """
        인코딩 fallback으로 CSV 읽기

        Args:
            file_path: CSV 파일 경로

        Returns:
            DataFrame

        Raises:
            ValueError: 모든 인코딩 실패 시
        """
        last_error = None

        for encoding in self.ENCODINGS:
            try:
                df = pd.read_csv(file_path, skiprows=1, skipinitialspace=True, encoding=encoding)
                return df
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue

        raise ValueError(f"모든 인코딩 실패: {file_path.name} - {last_error}")

    def read_rnd_file(self, file_path: Path, weighting: str = 'LAS',
                      include_bands: bool = True) -> pd.DataFrame:
        """
        .rnd 파일 읽기

        형식: CSV, 첫 줄 "CSV" 스킵

        Args:
            file_path: .rnd 파일 경로
            weighting: 가중치 ('LAS'=Main, 'LCS'=Sub)
            include_bands: 주파수 밴드 포함 여부

        Returns:
            DataFrame with timestamp, spl, [frequency bands]
        """
        # CSV 읽기 (인코딩 fallback)
        df = self._read_csv_with_fallback(file_path)
        df.columns = df.columns.str.strip()

        if 'Start Time' not in df.columns:
            raise ValueError(f"Start Time 컬럼 없음: {file_path.name}")

        # 시간 파싱 + 초 단위 정규화
        df['timestamp'] = pd.to_datetime(df['Start Time'])
        df['timestamp'] = df['timestamp'].dt.floor('s')

        # spl 컬럼 선택
        # 정책:
        # - LAS 요청: Main → Leq fallback (Leq는 보통 A-weighted)
        # - LCS 요청: Sub 필수 (Leq fallback 없음, C-weighted 데이터가 아니므로)
        if weighting == 'LAS':
            if 'Main' in df.columns:
                spl_col = 'Main'
            elif 'Leq' in df.columns:
                spl_col = 'Leq'  # A-weighting fallback
            else:
                raise ValueError(f"A-weighting(Main/Leq) 컬럼 없음: {file_path.name}")
        elif weighting == 'LCS':
            if 'Sub' in df.columns:
                spl_col = 'Sub'
            else:
                # LCS 요청 시 Sub 없으면 명확한 에러 (Leq fallback 안함)
                raise ValueError(f"C-weighting(Sub) 컬럼 없음 - 이 데이터는 A-weighting만 측정됨: {file_path.name}")
        else:
            raise ValueError(f"지원하지 않는 가중치: {weighting}")

        # SPL 변환 + 반올림
        df['spl'] = pd.to_numeric(df[spl_col].astype(str).str.strip(), errors='coerce')
        df['spl'] = df['spl'].apply(lambda x: round_half_up(x, 1) if pd.notna(x) else x)

        result_cols = ['timestamp', 'spl']

        # 주파수 밴드 변환
        if include_bands:
            for rion_col, std_col in self.FREQ_MAPPING.items():
                if rion_col in df.columns:
                    df[std_col] = pd.to_numeric(df[rion_col], errors='coerce')
                    df[std_col] = df[std_col].apply(
                        lambda x: round_half_up(x, 1) if pd.notna(x) else x
                    )
                    result_cols.append(std_col)

        return df[result_cols]

    def find_device_folders(self, point_folder: Path) -> List[Path]:
        """
        지점 폴더 내 장비 폴더 찾기

        Args:
            point_folder: 지점 폴더

        Returns:
            장비 폴더 목록
        """
        device_folders = []
        try:
            for child in point_folder.iterdir():
                if child.is_dir():
                    if any(child.name.startswith(p) for p in self.SUPPORTED_PREFIXES):
                        device_folders.append(child)
        except PermissionError:
            pass
        return device_folders

    def process(self, device_folder: Path, weighting: str = 'LAS',
                include_bands: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Rion 장비 데이터 처리

        중요: AUTO_LP 폴더만 사용 (AUTO_LEQ 사용 금지)

        Args:
            device_folder: 장비 폴더 경로 (예: .../NX-42RT/)
            weighting: 가중치 ('LAS' 또는 'LCS')
            include_bands: 주파수 밴드 포함 여부

        Returns:
            {날짜문자열: DataFrame} 딕셔너리
        """
        results = {}

        # AUTO_LP 폴더 찾기
        lp_folders = self.find_auto_lp_folders(device_folder)
        if not lp_folders:
            self.log_warning(f"AUTO_LP 폴더 없음: {device_folder}")
            return results

        # 모든 .rnd 파일 읽기
        all_data = []
        lcs_warning_logged = False  # LCS 경고 1회만 출력

        for lp_folder in lp_folders:
            # .rnd, .CSV, .csv 파일 모두 검색
            rnd_files = list(lp_folder.glob('*.rnd')) + \
                        list(lp_folder.glob('*.CSV')) + \
                        list(lp_folder.glob('*.csv'))

            for rnd_file in rnd_files:
                try:
                    df = self.read_rnd_file(rnd_file, weighting, include_bands)
                    all_data.append(df)
                    self.log_info(f"읽기 완료: {rnd_file.name} ({len(df)}행)")
                except ValueError as e:
                    error_msg = str(e)
                    # LCS 관련 에러는 폴더당 1회만 경고
                    if "C-weighting(Sub)" in error_msg and not lcs_warning_logged:
                        self.log_warning(f"이 Rion 데이터는 C-weighting(Sub) 컬럼이 없어 LCS 변환을 건너뜁니다.")
                        lcs_warning_logged = True
                    elif "C-weighting(Sub)" not in error_msg:
                        self.log_warning(f"파일 읽기 실패: {rnd_file.name} - {e}")
                except Exception as e:
                    self.log_warning(f"파일 읽기 실패: {rnd_file.name} - {e}")

        if not all_data:
            self.log_warning(f"읽은 데이터 없음: {device_folder}")
            return results

        # 병합 + 중복 제거 (마지막 값 유지 - Fusion과 정책 통일)
        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values('timestamp', kind='stable').drop_duplicates(subset='timestamp', keep='last')

        self.log_info(f"병합 완료: 총 {len(combined)}행")

        # 날짜별 분리
        combined['date_key'] = combined['timestamp'].dt.strftime('%Y%m%d')

        for date_key, group in combined.groupby('date_key'):
            date = datetime.strptime(date_key, '%Y%m%d')
            full_df = self.create_full_day_df(date, include_bands)

            # 데이터 삽입
            for _, row in group.iterrows():
                ts = row['timestamp']
                idx = ts.hour * 3600 + ts.minute * 60 + ts.second
                if 0 <= idx < 86400:
                    full_df.loc[idx, 'spl'] = row['spl']
                    # 주파수 밴드 복사
                    if include_bands:
                        for col in group.columns:
                            if col not in ['timestamp', 'spl', 'date_key'] and col in full_df.columns:
                                full_df.loc[idx, col] = row[col]

            # 결과 저장
            valid_count = full_df['spl'].notna().sum()
            self.log_info(f"{date_key}: {valid_count}/86400 데이터")
            results[date_key] = full_df

        return results
