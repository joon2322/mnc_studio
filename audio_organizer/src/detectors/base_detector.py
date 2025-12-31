"""Base detector class"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional


@dataclass
class AudioSession:
    """오디오 세션 정보"""
    point: str                          # 지점명 (N-1, N-2, 이동식1 등)
    equipment_type: str                 # 장비 유형 (fusion, rion)
    measurement_date: date              # 측정일
    source_path: Path                   # 원본 경로
    source_files: List[Path] = field(default_factory=list)  # 원본 파일 목록
    file_count: int = 0                 # 파일 수
    total_bytes: int = 0                # 총 용량
    expected_count: int = 0             # 예상 파일 수
    valid_count: int = 0                # 유효 파일 수
    warning_count: int = 0              # 경고 파일 수
    skip_count: int = 0                 # 스킵 파일 수

    @property
    def status(self) -> str:
        """세션 상태"""
        if self.skip_count > 0:
            return "일부 스킵"
        if self.expected_count > 0 and self.file_count < self.expected_count:
            return "부분"
        if self.warning_count > 0:
            return "경고"
        return "정상"


class BaseDetector(ABC):
    """장비 감지 베이스 클래스"""

    @abstractmethod
    def detect(self, folder_path: Path) -> bool:
        """폴더가 해당 장비 유형인지 감지"""
        pass

    @abstractmethod
    def scan(self, folder_path: Path) -> List[AudioSession]:
        """폴더에서 오디오 세션 스캔"""
        pass

    @abstractmethod
    def extract_point(self, folder_path: Path) -> Optional[str]:
        """폴더 경로에서 지점명 추출"""
        pass
