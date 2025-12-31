"""MNC Audio Organizer v1.0 - PyQt6 GUI"""

import logging
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import APP_NAME, APP_VERSION, DEFAULT_OUTPUT_BASE, WEEKDAY_KR
from .detectors import AudioSession, FusionDetector
from .processors import FusionProcessor
from .utils import create_manifest, create_session_folder

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessingThread(QThread):
    """백그라운드 처리 스레드"""

    progress = pyqtSignal(int, int, str)  # current, total, message
    session_complete = pyqtSignal(int, bool, str)  # session_idx, success, message
    finished_all = pyqtSignal(int, int)  # success_count, fail_count

    def __init__(
        self,
        sessions: List[AudioSession],
        output_base: Path,
        location: str,
    ):
        super().__init__()
        self.sessions = sessions
        self.output_base = output_base
        self.location = location
        self._is_cancelled = False

    def run(self):
        """처리 실행"""
        success_count = 0
        fail_count = 0
        total_sessions = len(self.sessions)

        for idx, session in enumerate(self.sessions):
            if self._is_cancelled:
                break

            self.progress.emit(idx + 1, total_sessions, f"처리 중: {session.point}")

            try:
                # 세션 폴더 생성
                session_path = create_session_folder(
                    self.output_base,
                    self.location,
                    session.point,
                    session.measurement_date,
                )

                if session_path is None:
                    # 이미 존재하는 경우 스킵
                    self.session_complete.emit(idx, False, "폴더 이미 존재")
                    fail_count += 1
                    continue

                # 프로세서 생성 및 실행
                processor = FusionProcessor(measurement_date=session.measurement_date)

                # Audio 폴더 찾기
                audio_folder = session.source_path / "Audio"
                if not audio_folder.exists():
                    self.session_complete.emit(idx, False, "Audio 폴더 없음")
                    fail_count += 1
                    continue

                result = processor.process(
                    audio_folder,
                    session_path,
                    progress_callback=lambda c, t, m: self.progress.emit(c, t, m)
                )

                if result.success:
                    # Manifest 생성
                    create_manifest(
                        session_path,
                        session.source_path,
                        session.equipment_type,
                        session.measurement_date.isoformat(),
                    )
                    self.session_complete.emit(idx, True, result.message)
                    success_count += 1
                else:
                    self.session_complete.emit(idx, False, result.message)
                    fail_count += 1

            except Exception as e:
                logger.exception(f"세션 처리 실패: {session.point}")
                self.session_complete.emit(idx, False, str(e))
                fail_count += 1

        self.finished_all.emit(success_count, fail_count)

    def cancel(self):
        """취소"""
        self._is_cancelled = True


