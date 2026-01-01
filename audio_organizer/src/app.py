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
    QSplitter,
)
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtCore import QUrl

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


class ScanThread(QThread):
    """세션 스캔 백그라운드 스레드"""

    started_signal = pyqtSignal()
    progress = pyqtSignal(str)  # 진행 메시지
    finished_signal = pyqtSignal(list)  # 감지된 세션 리스트
    error = pyqtSignal(str)  # 에러 메시지

    def __init__(self, source_path: Path):
        super().__init__()
        self.source_path = source_path

    def run(self):
        try:
            self.started_signal.emit()
            self.progress.emit("[INFO] 스캔 시작...")

            detector = FusionDetector()
            sessions = detector.detect(self.source_path)

            self.progress.emit(f"[INFO] 감지된 세션: {len(sessions)}개")
            self.finished_signal.emit(sessions)

        except Exception as e:
            logger.exception("스캔 실패")
            self.error.emit(f"[ERROR] 스캔 실패: {str(e)}")


class ProcessingThread(QThread):
    """백그라운드 처리 스레드"""

    progress = pyqtSignal(int, int, str)  # current, total, message
    session_complete = pyqtSignal(int, bool, str)  # session_idx, success, message
    log = pyqtSignal(str)  # 로그 메시지
    finished_all = pyqtSignal(int, int, bool)  # success_count, fail_count, was_cancelled

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

        self.log.emit(f"[INFO] 추출 시작: {total_sessions}개 세션")

        for idx, session in enumerate(self.sessions):
            if self._is_cancelled:
                self.log.emit("[WARN] 사용자에 의해 취소됨")
                break

            self.progress.emit(idx + 1, total_sessions, f"처리 중: {session.point}")
            self.log.emit(f"\n[INFO] === {session.point} ({session.measurement_date}) ===")

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
                    self.log.emit(f"[WARN] 폴더 이미 존재, 건너뜀")
                    self.session_complete.emit(idx, False, "폴더 이미 존재")
                    fail_count += 1
                    continue

                # 프로세서 생성 및 실행
                processor = FusionProcessor(measurement_date=session.measurement_date)

                # Audio 폴더 찾기
                audio_folder = session.source_path / "Audio"
                if not audio_folder.exists():
                    self.log.emit(f"[ERROR] Audio 폴더 없음")
                    self.session_complete.emit(idx, False, "Audio 폴더 없음")
                    fail_count += 1
                    continue

                self.log.emit(f"[INFO] BID 파일 변환 중...")

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
                    self.log.emit(f"[INFO] 완료: {result.files_processed}개 파일 변환")
                    self.session_complete.emit(idx, True, result.message)
                    success_count += 1
                else:
                    self.log.emit(f"[ERROR] 실패: {result.message}")
                    self.session_complete.emit(idx, False, result.message)
                    fail_count += 1

            except Exception as e:
                logger.exception(f"세션 처리 실패: {session.point}")
                self.log.emit(f"[ERROR] 예외 발생: {str(e)}")
                self.session_complete.emit(idx, False, str(e))
                fail_count += 1

        if self._is_cancelled:
            self.log.emit(f"\n[WARN] === 작업 취소됨 ===")
            self.log.emit(f"[INFO] 취소 전 완료: 성공 {success_count}개, 실패 {fail_count}개")
        else:
            self.log.emit(f"\n[INFO] === 추출 완료 ===")
            self.log.emit(f"[INFO] 성공: {success_count}개, 실패: {fail_count}개")

        self.finished_all.emit(success_count, fail_count, self._is_cancelled)

    def cancel(self):
        """취소"""
        self._is_cancelled = True


class NumericTableWidgetItem(QTableWidgetItem):
    """숫자 정렬을 지원하는 테이블 아이템"""

    def __init__(self, value: int):
        super().__init__(str(value))
        self._value = value

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self._value < other._value
        return super().__lt__(other)


