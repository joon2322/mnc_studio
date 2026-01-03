# Fusion 오디오 BID 파일 형식

> Fusion 소음측정기의 Audio BID 파일 형식 및 설정 감지 방법

---

## 개요

| 항목 | 값 |
|------|-----|
| **파일 위치** | `세션폴더/Audio/*.bid` |
| **파일 형식** | Raw PCM (헤더 없음) |
| **비트 깊이** | 32-bit signed integer (little-endian) |
| **채널** | Mono |
| **세그먼트** | 30분 단위 |

---

## 샘플레이트 (가변)

Fusion 장비는 다양한 샘플레이트를 지원하며, **세션별로 다를 수 있음**.

| 샘플레이트 | 30분 파일 크기 | 비고 |
|-----------|---------------|------|
| 51.2 kHz | 368,640,000 bytes | 고해상도 |
| **25.6 kHz** | **184,320,000 bytes** | **기본값** |
| 12.8 kHz | 92,160,000 bytes | 저해상도 |
| 6.4 kHz | 46,080,000 bytes | |
| 3.2 kHz | 23,040,000 bytes | |
| 1.6 kHz | 11,520,000 bytes | |

**계산식**: `파일크기 = 샘플레이트 × 1800초 × 4bytes`

---

## 설정 파일에서 샘플레이트 읽기

### 경로

```
세션폴더/
├── Audio/
│   └── *.bid
└── settings/
    └── configuration/
        └── *.xml  ← 여기서 읽기
```

### XML 형식

```xml
<SamplingFrequency>25.6</SamplingFrequency>
<!-- 가능한 값: 51.2, 25.6, 12.8, 6.4, 3.2, 1.6 (kHz) -->
```

### 파싱 코드

```python
import re
from pathlib import Path
from typing import List

def get_sampling_frequency(session_path: Path) -> int:
    """
    세션의 샘플레이트 읽기

    - 최신 수정 시간 파일 우선
    - 공백/개행 허용
    - UTF-16/UTF-8 BOM 지원

    Args:
        session_path: 세션 폴더 경로 (예: .../20251124_000000_000000/)

    Returns:
        샘플레이트 (Hz), 기본값 25600
    """
    config_dir = session_path / "settings" / "configuration"

    if not config_dir.exists():
        return 25600  # 기본값

    # XML 파일 목록 (최신 수정 시간 순 정렬)
    xml_files: List[Path] = list(config_dir.glob("*.xml"))
    xml_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    for xml_file in xml_files:
        try:
            content = xml_file.read_bytes()
            text = _decode_xml_content(content)

            # <SamplingFrequency>25.6</SamplingFrequency> 파싱 (공백 허용)
            match = re.search(
                r'<SamplingFrequency>\s*([\d.]+)\s*</SamplingFrequency>',
                text,
                re.IGNORECASE
            )
            if match:
                freq_khz = float(match.group(1))
                return int(freq_khz * 1000)  # kHz → Hz
        except Exception:
            continue

    return 25600  # 기본값
```

---

## 설정 프로파일

Fusion 장비는 여러 설정 프로파일을 지원:

| 프로파일 | 파일명 | 용도 |
|---------|--------|------|
| military | `military.xml` | 군 소음 측정 (기본) |
| default_ENV | `default_ENV.xml` | 환경 소음 측정 |

**주의**: 같은 장비라도 측정 중간에 프로파일이 변경될 수 있음!

**다중 XML 처리**: 폴더에 여러 XML 파일이 있을 경우, **최신 수정 시간 파일**을 우선 사용합니다.

### 실제 사례

```
N-10(217) 장비:
├── 2025-08-15 ~ 08-16 초반: default_ENV.xml (51.2 kHz)
└── 2025-08-16 후반 ~      : military.xml   (25.6 kHz)
```

---

## BID → WAV 변환

### 핵심 로직 (32-bit 피크 정규화)

정식 Fusion 프로그램과 100% 동일한 알고리즘입니다.

```python
import numpy as np
import wave

FULL_SCALE = 2_147_483_642  # INT32_MAX - 5 (정식 프로그램 동일)

def convert_bid_to_wav(
    bid_path: Path,
    wav_path: Path,
    sample_rate: int = 25600
):
    """
    BID 파일을 WAV로 변환 (32-bit 피크 정규화)

    Args:
        bid_path: 입력 BID 파일
        wav_path: 출력 WAV 파일
        sample_rate: 샘플레이트 (Hz) - 설정 파일에서 읽어야 함!
    """
    # BID 읽기: 32-bit little-endian signed integer
    raw = np.fromfile(bid_path, dtype='<i4')
    raw_64 = raw.astype(np.int64)  # 오버플로우 방지

    # 피크값 계산
    max_abs = int(np.max(np.abs(raw_64)))

    # 정수 나눗셈으로 스케일링 (부호 보존)
    num = raw_64 * FULL_SCALE
    scaled = (np.sign(num) * (np.abs(num) // max_abs)).astype(np.int32)

    # WAV 쓰기 (32-bit)
    with wave.open(str(wav_path), 'wb') as wav:
        wav.setnchannels(1)           # mono
        wav.setsampwidth(4)           # 32-bit = 4 bytes
        wav.setframerate(sample_rate) # 동적 샘플레이트!
        wav.writeframes(scaled.tobytes())
```

**핵심 규칙**:
- `FULL_SCALE = 2,147,483,642` (INT32_MAX가 아님!)
- 정수 나눗셈(`//`) 사용 필수 (부동소수점 사용 시 LSB 오차)
- 검증: 미여도, 낙동, 수원 데이터에서 100% 샘플 일치 확인

**금지**: 16-bit 변환(`>> 8`) 사용 금지 - 일부 데이터에서 89% 클리핑 발생!

---

## 검증 방법

### 파일 크기로 샘플레이트 역산

```python
def verify_sample_rate(bid_path: Path, expected_rate: int) -> bool:
    """설정 파일의 샘플레이트와 실제 파일 크기 일치 확인"""
    file_size = bid_path.stat().st_size
    duration = 1800  # 30분
    bytes_per_sample = 4  # 32-bit

    expected_size = expected_rate * duration * bytes_per_sample

    # 부분 파일 허용 (마지막 세그먼트)
    if file_size == expected_size:
        return True
    elif file_size < expected_size:
        # 부분 파일 - 비율로 검증
        ratio = file_size / expected_size
        return 0 < ratio < 1

    return False
```

---

## 요약

1. **BID 파일은 헤더가 없음** - Raw PCM 데이터
2. **샘플레이트는 XML에서 읽기** - `settings/configuration/*.xml`
3. **세션마다 설정이 다를 수 있음** - 반드시 개별 확인
4. **비트 깊이는 항상 32-bit** - Fusion 고정
5. **채널은 항상 Mono** - Fusion 고정

---

**최종 업데이트**: 2026-01-03
