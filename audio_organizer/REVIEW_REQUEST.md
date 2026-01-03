# 외부 검토 요청: 32-bit 피크 정규화 구현

**요청일**: 2026-01-03
**버전**: Audio Organizer v1.1.0
**검토 대상**: BID → WAV 변환 알고리즘

---

## 변경 사항 요약

### 이전 (v1.0.0)
```python
# 16-bit 비트 시프트 방식 (클리핑 발생)
raw_data = np.fromfile(bid_path, dtype='<i4')
audio_16bit = (raw_data >> 8).astype(np.int16)  # 문제!
```

### 이후 (v1.1.0)
```python
# 32-bit 피크 정규화 (정식 프로그램 동일)
FULL_SCALE = 2_147_483_642

raw = np.fromfile(bid_path, dtype='<i4')
raw_64 = raw.astype(np.int64)  # 오버플로우 방지
max_abs = int(np.max(np.abs(raw_64)))

num = raw_64 * FULL_SCALE
scaled = (np.sign(num) * (np.abs(num) // max_abs)).astype(np.int32)
```

---

## 검토 포인트

### 1. 알고리즘 정확성
- [ ] `FULL_SCALE = 2,147,483,642` (INT32_MAX - 5) 맞는가?
- [ ] 정수 나눗셈(`//`) 사용이 정식 프로그램과 동일한가?
- [ ] 부호 처리 `np.sign(num) * (np.abs(num) // max_abs)` 정확한가?

### 2. 오버플로우 방지
- [ ] `int64` 변환으로 `raw * FULL_SCALE` 오버플로우 방지 충분한가?
- [ ] 최종 `int32` 캐스팅 안전한가?

### 3. 엣지 케이스
- [ ] `max_abs == 0` (무음 파일) 처리 적절한가?
- [ ] 최대값이 정확히 INT32_MAX인 BID 파일 처리 가능한가?

---

## 수정된 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/processors/fusion_processor.py` | `_convert_bid_to_wav()` 알고리즘 변경 |
| `src/config.py` | `FUSION_FULL_SCALE`, `OUTPUT_SAMPLE_WIDTH=4` 추가 |
| `main.py` | CLI 기본, GUI 레거시 분리 |

---

## 검증 방법

### 1. 단일 파일 테스트
```bash
cd /opt/mnc-system/mnc_studio/audio_organizer
source ../venv/bin/activate

python3 << 'EOF'
import numpy as np
from pathlib import Path

FULL_SCALE = 2_147_483_642

# 테스트 BID 파일 경로
bid_path = Path("테스트파일.bid")
raw = np.fromfile(bid_path, dtype='<i4')
raw_64 = raw.astype(np.int64)
max_abs = int(np.max(np.abs(raw_64)))

num = raw_64 * FULL_SCALE
scaled = (np.sign(num) * (np.abs(num) // max_abs)).astype(np.int32)

print(f"max_abs: {max_abs:,}")
print(f"스케일 후 범위: [{scaled.min():,}, {scaled.max():,}]")
print(f"피크가 FULL_SCALE인가: {abs(scaled.min()) == FULL_SCALE or scaled.max() == FULL_SCALE}")
EOF
```

### 2. 정식 프로그램 출력과 비교
```bash
# 정식 프로그램 WAV와 새 구현 WAV 비교
python3 << 'EOF'
import numpy as np

official = np.memmap("정식프로그램.wav", dtype='<i4', mode='r', offset=44)
ours = np.memmap("새구현.wav", dtype='<i4', mode='r', offset=44)

diff = official.astype(np.int64) - ours.astype(np.int64)
print(f"차이 최대: {np.max(np.abs(diff))}")
print(f"일치율: {100 * np.sum(diff == 0) / len(diff):.4f}%")
EOF
```

---

## 검토자 코멘트

(검토 후 작성)

```
[ ] 승인
[ ] 수정 필요
[ ] 반려

사유:



서명:                        일자:
```