class MainWindow(QMainWindow):
    """메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.sessions: List[AudioSession] = []
        self.processing_thread: Optional[ProcessingThread] = None
        self.scan_thread: Optional[ScanThread] = None

        self._init_ui()

    def _init_ui(self):
        """UI 초기화 - 옵션 B: 테이블 중심 + 로그 하단"""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # 스타일시트 적용
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #c0c0c0;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #333;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #a0a0a0;
            }
            QPushButton#startBtn {
                background-color: #2563eb;
                color: white;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#startBtn:hover {
                background-color: #1d4ed8;
            }
            QPushButton#startBtn:disabled {
                background-color: #93c5fd;
            }
            QPushButton#cancelBtn {
                background-color: #dc2626;
                color: white;
                border: none;
            }
            QPushButton#cancelBtn:hover {
                background-color: #b91c1c;
            }
            QPushButton#cancelBtn:disabled {
                background-color: #fca5a5;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
            }
            QLineEdit:disabled {
                background-color: #f5f5f5;
            }
            QProgressBar {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 3px;
            }
            QTableWidget {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                gridline-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #c0c0c0;
                font-weight: bold;
            }
            QCheckBox:disabled {
                color: #a0a0a0;
            }
        """)

        # ========== 1. 설정 영역 (상단) ==========
        settings_group = QGroupBox("설정")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(8)

        # 첫 번째 줄: 소스 경로
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("소스 경로:"))
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Fusion 데이터 루트 폴더 선택...")
        row1.addWidget(self.source_edit, stretch=1)
        self.source_btn = QPushButton("찾아보기")
        self.source_btn.setFixedWidth(90)
        self.source_btn.clicked.connect(self._browse_source)
        row1.addWidget(self.source_btn)
        self.scan_btn = QPushButton("스캔")
        self.scan_btn.setFixedWidth(70)
        self.scan_btn.clicked.connect(self._scan_sessions)
        row1.addWidget(self.scan_btn)
        settings_layout.addLayout(row1)

        # 두 번째 줄: 위치명 + 출력 경로
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("위치명:"))
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("예: 광주비행장")
        self.location_edit.setFixedWidth(150)
        row2.addWidget(self.location_edit)
        row2.addSpacing(20)
        row2.addWidget(QLabel("출력 경로:"))
        self.output_edit = QLineEdit()
        self.output_edit.setText(str(DEFAULT_OUTPUT_BASE))
        row2.addWidget(self.output_edit, stretch=1)
        self.output_btn = QPushButton("찾아보기")
        self.output_btn.setFixedWidth(90)
        self.output_btn.clicked.connect(self._browse_output)
        row2.addWidget(self.output_btn)
        self.open_output_btn = QPushButton("열기")
        self.open_output_btn.setFixedWidth(50)
        self.open_output_btn.clicked.connect(self._open_output_folder)
        row2.addWidget(self.open_output_btn)
        settings_layout.addLayout(row2)

        main_layout.addWidget(settings_group)

        # ========== 2. 세션 테이블 (메인, 크게) ==========
        table_group = QGroupBox("감지된 세션")
        table_layout = QVBoxLayout(table_group)

        # 필터 옵션
        filter_layout = QHBoxLayout()
        self.exclude_weekend_cb = QCheckBox("주말 제외")
        self.exclude_weekend_cb.stateChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.exclude_weekend_cb)

        self.exclude_partial_cb = QCheckBox("부분 데이터 제외")
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
        self.session_table.verticalHeader().setVisible(False)
        self.session_table.setMinimumHeight(300)
        table_layout.addWidget(self.session_table)

        main_layout.addWidget(table_group, stretch=1)  # 테이블이 가장 크게

        # ========== 3. 로그 영역 (하단) ==========
        log_group = QGroupBox("로그")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(0, 10, 0, 0)

        # 로그 헤더
        log_header = QWidget()
        log_header.setStyleSheet("background-color: #1e3a5f; border-radius: 4px 4px 0 0;")
        log_header_layout = QHBoxLayout(log_header)
        log_header_layout.setContentsMargins(12, 6, 12, 6)

        log_title = QLabel("추출 로그")
        log_title.setStyleSheet("color: #fff; font-weight: bold; font-size: 11px;")
        log_header_layout.addWidget(log_title)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #94a3b8; font-size: 10px;")
        log_header_layout.addWidget(self.stats_label)
        log_header_layout.addStretch()

        # 로그 버튼
        log_btn_style = """
            QPushButton {
                background-color: #2d4a6f;
                color: #ccc;
                border: none;
                padding: 3px 10px;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #3d5a7f;
            }
        """
        self.clear_log_btn = QPushButton("지우기")
        self.clear_log_btn.setStyleSheet(log_btn_style)
        self.clear_log_btn.clicked.connect(self._clear_log)
        log_header_layout.addWidget(self.clear_log_btn)

        log_layout.addWidget(log_header)

        # 로그 텍스트
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10px;
                border: none;
                border-radius: 0 0 4px 4px;
                padding: 6px;
            }
        """)
        log_layout.addWidget(self.log_text)

        main_layout.addWidget(log_group)

        # ========== 4. 실행 영역 (하단) ==========
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        # 진행 상황
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(4)

        self.progress_label = QLabel("대기 중")
        self.progress_label.setStyleSheet("color: #666; font-size: 11px;")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        action_layout.addWidget(progress_widget, stretch=1)

        # 버튼
        self.start_btn = QPushButton("추출 시작")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setMinimumWidth(120)
        self.start_btn.clicked.connect(self._start_processing)
        self.start_btn.setEnabled(False)
        action_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setMinimumHeight(50)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        self.cancel_btn.setEnabled(False)
        action_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(action_layout)

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

    def _open_output_folder(self):
        """출력 폴더 열기"""
        folder = self.output_edit.text().strip()
        if folder and Path(folder).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.warning(self, "경고", "출력 폴더가 존재하지 않습니다.")

    def _scan_sessions(self):
        """세션 스캔 (백그라운드 스레드)"""
        source_path = self.source_edit.text().strip()
        if not source_path:
            QMessageBox.warning(self, "경고", "소스 경로를 입력하세요.")
            return

        source = Path(source_path)
        if not source.exists():
            QMessageBox.warning(self, "경고", "소스 경로가 존재하지 않습니다.")
            return

        # 스캔 스레드 시작
        self.scan_thread = ScanThread(source)
        self.scan_thread.started_signal.connect(self._on_scan_started)
        self.scan_thread.progress.connect(self._on_log)
        self.scan_thread.finished_signal.connect(self._on_scan_finished)
        self.scan_thread.error.connect(self._on_log)
        self.scan_thread.start()

    def _on_scan_started(self):
        """스캔 시작됨"""
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("스캔중...")
        self.source_btn.setEnabled(False)

    def _on_scan_finished(self, sessions: List[AudioSession]):
        """스캔 완료"""
        self.sessions = sessions
        self._populate_table()

        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("스캔")
        self.source_btn.setEnabled(True)
        self.start_btn.setEnabled(len(self.sessions) > 0)

    def _populate_table(self):
        """테이블 채우기"""
        self.session_table.setSortingEnabled(False)
        self.session_table.setRowCount(len(self.sessions))

        for row, session in enumerate(self.sessions):
            # 체크박스
            check_item = QTableWidgetItem()
            check_item.setCheckState(Qt.CheckState.Checked)
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
            if weekday_idx >= 5:
                weekday_item.setBackground(QColor(255, 230, 230))
            self.session_table.setItem(row, 4, weekday_item)

            # 파일수 (숫자 정렬 지원)
            file_count_item = NumericTableWidgetItem(session.bid_count)
            file_count_item.setData(Qt.ItemDataRole.UserRole, row)
            self.session_table.setItem(row, 5, file_count_item)

            # 상태
            if session.bid_count >= 48:
                status = "완전"
                status_color = QColor(200, 255, 200)
            elif session.bid_count > 0:
                status = f"부분 ({session.bid_count}/48)"
                status_color = QColor(255, 240, 200)
            else:
                status = "없음"
                status_color = QColor(255, 200, 200)

            status_item = QTableWidgetItem(status)
            status_item.setData(Qt.ItemDataRole.UserRole, row)
            status_item.setBackground(status_color)
            self.session_table.setItem(row, 6, status_item)

        self.session_table.setSortingEnabled(True)

    def _apply_filters(self):
        """필터 적용"""
        exclude_weekend = self.exclude_weekend_cb.isChecked()
        exclude_partial = self.exclude_partial_cb.isChecked()

        for row in range(self.session_table.rowCount()):
            item = self.session_table.item(row, 0)
            if item is None:
                continue

            session_idx = item.data(Qt.ItemDataRole.UserRole)
            if session_idx is None or session_idx >= len(self.sessions):
                continue

            session = self.sessions[session_idx]
            should_check = True

            if exclude_weekend:
                weekday = session.measurement_date.weekday()
                if weekday >= 5:
                    should_check = False

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
        self.log_text.clear()

        # 스레드 시작
        self.processing_thread = ProcessingThread(
            selected, output_path, location
        )
        self.processing_thread.progress.connect(self._on_progress)
        self.processing_thread.log.connect(self._on_log)
        self.processing_thread.session_complete.connect(self._on_session_complete)
        self.processing_thread.finished_all.connect(self._on_finished)
        self.processing_thread.start()

    def _cancel_processing(self):
        """처리 취소"""
        if self.processing_thread:
            self.processing_thread.cancel()
            self._log("[WARN] 취소 요청됨...")

    def _set_processing_state(self, processing: bool):
        """처리 상태에 따른 UI 변경"""
        # 버튼
        self.start_btn.setEnabled(not processing)
        self.cancel_btn.setEnabled(processing)
        self.scan_btn.setEnabled(not processing)
        self.source_btn.setEnabled(not processing)
        self.output_btn.setEnabled(not processing)

        # 입력 필드
        self.source_edit.setEnabled(not processing)
        self.location_edit.setEnabled(not processing)
        self.output_edit.setEnabled(not processing)

        # 테이블 및 필터
        self.session_table.setEnabled(not processing)
        self.exclude_weekend_cb.setEnabled(not processing)
        self.exclude_partial_cb.setEnabled(not processing)
        self.select_all_btn.setEnabled(not processing)
        self.deselect_all_btn.setEnabled(not processing)

    def _on_progress(self, current: int, total: int, message: str):
        """진행 업데이트"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(message)

    def _on_log(self, message: str):
        """로그 추가 (색상 적용)"""
        if '[ERROR]' in message:
            color = '#f87171'
        elif '[WARN]' in message:
            color = '#fbbf24'
        elif '완료' in message or '성공' in message:
            color = '#4ade80'
        else:
            color = '#e2e8f0'

        escaped = message.replace('<', '&lt;').replace('>', '&gt;')
        self.log_text.append(f'<span style="color: {color};">{escaped}</span>')

        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_session_complete(self, idx: int, success: bool, message: str):
        """세션 완료"""
        pass

    def _on_finished(self, success_count: int, fail_count: int, was_cancelled: bool):
        """전체 완료"""
        self._set_processing_state(False)

        if was_cancelled:
            self.progress_label.setText(f"취소됨 (완료: 성공 {success_count}개, 실패 {fail_count}개)")
            self.stats_label.setText(f"취소됨 | 성공: {success_count} | 실패: {fail_count}")
            QMessageBox.warning(
                self,
                "취소됨",
                f"작업이 취소되었습니다.\n\n취소 전 완료:\n성공: {success_count}개\n실패: {fail_count}개"
            )
        else:
            self.progress_label.setText(f"완료: 성공 {success_count}개, 실패 {fail_count}개")
            self.stats_label.setText(f"성공: {success_count} | 실패: {fail_count}")
            QMessageBox.information(
                self,
                "완료",
                f"처리 완료\n성공: {success_count}개\n실패: {fail_count}개"
            )

    def _log(self, message: str):
        """로그 출력 (내부용)"""
        self._on_log(message)

    def _clear_log(self):
        """로그 지우기"""
        self.log_text.clear()
        self.stats_label.setText("")


def main():
    """메인 엔트리"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