class MainWindow(QMainWindow):
    """메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.sessions: List[AudioSession] = []
        self.processing_thread: Optional[ProcessingThread] = None

        self._init_ui()

    def _init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # 입력 섹션
        input_group = QGroupBox("입력 설정")
        input_layout = QVBoxLayout(input_group)

        # 소스 경로
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("소스 경로:"))
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Fusion 데이터 루트 폴더 선택...")
        source_layout.addWidget(self.source_edit)
        self.source_btn = QPushButton("찾아보기...")
        self.source_btn.clicked.connect(self._browse_source)
        source_layout.addWidget(self.source_btn)
        input_layout.addLayout(source_layout)

        # 위치명
        location_layout = QHBoxLayout()
        location_layout.addWidget(QLabel("위치명:"))
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("예: 광주비행장")
        location_layout.addWidget(self.location_edit)
        location_layout.addStretch()
        input_layout.addLayout(location_layout)

        # 스캔 버튼
        scan_layout = QHBoxLayout()
        self.scan_btn = QPushButton("스캔")
        self.scan_btn.clicked.connect(self._scan_sessions)
        scan_layout.addWidget(self.scan_btn)
        scan_layout.addStretch()
        input_layout.addLayout(scan_layout)

        layout.addWidget(input_group)

        # 세션 테이블
        table_group = QGroupBox("감지된 세션")
        table_layout = QVBoxLayout(table_group)

        # 필터 옵션
        filter_layout = QHBoxLayout()
        self.exclude_weekend_cb = QCheckBox("주말 제외")
        self.exclude_weekend_cb.stateChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.exclude_weekend_cb)

        self.exclude_partial_cb = QCheckBox("부분 제외 (불완전 데이터)")
        self.exclude_partial_cb.stateChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.exclude_partial_cb)

        filter_layout.addStretch()

        self.select_all_btn = QPushButton("전체 선택")
        self.select_all_btn.clicked.connect(self._select_all)
        filter_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("전체 해제")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        filter_layout.addWidget(self.deselect_all_btn)

        table_layout.addLayout(filter_layout)

        # 테이블
        self.session_table = QTableWidget()
        self.session_table.setColumnCount(7)
        self.session_table.setHorizontalHeaderLabels([
            "선택", "지점", "장비", "측정일", "요일", "파일수", "상태"
        ])
        self.session_table.setSortingEnabled(True)
        self.session_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        table_layout.addWidget(self.session_table)

        layout.addWidget(table_group)

        # 출력 섹션
        output_group = QGroupBox("출력 설정")
        output_layout = QVBoxLayout(output_group)

        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(QLabel("출력 경로:"))
        self.output_edit = QLineEdit()
        self.output_edit.setText(str(DEFAULT_OUTPUT_BASE))
        output_path_layout.addWidget(self.output_edit)
        self.output_btn = QPushButton("찾아보기...")
        self.output_btn.clicked.connect(self._browse_output)
        output_path_layout.addWidget(self.output_btn)
        output_layout.addLayout(output_path_layout)

        layout.addWidget(output_group)

        # 진행 상태
        progress_group = QGroupBox("진행 상태")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        progress_layout.addWidget(self.log_text)

        layout.addWidget(progress_group)

        # 실행 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.start_btn = QPushButton("추출 시작")
        self.start_btn.clicked.connect(self._start_processing)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self._cancel_processing)
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _browse_source(self):
        """소스 폴더 선택"""
        path = QFileDialog.getExistingDirectory(
            self, "소스 폴더 선택", str(Path.home())
        )
        if path:
            self.source_edit.setText(path)

    def _browse_output(self):
        """출력 폴더 선택"""
        path = QFileDialog.getExistingDirectory(
            self, "출력 폴더 선택", self.output_edit.text()
        )
        if path:
            self.output_edit.setText(path)

    def _scan_sessions(self):
        """세션 스캔"""
        source_path = self.source_edit.text().strip()
        if not source_path:
            QMessageBox.warning(self, "경고", "소스 경로를 입력하세요.")
            return

        source = Path(source_path)
        if not source.exists():
            QMessageBox.warning(self, "경고", "소스 경로가 존재하지 않습니다.")
            return

        self._log("스캔 시작...")

        detector = FusionDetector()
        self.sessions = detector.detect(source)

        self._log(f"감지된 세션: {len(self.sessions)}개")

        self._populate_table()
        self.start_btn.setEnabled(len(self.sessions) > 0)

    def _populate_table(self):
        """테이블 채우기"""
        self.session_table.setSortingEnabled(False)
        self.session_table.setRowCount(len(self.sessions))

        for row, session in enumerate(self.sessions):
            # 체크박스
            check_item = QTableWidgetItem()
            check_item.setCheckState(Qt.CheckState.Checked)
            # 원본 세션 인덱스 저장 (정렬 후에도 올바른 세션 참조용)
            check_item.setData(Qt.ItemDataRole.UserRole, row)
            self.session_table.setItem(row, 0, check_item)

            # 지점
            point_item = QTableWidgetItem(session.point)
            point_item.setData(Qt.ItemDataRole.UserRole, row)
            self.session_table.setItem(row, 1, point_item)

            # 장비
            equip_item = QTableWidgetItem(session.equipment_type)
            equip_item.setData(Qt.ItemDataRole.UserRole, row)
            self.session_table.setItem(row, 2, equip_item)

            # 측정일
            date_item = QTableWidgetItem(
                session.measurement_date.strftime("%Y-%m-%d")
            )
            date_item.setData(Qt.ItemDataRole.UserRole, row)
            self.session_table.setItem(row, 3, date_item)

            # 요일
            weekday_idx = session.measurement_date.weekday()
            weekday_item = QTableWidgetItem(WEEKDAY_KR[weekday_idx])
            weekday_item.setData(Qt.ItemDataRole.UserRole, row)
            self.session_table.setItem(row, 4, weekday_item)

            # 파일수
            file_count_item = QTableWidgetItem(str(session.bid_count))
            file_count_item.setData(Qt.ItemDataRole.UserRole, row)
            self.session_table.setItem(row, 5, file_count_item)

            # 상태 (48개 = 완전, 그 외 = 부분)
            if session.bid_count >= 48:
                status = "완전"
            elif session.bid_count > 0:
                status = f"부분 ({session.bid_count}/48)"
            else:
                status = "없음"

            status_item = QTableWidgetItem(status)
            status_item.setData(Qt.ItemDataRole.UserRole, row)
            self.session_table.setItem(row, 6, status_item)

        self.session_table.setSortingEnabled(True)

    def _apply_filters(self):
        """필터 적용"""
        exclude_weekend = self.exclude_weekend_cb.isChecked()
        exclude_partial = self.exclude_partial_cb.isChecked()

        for row in range(self.session_table.rowCount()):
            # 원본 세션 인덱스 가져오기
            item = self.session_table.item(row, 0)
            if item is None:
                continue

            session_idx = item.data(Qt.ItemDataRole.UserRole)
            if session_idx is None or session_idx >= len(self.sessions):
                continue

            session = self.sessions[session_idx]
            should_check = True

            # 주말 제외
            if exclude_weekend:
                weekday = session.measurement_date.weekday()
                if weekday >= 5:  # 토(5), 일(6)
                    should_check = False

            # 부분 제외
            if exclude_partial and session.bid_count < 48:
                should_check = False

            item.setCheckState(
                Qt.CheckState.Checked if should_check else Qt.CheckState.Unchecked
            )

    def _select_all(self):
        """전체 선택"""
        for row in range(self.session_table.rowCount()):
            item = self.session_table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _deselect_all(self):
        """전체 해제"""
        for row in range(self.session_table.rowCount()):
            item = self.session_table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _get_selected_sessions(self) -> List[AudioSession]:
        """선택된 세션 목록 반환"""
        selected = []

        for row in range(self.session_table.rowCount()):
            item = self.session_table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                # 원본 세션 인덱스로 접근
                session_idx = item.data(Qt.ItemDataRole.UserRole)
                if session_idx is not None and session_idx < len(self.sessions):
                    selected.append(self.sessions[session_idx])

        return selected

    def _start_processing(self):
        """처리 시작"""
        selected = self._get_selected_sessions()
        if not selected:
            QMessageBox.warning(self, "경고", "선택된 세션이 없습니다.")
            return

        location = self.location_edit.text().strip()
        if not location:
            QMessageBox.warning(self, "경고", "위치명을 입력하세요.")
            return

        output_path = Path(self.output_edit.text().strip())
        if not output_path.exists():
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(
                    self, "오류", f"출력 폴더 생성 실패: {e}"
                )
                return

        # UI 상태 변경
        self._set_processing_state(True)

        self._log(f"처리 시작: {len(selected)}개 세션")

        # 스레드 시작
        self.processing_thread = ProcessingThread(
            selected, output_path, location
        )
        self.processing_thread.progress.connect(self._on_progress)
        self.processing_thread.session_complete.connect(self._on_session_complete)
        self.processing_thread.finished_all.connect(self._on_finished)
        self.processing_thread.start()

    def _cancel_processing(self):
        """처리 취소"""
        if self.processing_thread:
            self.processing_thread.cancel()
            self._log("취소 요청됨...")

    def _set_processing_state(self, processing: bool):
        """처리 상태에 따른 UI 변경"""
        self.start_btn.setEnabled(not processing)
        self.cancel_btn.setEnabled(processing)
        self.scan_btn.setEnabled(not processing)
        self.source_btn.setEnabled(not processing)
        self.output_btn.setEnabled(not processing)

    def _on_progress(self, current: int, total: int, message: str):
        """진행 업데이트"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_session_complete(self, idx: int, success: bool, message: str):
        """세션 완료"""
        status = "성공" if success else "실패"
        self._log(f"세션 {idx + 1}: {status} - {message}")

    def _on_finished(self, success_count: int, fail_count: int):
        """전체 완료"""
        self._set_processing_state(False)
        self._log(f"완료: 성공 {success_count}개, 실패 {fail_count}개")

        QMessageBox.information(
            self,
            "완료",
            f"처리 완료\n성공: {success_count}개\n실패: {fail_count}개"
        )

    def _log(self, message: str):
        """로그 출력"""
        self.log_text.append(message)
        # 자동 스크롤 - 커서를 끝으로 이동
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)


def main():
    """메인 엔트리"""
    app = QApplication(sys.argv)

    # 스타일 설정
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
