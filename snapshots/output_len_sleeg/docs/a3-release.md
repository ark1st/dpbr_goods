# A3 재배치·병합 기록

2026-11-21 사용자 요청: 원격 출력 병합, kimyun_ascent.ai와 줄줄이키링.zip 추가, 이번 제작판을 A3로 전환.

- 원격 Len 작업: `d17b590` (`output_len_sleeg`). 출력 브랜치에서 3방향 병합하고, 소스·에셋·설정만 main으로 통합합니다.
- main과 output_len에 이미 있던 매끄러운 칼선 수정과 자동 검사를 유지합니다.
- 기존 추가 이미지 38조각 및 튀잉 소스는 `configs/a3_release.json`의 커밋·SHA-256으로 고정했습니다.
- 새 제공 원본은 `assets/external/ascent_original` 및 `assets/external/linked_supplied`에 보존합니다.

## 재생성

```powershell
python scripts/build_a3_release.py
python scripts/package_a3_release.py
python -m unittest discover -s tests
python scripts/verify_release.py
```

부분 재생성은 `--only 02_extra`, `--only 03_linked`, `--only 04_ascent`, `--only 05_len`을 사용합니다.
원본 출력이 없는 checkout에서는 고정된 커밋에서 필요한 파일만 복원합니다.
원본 해시가 달라지면 중단하며, 새 입력의 검토 후 설정을 갱신해야 합니다.

## 검사 범위

각 조각에 대해 그림·백색·재단에 같은 이동/90도 회전을 적용합니다. 배율은 1입니다.
외부 30개 경로는 곡선 명령을 보존하며, 검사기의 보호 분류는 새 위치의 명시적 영역에 연결합니다.
단순히 예전 drawing index를 새 배치에 재사용하지 않습니다.
Len의 생성 외곽은 모두 `laser_paths.cut_path`를 통과시킵니다. 기존 오차 상한 0.035mm가 적용됩니다.
내보낸 원본 대비 배치 오차 상한은 0.002mm이며, 구멍·홈·돌기 등 모든 경로를 대조합니다.

전수 검사는 A3 SVG, AI, 레이어 PDF, CUT_ONLY PDF, VectorCraft를 포함합니다.
추가 A3 검사는 7개 대지의 수량, 실제 크기, PNG 300ppi, 원본 경로, 인쇄 PDF의 픽셀 일치, ZIP 파일 해시를 검사합니다.
구 527×204mm 추가 시트, 55×75mm 튀잉 시트, 320×370mm Len은 원본·참고용이며 현재 제작판으로 배포하지 않습니다.

PDF 인쇄 파일은 원래 그림 데이터를 보존합니다. AI는 PDF 호환 레이어 파일이며 VectorCraft 전용 편집 상태는 별도 파일입니다.
일부 편집 파일에는 크기를 유지한 600ppi 그림을 넣어 반복 클리핑으로 생기는 과도한 편집 데이터와 메모리 사용을 방지합니다.
재단은 항상 벡터이며, 인쇄 PDF에는 이 편집용 래스터화를 적용하지 않습니다.

실물 시험 미완료. 어센트의 3.2mm 홈·3mm 돌기, 좌우 홈 약 0.195mm 세로 차이, 받침 5개와 빈 효과판 1개는 제공 원본대로 보존합니다.
이 기록은 장비 커프·실제 판 두께·끼움·인쇄 정합을 보증하지 않습니다.
