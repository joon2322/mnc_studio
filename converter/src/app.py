"""MNC Master Converter v3.0.0 - PyQt6 GUI"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QProgressBar,
    QTextEdit, QCheckBox, QComboBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QSplitter, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QColor, QDesktopServices

from .parsers import FusionParser, RionParser
from .exporters import ParquetExporter, CSVExporter
from .validators import DataValidator, ValidationResult
from .config import ConversionConfig, APP_VERSION
from .utils.file_utils import parse_point_folder, generate_filename


@dataclass
class DeviceInfo:
    """지점별 장비 정보"""
    point_folder: Path
    point_id: str
    point_name: str
    detected_type: str  # 'Fusion', 'Rion', '미감지'
    device_folder: Optional[Path] = None
    selected_type: str = ''  # 사용자 선택 (빈 문자열이면 자동 감지 사용)


class ConverterWorker(QThread):
    """변환 작업 스레드"""
    progress = pyqtSignal(int, str)  # (percent, message)
    log = pyqtSignal(str)
    stats = pyqtSignal(int, int)  # (warning_count, error_count)
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, config: ConversionConfig, device_list: List[DeviceInfo]):
        super().__init__()
        self.config = config
        self.device_list = device_list
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        # 경고/에러 카운터
        self.warning_count = 0
        self.error_count = 0

        def emit_log(msg):
            """로그 출력 + 경고/에러 카운트 (모든 로그 통합)"""
            self.log.emit(msg)
            if '[WARN]' in msg:
                self.warning_count += 1
                self.stats.emit(self.warning_count, self.error_count)
            elif '[ERROR]' in msg:
                self.error_count += 1
                self.stats.emit(self.warning_count, self.error_count)

        try:
            emit_log("[INFO] 변환 시작...")

            # 파서 초기화
            fusion_parser = FusionParser()
            rion_parser = RionParser()

            # 로그 콜백 설정 (카운트 포함)
            fusion_parser.set_log_callback(emit_log)
            rion_parser.set_log_callback(emit_log)

            # 출력 모듈 초기화
            parquet_exporter = ParquetExporter(self.config.output_path)
            csv_exporter = CSVExporter(self.config.output_path) if self.config.output_csv else None

            # 검증기 초기화
            validator = DataValidator()
            validation_results: List[ValidationResult] = []

            total_files = 0
            total_points = len(self.device_list)

            for i, device_info in enumerate(self.device_list):
                if self._is_cancelled:
                    self.finished.emit(False, "사용자에 의해 취소됨")
                    return

                progress = int((i + 1) / total_points * 100)
                self.progress.emit(progress, f"처리 중: {device_info.point_id}")
                emit_log(f"\n[INFO] === {device_info.point_id} ({device_info.point_name}) ===")

                # 장비 타입 결정 (사용자 선택 > 자동 감지)
                device_type = device_info.selected_type or device_info.detected_type

                if device_type == '미감지':
                    emit_log(f"[WARN] 장비 미감지, 건너뜀")
                    continue

                # 수동 선택으로 타입이 변경되었는지 확인
                type_changed = (device_info.selected_type and
                               device_info.selected_type != device_info.detected_type)

                # 파서 및 장비 폴더 결정
                if device_type == 'Fusion':
                    parser = fusion_parser
                    # 타입 변경 시 또는 device_folder가 없으면 재탐색
                    if type_changed or not device_info.device_folder:
                        folders = fusion_parser.find_device_folders(device_info.point_folder)
                        if not folders:
                            emit_log(f"[WARN] Fusion 장비 폴더를 찾을 수 없음")
                            continue
                        device_folder = folders[0]
                        if type_changed:
                            emit_log(f"[INFO] 수동 선택으로 Fusion 재탐색")
                    else:
                        device_folder = device_info.device_folder
                else:  # Rion
                    parser = rion_parser
                    # 타입 변경 시 또는 device_folder가 없으면 재탐색
                    if type_changed or not device_info.device_folder:
                        folders = rion_parser.find_device_folders(device_info.point_folder)
                        if not folders:
                            emit_log(f"[WARN] Rion 장비 폴더를 찾을 수 없음")
                            continue
                        device_folder = folders[0]
                        if type_changed:
                            emit_log(f"[INFO] 수동 선택으로 Rion 재탐색")
                    else:
                        device_folder = device_info.device_folder

                emit_log(f"[INFO] 장비: {device_type} ({device_folder.name})")

                # 가중치 목록
                weightings = ['LAS', 'LCS'] if self.config.weighting == 'both' else [self.config.weighting]

                for weighting in weightings:
                    emit_log(f"[INFO] 가중치: {weighting}")

                    # 변환
                    data_dict = parser.process(
                        device_folder,
                        weighting,
                        include_bands=self.config.include_bands
                    )

                    if not data_dict:
                        emit_log(f"[WARN] 데이터 없음")
                        continue

                    # 저장
                    for date_key, df in data_dict.items():
                        date = datetime.strptime(date_key, '%Y%m%d')
                        valid_count = df['spl'].notna().sum()

                        pq_path = parquet_exporter.export(
                            df,
                            self.config.site_name,
                            device_info.point_id,
                            date,
                            weighting,
                            self.config.round_number
                        )
                        emit_log(f"[INFO] 저장: {pq_path.name} ({valid_count}/86400)")

                        if csv_exporter:
                            csv_exporter.export(
                                df,
                                self.config.site_name,
                                device_info.point_id,
                                date,
                                weighting,
                                self.config.round_number
                            )

                        # 검증
                        result = validator.validate(
                            df=df,
                            filename=pq_path.name,
                            date=date,
                            point_id=device_info.point_id,
                            weighting=weighting
                        )
                        validation_results.append(result)

                        total_files += 1

            # 검증 요약 리포트 출력
            if validation_results:
                emit_log("\n")
                report = validator.validate_batch(validation_results)
                for line in report.split('\n'):
                    emit_log(line)

            self.finished.emit(True, f"완료! 총 {total_files}개 파일 생성")

        except Exception as e:
            import traceback
            emit_log(f"[ERROR] {traceback.format_exc()}")
            self.finished.emit(False, f"오류: {str(e)}")


class MainWindow(QMainWindow):
    """메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MNC Master Converter v{APP_VERSION}")
        self.setMinimumSize(1100, 900)
        self.worker = None
        self.device_list: List[DeviceInfo] = []
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(12)
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
            QPushButton#convertBtn {
                background-color: #4a90d9;
                color: white;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#convertBtn:hover {
                background-color: #3a80c9;
            }
            QPushButton#convertBtn:disabled {
                background-color: #a0a0a0;
            }
            QPushButton#cancelBtn {
                background-color: #e74c3c;
                color: white;
                border: none;
            }
            QPushButton#cancelBtn:hover {
                background-color: #c0392b;
            }
            QPushButton#cancelBtn:disabled {
                background-color: #a0a0a0;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1px solid #4a90d9;
            }
            QProgressBar {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #4a90d9;
                border-radius: 3px;
            }
            QTextEdit#logText {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10px;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
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
        """)

        # ========== 좌측 패널 (설정) ==========
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. 원본 데이터 선택
        source_group = QGroupBox("원본 데이터")
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(8)

        path_row = QHBoxLayout()
        self.source_path = QLineEdit()
        self.source_path.setPlaceholderText("폴더 경로 (지점 폴더들이 있는 상위 폴더)")
        source_btn = QPushButton("찾아보기")
        source_btn.setFixedWidth(90)
        source_btn.clicked.connect(self.select_source_folder)
        self.detect_btn = QPushButton("장비 감지")
        self.detect_btn.setFixedWidth(90)
        self.detect_btn.clicked.connect(self.detect_devices)
        path_row.addWidget(self.source_path, stretch=1)
        path_row.addWidget(source_btn)
        path_row.addWidget(self.detect_btn)
        source_layout.addLayout(path_row)

        # 장비 감지 테이블
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["지점", "이름", "감지", "선택"])
        self.device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.device_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.setMinimumHeight(200)
        self.device_table.setMaximumHeight(400)
        self.device_table.verticalHeader().setVisible(False)
        source_layout.addWidget(self.device_table)

        left_layout.addWidget(source_group)

        # 2. 변환 설정
        settings_group = QGroupBox("변환 설정")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(6)

        # 사이트명
        site_row = QHBoxLayout()
        site_label = QLabel("사이트명:")
        site_label.setFixedWidth(70)
        self.site_name = QLineEdit()
        self.site_name.setPlaceholderText("예: 광주비행장")
        site_row.addWidget(site_label)
        site_row.addWidget(self.site_name, stretch=1)
        settings_layout.addLayout(site_row)

        # 차수 + 가중치 한 줄에
        option_row = QHBoxLayout()
        self.include_round = QCheckBox("차수")
        self.round_combo = QComboBox()
        self.round_combo.addItems(["1차", "2차", "3차", "4차", "5차"])
        self.round_combo.setFixedWidth(60)
        self.round_combo.setEnabled(False)
        self.include_round.toggled.connect(self.round_combo.setEnabled)
        option_row.addWidget(self.include_round)
        option_row.addWidget(self.round_combo)
        option_row.addSpacing(20)
        option_row.addWidget(QLabel("가중치:"))
        self.weight_combo = QComboBox()
        self.weight_combo.addItems(["LAS", "LCS", "둘 다"])
        self.weight_combo.setFixedWidth(70)
        option_row.addWidget(self.weight_combo)
        option_row.addStretch()
        settings_layout.addLayout(option_row)

        # 옥타브 밴드
        self.include_bands = QCheckBox("1/3 옥타브 밴드 포함 (33밴드)")
        self.include_bands.setChecked(True)
        settings_layout.addWidget(self.include_bands)

        left_layout.addWidget(settings_group)

        # 3. 출력 설정
        output_group = QGroupBox("출력 설정")
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(6)

        path_row2 = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("출력 폴더 경로")
        output_btn = QPushButton("찾아보기")
        output_btn.setFixedWidth(90)
        output_btn.clicked.connect(self.select_output_folder)
        self.open_output_btn = QPushButton("열기")
        self.open_output_btn.setFixedWidth(60)
        self.open_output_btn.clicked.connect(self.open_output_folder)
        path_row2.addWidget(self.output_path, stretch=1)
        path_row2.addWidget(output_btn)
        path_row2.addWidget(self.open_output_btn)
        output_layout.addLayout(path_row2)

        self.output_csv = QCheckBox("CSV 함께 출력")
        self.output_csv.setChecked(True)
        output_layout.addWidget(self.output_csv)

        left_layout.addWidget(output_group)

        # 4. 실행
        action_group = QGroupBox("실행")
        action_layout = QVBoxLayout(action_group)
        action_layout.setSpacing(8)

        # 진행 상황
        self.progress_label = QLabel("대기 중")
        self.progress_label.setStyleSheet("color: #666;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        action_layout.addWidget(self.progress_label)
        action_layout.addWidget(self.progress_bar)

        # 버튼
        btn_row = QHBoxLayout()
        self.convert_btn = QPushButton("변환 시작")
        self.convert_btn.setObjectName("convertBtn")
        self.convert_btn.setMinimumHeight(45)
        self.convert_btn.clicked.connect(self.start_conversion)
        btn_row.addWidget(self.convert_btn, stretch=2)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setMinimumHeight(45)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_conversion)
        btn_row.addWidget(self.cancel_btn, stretch=1)
        action_layout.addLayout(btn_row)

        left_layout.addWidget(action_group)

        # ========== 우측 패널 (로그) ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 로그 헤더
        log_header = QWidget()
        log_header.setStyleSheet("background-color: #2d2d2d; border-radius: 4px 4px 0 0;")
        log_header_layout = QHBoxLayout(log_header)
        log_header_layout.setContentsMargins(12, 8, 12, 8)
        log_title = QLabel("변환 로그")
        log_title.setStyleSheet("color: #fff; font-weight: bold; font-size: 12px;")
        log_header_layout.addWidget(log_title)

        # 경고/에러 카운트 라벨
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #888; font-size: 11px;")
        log_header_layout.addWidget(self.stats_label)
        log_header_layout.addStretch()

        # 로그 버튼 스타일
        log_btn_style = """
            QPushButton {
                background-color: #444;
                color: #ccc;
                border: none;
                padding: 4px 12px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """

        # 복사 버튼
        self.copy_log_btn = QPushButton("복사")
        self.copy_log_btn.setStyleSheet(log_btn_style)
        self.copy_log_btn.clicked.connect(self.copy_log_to_clipboard)
        log_header_layout.addWidget(self.copy_log_btn)

        # 저장 버튼
        self.save_log_btn = QPushButton("저장")
        self.save_log_btn.setStyleSheet(log_btn_style)
        self.save_log_btn.clicked.connect(self.save_log_to_file)
        log_header_layout.addWidget(self.save_log_btn)

        # 지우기 버튼
        self.clear_log_btn = QPushButton("지우기")
        self.clear_log_btn.setStyleSheet(log_btn_style)
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_header_layout.addWidget(self.clear_log_btn)

        right_layout.addWidget(log_header)

        # 로그 텍스트
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logText")
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: none;
                border-radius: 0 0 4px 4px;
                padding: 8px;
            }
        """)
        right_layout.addWidget(self.log_text)

        # ========== 스플리터로 좌우 배치 ==========
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 650])  # 좌측 450, 우측 650
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #4a90d9;
            }
        """)

        main_layout.addWidget(splitter)

    def select_source_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "원본 데이터 폴더 선택",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.source_path.setText(folder)
            self.scan_devices(folder)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "출력 폴더 선택",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self.output_path.setText(folder)

    def open_output_folder(self):
        """출력 폴더 열기"""
        folder = self.output_path.text().strip()
        if folder and Path(folder).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.warning(self, "경고", "출력 폴더가 설정되지 않았거나 존재하지 않습니다.")

    def copy_log_to_clipboard(self):
        """로그를 클립보드에 복사"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.log_text.toPlainText())
        self.stats_label.setText("클립보드에 복사됨")

    def save_log_to_file(self):
        """로그를 파일로 저장"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "로그 저장",
            f"conversion_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                self.stats_label.setText(f"저장됨: {Path(filename).name}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 실패: {e}")

    def clear_log(self):
        """로그 지우기 + 카운터 초기화"""
        self.log_text.clear()
        self.stats_label.setText("")

    def detect_devices(self):
        """장비 감지 버튼 클릭"""
        folder = self.source_path.text().strip()
        if not folder:
            QMessageBox.warning(self, "경고", "먼저 원본 데이터 폴더를 선택하세요.")
            return
        if not Path(folder).exists():
            QMessageBox.warning(self, "경고", f"폴더가 존재하지 않습니다:\n{folder}")
            return
        self.scan_devices(folder)

    def scan_devices(self, folder: str):
        """폴더 스캔 및 장비 감지"""
        path = Path(folder)
        self.log_text.clear()
        self.log_text.append(f"[INFO] 폴더 스캔: {folder}")

        # 파서 초기화
        fusion_parser = FusionParser()
        rion_parser = RionParser()

        # 지점 폴더 검색
        point_folders = sorted([
            d for d in path.iterdir()
            if d.is_dir() and (d.name.startswith('N') or d.name.startswith('이동식'))
        ])

        self.device_list.clear()
        self.device_table.setRowCount(0)

        if not point_folders:
            self.log_text.append("[WARN] 지점 폴더를 찾을 수 없습니다.")
            return

        self.device_table.setRowCount(len(point_folders))

        detected_count = 0
        for row, point_folder in enumerate(point_folders):
            point_id, point_name = parse_point_folder(point_folder.name)

            # 장비 감지
            detected_type = '미감지'
            device_folder = None

            fusion_devices = fusion_parser.find_device_folders(point_folder)
            if fusion_devices:
                detected_type = 'Fusion'
                device_folder = fusion_devices[0]
                detected_count += 1
            else:
                rion_devices = rion_parser.find_device_folders(point_folder)
                if rion_devices:
                    detected_type = 'Rion'
                    device_folder = rion_devices[0]
                    detected_count += 1

            # 장비 정보 저장
            device_info = DeviceInfo(
                point_folder=point_folder,
                point_id=point_id,
                point_name=point_name,
                detected_type=detected_type,
                device_folder=device_folder
            )
            self.device_list.append(device_info)

            # 테이블에 추가
            self.device_table.setItem(row, 0, QTableWidgetItem(point_id))
            self.device_table.setItem(row, 1, QTableWidgetItem(point_name))

            # 감지 상태
            status_item = QTableWidgetItem(detected_type)
            if detected_type == '미감지':
                status_item.setBackground(QColor(255, 200, 200))  # 빨간색 배경
            else:
                status_item.setBackground(QColor(200, 255, 200))  # 초록색 배경
            self.device_table.setItem(row, 2, status_item)

            # 장비 선택 콤보박스
            combo = QComboBox()
            combo.addItems(["자동", "Fusion", "Rion", "건너뛰기"])
            combo.setProperty("row", row)
            combo.currentTextChanged.connect(self.on_device_selection_changed)
            self.device_table.setCellWidget(row, 3, combo)

        self.log_text.append(f"[INFO] 발견된 지점: {len(point_folders)}개")
        self.log_text.append(f"[INFO] 장비 감지: {detected_count}개 성공, {len(point_folders) - detected_count}개 미감지")

        if detected_count < len(point_folders):
            self.log_text.append("[WARN] 미감지된 지점은 '장비 선택' 열에서 수동으로 지정하세요.")

    def on_device_selection_changed(self, text: str):
        """장비 선택 변경 시 처리"""
        combo = self.sender()
        row = combo.property("row")

        if 0 <= row < len(self.device_list):
            if text == "자동":
                self.device_list[row].selected_type = ''
            elif text == "건너뛰기":
                self.device_list[row].selected_type = '미감지'
            else:
                self.device_list[row].selected_type = text

    def get_weighting(self) -> str:
        """가중치 설정 반환"""
        idx = self.weight_combo.currentIndex()
        if idx == 0:
            return 'LAS'
        elif idx == 1:
            return 'LCS'
        else:
            return 'both'

    def start_conversion(self):
        """변환 시작"""
        # 입력 검증
        if not self.source_path.text():
            QMessageBox.warning(self, "경고", "원본 데이터 폴더를 선택하세요.")
            return

        if not self.output_path.text():
            QMessageBox.warning(self, "경고", "출력 폴더를 선택하세요.")
            return

        if not self.site_name.text():
            QMessageBox.warning(self, "경고", "사이트명을 입력하세요.")
            return

        if not self.device_list:
            QMessageBox.warning(self, "경고", "먼저 원본 폴더를 선택하여 장비를 스캔하세요.")
            return

        # 미감지 장비 확인
        undetected = []
        for info in self.device_list:
            effective_type = info.selected_type or info.detected_type
            if effective_type == '미감지':
                undetected.append(info.point_id)

        if undetected:
            reply = QMessageBox.question(
                self, "확인",
                f"다음 지점의 장비가 미감지되어 건너뜁니다:\n{', '.join(undetected)}\n\n계속하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # 설정 생성
        config = ConversionConfig(
            source_path=Path(self.source_path.text()),
            output_path=Path(self.output_path.text()),
            site_name=self.site_name.text().strip(),
            round_number=self.round_combo.currentText() if self.include_round.isChecked() else None,
            weighting=self.get_weighting(),
            include_bands=self.include_bands.isChecked(),
            output_csv=self.output_csv.isChecked()
        )

        # UI 상태 변경
        self.convert_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        self.stats_label.setText("")
        self.stats_label.setStyleSheet("color: #888; font-size: 11px;")

        # 워커 시작
        self.worker = ConverterWorker(config, self.device_list)
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.on_log)
        self.worker.stats.connect(self.on_stats)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def cancel_conversion(self):
        """변환 취소"""
        if self.worker:
            self.worker.cancel()
            self.log_text.append("[INFO] 취소 요청됨...")

    def on_progress(self, percent: int, message: str):
        """진행 상황 업데이트"""
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)

    def on_log(self, message: str):
        """로그 추가 (색상 적용)"""
        # 색상 결정
        if '[ERROR]' in message:
            color = '#f87171'  # 빨간색
        elif '[WARN]' in message or '심각' in message:
            color = '#fbbf24'  # 노란색
        elif message.startswith('✓') or '[정상]' in message:
            color = '#4ade80'  # 녹색
        elif '저장:' in message and '86400/86400' in message:
            color = '#4ade80'  # 녹색 (완전한 데이터)
        else:
            color = '#d4d4d4'  # 기본 회색

        # HTML로 색상 적용
        escaped = message.replace('<', '&lt;').replace('>', '&gt;')
        self.log_text.append(f'<span style="color: {color};">{escaped}</span>')

        # 스크롤 맨 아래로
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_stats(self, warnings: int, errors: int):
        """경고/에러 카운트 업데이트"""
        parts = []
        if warnings > 0:
            parts.append(f"경고: {warnings}")
        if errors > 0:
            parts.append(f"에러: {errors}")
        if parts:
            self.stats_label.setText(" | ".join(parts))
            # 에러가 있으면 빨간색
            if errors > 0:
                self.stats_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
            else:
                self.stats_label.setStyleSheet("color: #ffc107; font-size: 11px;")

    def on_finished(self, success: bool, message: str):
        """변환 완료"""
        self.convert_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText(message)
            self.log_text.append(f"\n[INFO] {message}")
            QMessageBox.information(self, "완료", message)
        else:
            self.progress_label.setText("실패")
            self.log_text.append(f"\n[ERROR] {message}")
            QMessageBox.critical(self, "오류", message)

        self.worker = None


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
