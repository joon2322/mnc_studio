"""데이터 검증 모듈"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import pandas as pd
import numpy as np

from ..config import EXPECTED_ROWS, FREQUENCY_COLUMNS


@dataclass
class ValidationResult:
    """검증 결과"""
    # 기본 정보
    filename: str
    date: str
    point_id: str
    weighting: str

    # 행 수 검증
    row_count: int = 0
    row_valid: bool = False

    # 커버리지
    spl_valid_count: int = 0
    spl_coverage: float = 0.0
    coverage_level: str = ''  # 정상, 주의, 경고, 심각
    band_valid_count: int = 0
    band_coverage: float = 0.0

    # 이상치 (오류: 0-150 범위 벗어남)
    spl_min: float = 0.0
    spl_max: float = 0.0
    anomaly_count: int = 0
    anomalies: List[str] = field(default_factory=list)

    # 경고 범위 (20-130 벗어남)
    warning_count: int = 0
    warning_values: List[str] = field(default_factory=list)

    # 시간 오류
    time_errors: List[str] = field(default_factory=list)

    # 전체 결과
    is_valid: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_summary(self) -> str:
        """요약 문자열 생성"""
        lines = [
            f"=== {self.filename} ===",
            f"날짜: {self.date} | 지점: {self.point_id} | 가중치: {self.weighting}",
            f"",
            f"[행 수] {self.row_count}/86400 {'✓' if self.row_valid else '✗'}",
            f"[커버리지] SPL: {self.spl_coverage:.1f}% ({self.spl_valid_count}/86400) [{self.coverage_level}]",
        ]

        if self.band_valid_count > 0:
            lines.append(f"           밴드: {self.band_coverage:.1f}% ({self.band_valid_count}/86400)")

        lines.append(f"[SPL 범위] {self.spl_min:.1f} ~ {self.spl_max:.1f} dB")

        if self.anomaly_count > 0:
            lines.append(f"[이상치-오류] {self.anomaly_count}건 (0~150 dB 벗어남)")
            for a in self.anomalies[:3]:
                lines.append(f"  - {a}")
            if len(self.anomalies) > 3:
                lines.append(f"  ... 외 {len(self.anomalies) - 3}건")

        if self.warning_count > 0:
            lines.append(f"[이상치-경고] {self.warning_count}건 (20~130 dB 벗어남)")
            for w in self.warning_values[:3]:
                lines.append(f"  - {w}")
            if len(self.warning_values) > 3:
                lines.append(f"  ... 외 {len(self.warning_values) - 3}건")

        if self.time_errors:
            lines.append(f"[시간 오류] {len(self.time_errors)}건")
            for e in self.time_errors[:3]:
                lines.append(f"  - {e}")

        if self.warnings:
            lines.append(f"[경고] {len(self.warnings)}건")
            for w in self.warnings:
                lines.append(f"  - {w}")

        status = "✓ 정상" if self.is_valid else "✗ 검증 실패"
        lines.append(f"\n결과: {status}")

        return "\n".join(lines)


class DataValidator:
    """데이터 검증기"""

    # 오류 SPL 범위 (확실한 오류)
    SPL_ERROR_MIN = 0.0
    SPL_ERROR_MAX = 150.0

    # 경고 SPL 범위 (실질적 이상치)
    SPL_WARNING_MIN = 20.0
    SPL_WARNING_MAX = 130.0

    # 커버리지 단계별 임계값
    COVERAGE_NORMAL = 0.9     # 90% 이상: 정상
    COVERAGE_CAUTION = 0.7    # 70~90%: 주의
    COVERAGE_WARNING = 0.5    # 50~70%: 경고
    COVERAGE_CRITICAL = 0.1   # 10% 미만: 심각 (is_valid 실패)

    # 연도 유효 범위
    VALID_YEAR_MIN = 2020
    VALID_YEAR_MAX = 2030

    def _get_coverage_level(self, coverage: float) -> str:
        """커버리지 단계 반환"""
        ratio = coverage / 100.0
        if ratio >= self.COVERAGE_NORMAL:
            return "정상"
        elif ratio >= self.COVERAGE_CAUTION:
            return "주의"
        elif ratio >= self.COVERAGE_WARNING:
            return "경고"
        else:
            return "심각"

    def validate(
        self,
        df: pd.DataFrame,
        filename: str,
        date: datetime,
        point_id: str,
        weighting: str
    ) -> ValidationResult:
        """
        DataFrame 검증

        Args:
            df: 검증할 DataFrame
            filename: 파일명
            date: 날짜
            point_id: 지점 ID
            weighting: 가중치

        Returns:
            ValidationResult
        """
        result = ValidationResult(
            filename=filename,
            date=date.strftime('%Y-%m-%d'),
            point_id=point_id,
            weighting=weighting
        )

        # 1. 행 수 검증
        result.row_count = len(df)
        result.row_valid = (result.row_count == EXPECTED_ROWS)
        if not result.row_valid:
            result.warnings.append(f"행 수 불일치: {result.row_count} (예상: {EXPECTED_ROWS})")

        # 2. 커버리지 계산
        if 'spl' in df.columns:
            result.spl_valid_count = int(df['spl'].notna().sum())
            result.spl_coverage = (result.spl_valid_count / EXPECTED_ROWS) * 100
            result.coverage_level = self._get_coverage_level(result.spl_coverage)

            if result.coverage_level == "심각":
                result.warnings.append(f"SPL 커버리지 심각: {result.spl_coverage:.1f}% (50% 미만)")
            elif result.coverage_level == "경고":
                result.warnings.append(f"SPL 커버리지 낮음: {result.spl_coverage:.1f}% (50~70%)")
            elif result.coverage_level == "주의":
                result.warnings.append(f"SPL 커버리지 주의: {result.spl_coverage:.1f}% (70~90%)")

        # 3. 밴드 커버리지 (전체 밴드 평균)
        band_counts = []
        for col in FREQUENCY_COLUMNS:
            if col in df.columns:
                band_counts.append(df[col].notna().sum())

        if band_counts:
            result.band_valid_count = int(np.mean(band_counts))
            result.band_coverage = (result.band_valid_count / EXPECTED_ROWS) * 100

        # 4. 이상치 감지 (오류 + 경고 분리)
        if 'spl' in df.columns:
            spl_valid = df['spl'].dropna()
            if len(spl_valid) > 0:
                result.spl_min = float(spl_valid.min())
                result.spl_max = float(spl_valid.max())

                # 오류 범위 (0-150 벗어남) - is_valid에 영향
                error_low = df[df['spl'] < self.SPL_ERROR_MIN]
                error_high = df[df['spl'] > self.SPL_ERROR_MAX]

                for idx in error_low.index[:5]:
                    ts = df.loc[idx, 'timestamp']
                    val = df.loc[idx, 'spl']
                    result.anomalies.append(f"{ts}: {val:.1f} dB (0 dB 미만)")

                for idx in error_high.index[:5]:
                    ts = df.loc[idx, 'timestamp']
                    val = df.loc[idx, 'spl']
                    result.anomalies.append(f"{ts}: {val:.1f} dB (150 dB 초과)")

                result.anomaly_count = len(error_low) + len(error_high)

                # 경고 범위 (20-130 벗어남) - 경고만, is_valid에 영향 없음
                # 오류 범위와 겹치지 않는 것만 카운트
                warning_low = df[(df['spl'] >= self.SPL_ERROR_MIN) & (df['spl'] < self.SPL_WARNING_MIN)]
                warning_high = df[(df['spl'] > self.SPL_WARNING_MAX) & (df['spl'] <= self.SPL_ERROR_MAX)]

                for idx in warning_low.index[:5]:
                    ts = df.loc[idx, 'timestamp']
                    val = df.loc[idx, 'spl']
                    result.warning_values.append(f"{ts}: {val:.1f} dB (20 dB 미만)")

                for idx in warning_high.index[:5]:
                    ts = df.loc[idx, 'timestamp']
                    val = df.loc[idx, 'spl']
                    result.warning_values.append(f"{ts}: {val:.1f} dB (130 dB 초과)")

                result.warning_count = len(warning_low) + len(warning_high)

                if result.warning_count > 0:
                    result.warnings.append(f"경고 범위 이상치: {result.warning_count}건 (20~130 dB 벗어남)")

        # 5. 시간 오류 감지
        if 'timestamp' in df.columns:
            # 중복 타임스탬프
            duplicates = df['timestamp'].duplicated()
            dup_count = duplicates.sum()
            if dup_count > 0:
                result.time_errors.append(f"중복 타임스탬프: {dup_count}건")

            # 시작/종료 시간 확인
            if len(df) > 0:
                first_ts = df['timestamp'].iloc[0]
                last_ts = df['timestamp'].iloc[-1]

                # pandas Timestamp를 datetime으로 변환
                if hasattr(first_ts, 'to_pydatetime'):
                    first_ts = first_ts.to_pydatetime()
                if hasattr(last_ts, 'to_pydatetime'):
                    last_ts = last_ts.to_pydatetime()

                expected_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
                expected_end = date.replace(hour=23, minute=59, second=59, microsecond=0)

                # 시작/종료 시간이 datetime이면 비교
                if isinstance(first_ts, datetime):
                    if first_ts.replace(microsecond=0) != expected_start:
                        result.time_errors.append(f"시작 시간 불일치: {first_ts} (예상: {expected_start})")
                    if last_ts.replace(microsecond=0) != expected_end:
                        result.time_errors.append(f"종료 시간 불일치: {last_ts} (예상: {expected_end})")

                    # 연도 범위 검증
                    if first_ts.year < self.VALID_YEAR_MIN or first_ts.year > self.VALID_YEAR_MAX:
                        result.time_errors.append(f"연도 범위 오류: {first_ts.year}년 (유효: {self.VALID_YEAR_MIN}~{self.VALID_YEAR_MAX})")

        # 6. 전체 유효성 판정
        coverage_critical = (result.spl_coverage / 100.0) < self.COVERAGE_CRITICAL
        if coverage_critical:
            result.warnings.append(f"커버리지 심각 오류: {result.spl_coverage:.1f}% (10% 미만 - 검증 실패)")

        result.is_valid = (
            result.row_valid and
            result.anomaly_count == 0 and
            len(result.time_errors) == 0 and
            not coverage_critical  # 커버리지 10% 미만이면 실패
        )

        return result

    def validate_batch(
        self,
        results: List[ValidationResult]
    ) -> str:
        """
        배치 검증 결과 요약

        Args:
            results: ValidationResult 목록

        Returns:
            전체 요약 문자열
        """
        if not results:
            return "검증할 결과가 없습니다."

        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid

        # 커버리지별 파일 수
        complete_days = sum(1 for r in results if r.spl_coverage >= 99.9)  # 100% (부동소수점 오차 고려)
        partial_days = total - complete_days

        total_anomalies = sum(r.anomaly_count for r in results)
        total_warnings_spl = sum(r.warning_count for r in results)
        total_warnings = sum(len(r.warnings) for r in results)

        # 날짜 범위
        dates = sorted(set(r.date for r in results))
        date_range = f"{dates[0]} ~ {dates[-1]}" if len(dates) > 1 else dates[0] if dates else "-"

        lines = [
            "=" * 50,
            "         변환 결과 요약 리포트",
            "=" * 50,
            "",
            f"날짜 범위: {date_range}",
            f"총 파일 수: {total}",
            f"  - 검증 통과: {valid}",
            f"  - 검증 실패: {invalid}",
            "",
            f"일별 커버리지:",
            f"  - 완전한 날짜 (100%): {complete_days}개",
            f"  - 부분 데이터 (<100%): {partial_days}개",
            "",
            f"이상치(오류): {total_anomalies}건 (0~150 dB 벗어남)",
            f"이상치(경고): {total_warnings_spl}건 (20~130 dB 벗어남)",
            "",
        ]

        # 문제 있는 파일 목록
        if invalid > 0:
            lines.append("문제 파일:")
            for r in results:
                if not r.is_valid:
                    issues = []
                    if not r.row_valid:
                        issues.append("행수")
                    if r.anomaly_count > 0:
                        issues.append(f"오류{r.anomaly_count}")
                    if r.time_errors:
                        issues.append("시간")
                    if (r.spl_coverage / 100.0) < self.COVERAGE_CRITICAL:
                        issues.append("커버리지심각")
                    lines.append(f"  - {r.filename}: {', '.join(issues)}")
            lines.append("")

        # 개별 파일 요약
        lines.append("-" * 50)
        lines.append("개별 파일 상세:")
        lines.append("-" * 50)

        for r in results:
            status = "✓" if r.is_valid else "✗"
            lines.append(f"{status} {r.filename}")
            lines.append(f"   SPL: {r.spl_coverage:.1f}% [{r.coverage_level}] | 범위: {r.spl_min:.1f}~{r.spl_max:.1f} dB")
            if r.warnings or r.anomalies or r.time_errors or r.warning_count > 0:
                if r.anomaly_count > 0:
                    lines.append(f"   오류: {r.anomaly_count}건")
                if r.warning_count > 0:
                    lines.append(f"   경고: {r.warning_count}건")
                if r.time_errors:
                    lines.append(f"   시간오류: {len(r.time_errors)}건")
                if r.warnings:
                    for w in r.warnings[:2]:
                        lines.append(f"   - {w}")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)
