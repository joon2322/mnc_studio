"""Fusion 장비 (.bid) 파서

지원 장비: N2xx, N3xx, N4xx 시리즈
파일 형식: int16 little-endian, 값 = dB * 100
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from .base_parser import BaseParser
from ..utils.round_utils import round_half_up
from ..config import FREQUENCY_COLUMNS


class FusionParser(BaseParser):
    """Fusion 장비 (N2xx, N3xx, N4xx) 파서"""

    # 지원 장비 모델 접두사
    SUPPORTED_PREFIXES = ['N2', 'N3', 'N4']

    # OctLeq3.bid 밴드 매핑 (36밴드 중 인덱스 3~35가 12.5Hz~20kHz)
    OCT_BAND_START_INDEX = 3  # 처음 3개는 추가 정보 (Leq, Lmax 등)
    OCT_BAND_COUNT = 33       # 12.5Hz ~ 20kHz

    def detect(self, folder_path: Path) -> bool:
        """
        Fusion 장비 폴더 감지

        감지 우선순위:
            1. N2xx/N3xx/N4xx 하위 폴더 존재
            2. YYYYMMDD_* 날짜 폴더에 LASeq.bid 또는 LCSeq.bid 존재

        Args:
            folder_path: 확인할 폴더 경로

        Returns:
            Fusion 장비 폴더면 True
        """
        try:
            for child in folder_path.iterdir():
                if child.is_dir():
                    # 1단계: N2xx/N3xx/N4xx 장비 폴더 확인
                    if any(child.name.startswith(p) for p in self.SUPPORTED_PREFIXES):
                        return True
                    # 2단계: 날짜 폴더 + .bid 파일 확인
                    if self._is_fusion_date_folder(child):
                        return True
        except PermissionError:
            pass
        return False

    def _is_fusion_date_folder(self, folder: Path) -> bool:
        """
        Fusion 날짜 폴더인지 확인

        조건:
            - 폴더명이 YYYYMMDD_HHMMSS_HHMMSS 형식
            - LASeq.bid 또는 LCSeq.bid 파일 존재

        Args:
            folder: 확인할 폴더

        Returns:
            Fusion 날짜 폴더면 True
        """
        import re
        # 폴더명 패턴: YYYYMMDD_HHMMSS_HHMMSS
        if not re.match(r'^\d{8}_\d{6}_\d{6}$', folder.name):
            return False

        # LASeq.bid 또는 LCSeq.bid 존재 확인
        try:
            for bid_file in ['LASeq.bid', 'LCSeq.bid']:
                if (folder / bid_file).exists():
                    return True
        except PermissionError:
            pass
        return False

    def read_bid_file(self, file_path: Path) -> np.ndarray:
        """
        .bid 파일 읽기 (SPL용)

        형식: int16 little-endian, 값 = dB * 100

        Args:
            file_path: .bid 파일 경로

        Returns:
            dB 값 배열 (사사오입 반올림 적용)
        """
        data = np.fromfile(file_path, dtype='<i2')  # little-endian int16
        db_values = data.astype(np.float64) / 100.0

        # 사사오입 반올림 (정확성을 위해 개별 적용)
        return np.array([round_half_up(v, 1) for v in db_values])

    def read_octave_file(self, file_path: Path, expected_samples: int = 0) -> np.ndarray:
        """
        OctLeq3.bid 파일 읽기 (옥타브 밴드용)

        형식: int16 little-endian, 36밴드 x N샘플
        밴드 0-2: 추가 정보
        밴드 3-35: 12.5Hz ~ 20kHz (33개)

        Args:
            file_path: OctLeq3.bid 파일 경로
            expected_samples: 예상 샘플 수 (0이면 검증 안함)

        Returns:
            (샘플 수, 33) 형태의 2D 배열 (사사오입 반올림 적용)

        Raises:
            ValueError: 데이터 크기가 36의 배수가 아니거나 예상 샘플 수와 불일치
        """
        data = np.fromfile(file_path, dtype='<i2')

        # 36밴드로 reshape
        total_bands = 36
        if len(data) % total_bands != 0:
            raise ValueError(f"OctLeq3 데이터 크기가 36으로 나누어지지 않음: {len(data)}")

        rows = len(data) // total_bands

        # 샘플 수 검증
        if expected_samples > 0 and rows != expected_samples:
            raise ValueError(f"OctLeq3 샘플 수 불일치: {rows} vs 예상 {expected_samples}")

        reshaped = data.reshape(rows, total_bands)

        # dB 변환
        db_values = reshaped.astype(np.float64) / 100.0

        # 밴드 3~35만 추출 (12.5Hz ~ 20kHz)
        freq_bands = db_values[:, self.OCT_BAND_START_INDEX:self.OCT_BAND_START_INDEX + self.OCT_BAND_COUNT]

        # 사사오입 반올림 (정확성을 위해 개별 적용)
        result = np.zeros_like(freq_bands)
        for i in range(freq_bands.shape[0]):
            for j in range(freq_bands.shape[1]):
                result[i, j] = round_half_up(freq_bands[i, j], 1)

        return result

    def parse_date_folder(self, folder_name: str) -> Tuple[datetime, Tuple[int, int, int], Tuple[int, int, int]]:
        """
        폴더명 파싱

        폴더명 형식: YYYYMMDD_HHMMSS_HHMMSS
        예: 20251127_130356_000000

        Args:
            folder_name: 폴더명

        Returns:
            (date, start_time, end_time) 튜플
            - date: datetime 객체 (날짜만)
            - start_time: (시, 분, 초) 튜플
            - end_time: (시, 분, 초) 튜플
        """
        parts = folder_name.split('_')
        date = datetime.strptime(parts[0], '%Y%m%d')

        start_str = parts[1]
        end_str = parts[2]

        start = (int(start_str[:2]), int(start_str[2:4]), int(start_str[4:6]))
        end = (int(end_str[:2]), int(end_str[2:4]), int(end_str[4:6]))

        return date, start, end

    def find_device_folders(self, point_folder: Path) -> List[Path]:
        """
        지점 폴더 내 장비 폴더 찾기

        감지 우선순위:
            1. N2xx/N3xx/N4xx 하위 폴더
            2. 지점 폴더 자체 (날짜 폴더가 직접 있는 경우)

        Args:
            point_folder: 지점 폴더

        Returns:
            장비 폴더 목록
        """
        device_folders = []
        has_date_folders = False

        try:
            for child in point_folder.iterdir():
                if child.is_dir():
                    # 1단계: N2xx/N3xx/N4xx 장비 폴더
                    if any(child.name.startswith(p) for p in self.SUPPORTED_PREFIXES):
                        device_folders.append(child)
                    # 2단계: 날짜 폴더 확인 (직접 구조)
                    elif self._is_fusion_date_folder(child):
                        has_date_folders = True
        except PermissionError:
            pass

        # 장비 폴더가 없고 날짜 폴더가 직접 있으면 지점 폴더 자체를 반환
        if not device_folders and has_date_folders:
            device_folders.append(point_folder)

        return device_folders

    def process(self, device_folder: Path, weighting: str = 'LAS',
                include_bands: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Fusion 장비 데이터 처리

        Args:
            device_folder: 장비 폴더 경로 (예: .../N214/)
            weighting: 가중치 ('LAS' 또는 'LCS')
            include_bands: 옥타브 밴드 포함 여부

        Returns:
            {날짜문자열: DataFrame} 딕셔너리
        """
        results = {}

        # 파일명 결정 (항상 Leq 모드)
        bid_filename = f'{weighting}eq.bid'  # LASeq.bid, LCSeq.bid
        oct_filename = 'OctLeq3.bid'

        # 날짜 폴더 수집 (숫자로 시작하는 폴더)
        date_folders = []
        try:
            date_folders = sorted([
                d for d in device_folder.iterdir()
                if d.is_dir() and d.name[0].isdigit()
            ])
        except PermissionError:
            self.log_error(f"폴더 접근 실패: {device_folder}")
            return results

        # 날짜별 그룹핑 (같은 날짜에 여러 세션 가능)
        date_groups: Dict[str, List] = {}
        for folder in date_folders:
            try:
                date, start, end = self.parse_date_folder(folder.name)
                date_key = date.strftime('%Y%m%d')

                if date_key not in date_groups:
                    date_groups[date_key] = []
                date_groups[date_key].append((folder, date, start, end))
            except Exception as e:
                self.log_warning(f"폴더 파싱 실패: {folder.name} - {e}")

        # 날짜별 처리
        for date_key in sorted(date_groups.keys()):
            sessions = date_groups[date_key]
            date = sessions[0][1]

            full_df = self.create_full_day_df(date, include_bands)

            for folder, _, start_time, _ in sessions:
                bid_file = folder / bid_filename
                oct_file = folder / oct_filename

                if not bid_file.exists():
                    self.log_warning(f"파일 없음: {bid_file.name} in {folder.name}")
                    continue

                try:
                    # SPL 데이터 읽기
                    db_values = self.read_bid_file(bid_file)

                    # 옥타브 밴드 읽기 (옵션)
                    oct_values = None
                    if include_bands:
                        if oct_file.exists():
                            try:
                                oct_values = self.read_octave_file(oct_file, len(db_values))
                                if oct_values.shape[0] != len(db_values):
                                    self.log_warning(f"옥타브 밴드 크기 불일치: {oct_values.shape[0]} vs {len(db_values)}")
                                    oct_values = None
                            except Exception as e:
                                self.log_warning(f"옥타브 밴드 읽기 실패: {e}")
                                oct_values = None
                        else:
                            self.log_warning(f"OctLeq3 파일 없음: {folder.name}")

                    # 시작 시간
                    start_dt = date.replace(
                        hour=start_time[0],
                        minute=start_time[1],
                        second=start_time[2]
                    )

                    # 데이터 삽입
                    for i, val in enumerate(db_values):
                        ts = start_dt + timedelta(seconds=i)
                        if ts.date() == date.date():
                            idx = ts.hour * 3600 + ts.minute * 60 + ts.second
                            if 0 <= idx < 86400:
                                full_df.loc[idx, 'spl'] = val

                                # 옥타브 밴드 삽입
                                if oct_values is not None and i < oct_values.shape[0]:
                                    for j, freq_col in enumerate(FREQUENCY_COLUMNS):
                                        if j < oct_values.shape[1]:
                                            full_df.loc[idx, freq_col] = oct_values[i, j]

                except Exception as e:
                    self.log_error(f"파일 처리 실패: {bid_file} - {e}")

            # 결과 저장
            valid_count = full_df['spl'].notna().sum()
            band_info = ""
            if include_bands:
                band_valid = full_df['12.5Hz'].notna().sum()
                band_info = f", 밴드: {band_valid}"
            self.log_info(f"{date_key}: {valid_count}/86400 데이터{band_info}")
            results[date_key] = full_df

        return results
