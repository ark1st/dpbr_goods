# 이미 인쇄된 판 재커팅

[500×800mm 단바 판 재커팅 전용](https://github.com/ark1st/dpbr_goods/tree/output_len/output/recut_only/danbar_500x800). 원본 위치·배율·77조각·294폐곡선을 보존한 새 칼선입니다. 새 인쇄나A3대지를 추가하지 않습니다. 현재 A3는 양검을 포함한4장이며 Len PAD는 보류합니다.

# 단풍바람 제작 파일

현재 선택은 **3T · A3 420×297mm · 실제 크기100%**입니다. 자동 맞춤을 끄고 인쇄·백색·재단의 원점과 배율을 동일하게 사용합니다.

## 내일 최종 출력

1. [기존 혼합 A3 1 · 추가 이미지·새튀·카데나 판2개 / 43조각 · 양검 캐릭터·키링 포함](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/02_extra_sheet/3T/sheet_01)
2. [기존 혼합 A3 2 · Len·DOT·튀잉·카데나 나머지 / 16조각 · 양검 받침 포함](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/05_len/3T/sheet_01)
3. [어센트 · 카데나 제외 · 완전히 별도 A3 2장 / 25조각](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/11_ascent_remaining)

확정 구성은 **4장·84조각**입니다. 어센트는 기존 조각과 섞지 않고, 원본의 무인쇄 패널31도 제외했습니다. 양검을 포함한 혼합59조각과 어센트25조각은 각각 한 장보다 큰 재료 면적이며 두 장씩 배치되어, 별도 배치 조건에서 최소4장입니다.
어센트의 인쇄 판은104×62.807mm(돌기3mm 포함), 받침은104×30mm입니다. 홈약20.2×3.2mm·돌기폭20mm를 보존합니다. [치수 검증·실물 검증의 한계](https://github.com/ark1st/dpbr_goods/blob/output_len/output/a3_release/11_ascent_remaining/SIZE_VERIFICATION.json).

양검 3조각은 혼합2장에 포함했습니다. [Len PAD 원본](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/06_len_pad)은 출력 보류입니다. 기존 혼합2장은 간격을 포함한 면적 하한상 수용할 수 없고, 어센트2장도 원본 크기의 유효 배치를 찾지 못했습니다. 후자는 불가능 증명이 아닙니다. [검토 기록](https://github.com/ark1st/dpbr_goods/blob/output_len/output/a3_release/OPTIONAL_FILL_ASSESSMENT.json). 5T는 대안이며 현재3T와 함께 출력하지 않습니다.

## 개별 에셋과 재생성

[개별141에셋 · 두께 대안 포함](https://github.com/ark1st/dpbr_goods/tree/output_len/output/individual_assets) · [전체 A3 출력판·시안·ZIP](https://github.com/ark1st/dpbr_goods/tree/output_len/output) · [raw 보관본](https://github.com/ark1st/dpbr_goods/tree/raw).
개별 에셋은 원본 방향·크기로 그림·백색·벡터 칼선을 분리한 파일이고, A3는 출력용 배치입니다. 기준 곡선은 `configs/individual_contours.json`에 고정합니다.

```sh
python -m pip install -r requirements.txt
python scripts/build_a3_release.py
python scripts/build_individual_assets.py
python scripts/ascent_size_audit.py
python scripts/package_a3_release.py
python -m unittest discover -s tests
python scripts/verify_release.py
```

Python3.11 이상과 설치된 VectorCraft CLI가 필요합니다. `VECTORCRAFT_CLI`로 별도 경로를 지정할 수 있습니다. 입력은 고정 커밋·SHA-256으로 `tmp/source_cache`에 복원합니다. 부분 생성은 `--only 11_ascent_remaining` 등이며, 공유 중간 파일을 쓰므로 생성 명령은 순서대로 실행합니다.

[칼선 규칙](docs/laser-cut-quality.md) · [A3 배포 규칙](docs/a3-release.md) · [마스코트·로고 소스](assets/README.md).
시험편·시험키·샘플 받침과 생성형 이미지 편집을 포함하지 않습니다. 보호 외부30개 도안은 원본 곡선을 보존하며 발견 사항을 별도로 기록합니다. 모든 현재 칼선 형식·인쇄·ZIP을 검사합니다. 소프트웨어 검사는 실물 두께·커프·끼움·인쇄 정합을 보증하지 않습니다.
작업과 배포는 output_len_sleeg에서 진행하고 output_len에 병합합니다. main에는 push하지 않습니다.
캐릭터·로고 권리는 원저작자에게 있으며 별도 공개 라이선스를 부여하지 않았습니다.
