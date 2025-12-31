"""오디오 처리 베이스 클래스"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """처리 결과"""
    success: bool
    input_path: Path
    output_path: Optional[Path] = None
    message: str = ""
    files_processed: int = 0
    files_failed: int = 0
    errors: List[str] = field(default_factory=list)


class BaseProcessor(ABC):
    """오디오 처리기 베이스 클래스"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def process(
        self,
        input_path: Path,
        output_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> ProcessingResult:
        """
        오디오 처리 실행

        Args:
            input_path: 입력 경로
            output_path: 출력 경로
            progress_callback: 진행 콜백 (current, total, message)

        Returns:
            ProcessingResult
        """
        pass

    @abstractmethod
    def get_output_filename(self, input_file: Path) -> str:
        """출력 파일명 생성"""
        pass
