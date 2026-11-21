# 단풍바람 굿즈 제작

main은 원본·설정·생성 코드, [output_len/output](https://github.com/ark1st/dpbr_goods/tree/output_len/output)은 인쇄·재단 결과물입니다.
[2026-11-20 제작 기준 반영 기록](docs/2026-11-20-production-requirements.md)

## 현재 A3 출력 파일 · 2026-11-21

대지 420×297mm, 실제 크기 100%. 3T/5T 대안 중 하나씩 선택하면 총 **A3 3장**입니다.

2. [추가 이미지38 + 제공 새튀4 · 42조각 / A3 1장](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/02_extra_sheet)
3. [줄줄이 키링8개는 추가 이미지·Len 대지에 분산](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/03_linked_keyrings)
4. [어센트 카데나만 · 4판 + 받침1 / A3 1장](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/04_ascent_cadena)
5. [Len 일반+DOT 공통세트8 + 시험편2 + 튀잉4 · 14조각 / A3 1장](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/05_len)

Len은 배경·받침 한 세트에 일반/DOT 캐릭터를 교체합니다. 조각 크기는 그대로입니다.
이전 키링 독립판과 어센트 전체2장 합본은 이번 출력에서 퇴역했습니다.

[전체 A3 안내·ZIP·시안](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release) · [재생성·병합 기록](docs/a3-release.md)
어센트는 원본 약 3.2mm 홈을 보존했습니다. 5T용이 아니며 실물 끼움 시험이 필요합니다.
이전 추가 이미지·개별 튀잉·Len 대지는 참고용으로 퇴역했습니다.

기존 별도 제작물: [단바 합본](https://github.com/ark1st/dpbr_goods/tree/output_len/output/combined_diorama_v3), [마스코트·로고 키링](https://github.com/ark1st/dpbr_goods/tree/output_len/output/production_v4), [티셔츠](https://github.com/ark1st/dpbr_goods/tree/output_len/output/tshirt_fronts).

## 제작 규격

가람·단팽이의 원본 카드 높이 비율135/356과 그림 크기를 유지했습니다.
일반 투명 외곽2.5mm, 구멍-외곽2.5mm, 고리 구멍 지름4mm.
레이저 선 자체는빨강 #FF0000 / **0.001mm**입니다. 연결판·받침 어깨는 구조상 더 넓습니다.

디오라마 그림: 가람56.78×65mm, 단팽이28.30×24.65mm, 제목 포함 로고160×56.33mm.
받침100×36mm 및140×38mm. 공통18mm 돌기, 3T/5T 대안과 실물 끼움 시험편 포함.
새yun은 그림 크기를 유지하고 끼움부만3T/5T로 조정했습니다. 슬롯은20.2×3.2/5.2mm입니다.
카라비너4종은 높이50/55mm와 여백2/2.5mm를 비교합니다.
카라비너 장착 구멍은 A=지름1.2/간격4mm, B=1.4/4mm, C=1.6/4mm, D=1.4/5mm입니다.
구매 부품9×23.5×1mm에 맞는지 실제 조립으로 확인하는 시험값이며, 본체에 레이저 타공이 포함됩니다.

## 칼선 품질 검사

[필수 제작 검사 기준](docs/laser-cut-quality.md) · [수정 전후와 전수 검사](https://github.com/ark1st/dpbr_goods/tree/output_len/output/cut_quality)

매 배포에서 실제 AI·PDF·SVG·VectorCraft 경로를 검사합니다. 미세 선분·자기교차·중복·열린 경로가 있으면 실패합니다. GitHub에서도 회귀 검사와 게시된 AI/PDF 검사를 실행합니다.

## 재생성

Python3.11 이상과 [VectorCraft CLI](https://github.com/storytold/vectorcraft/releases)를 사용합니다.
requirements.txt의 패키지를 설치합니다. CLI가 PATH에 없으면 VECTORCRAFT_CLI에 절대 경로를 지정합니다.

```sh
python -m pip install -r requirements.txt
python scripts/build_goods_v3.py
python scripts/build_diorama.py
python scripts/build_logo_diorama.py
python scripts/build_carabiner.py
python scripts/build_combined_diorama.py
python scripts/build_extra_sheet_38.py
python scripts/build_tshirt_fronts.py
python scripts/build_linked_tuiing.py
python scripts/build_a3_release.py
python scripts/package_a3_release.py
python -m unittest discover -s tests
python scripts/verify_release.py
```

명령은 순서대로 실행합니다. 공유 중간 파일 때문에 동시 실행하지 않습니다.
build_goods_v3.py는 기존 호출 호환성을 위해 파일명을 유지하며 현재 output/production_v4를 생성합니다.
엑스트라 시트는 저장소의 이전33조각 PDF와 assets/external/yun_image_sd_stand.ai를 사용합니다.
기존 build_extra_sheet.py는 과거 합본용이며 최신38조각 생성에는 사용하지 않습니다.
Len 원본 생성기는 `build_len_diorama.py`, DOT 캐릭터 대안은 `build_len_diorama_dot.py`입니다.
현재 A3 빌더는 고정 커밋·해시의 원본 출력에서 재배치하므로 원본 생성기를 먼저 다시 실행할 필요가 없습니다.

두께 변경 예:
```sh
python scripts/build_diorama.py --part-thickness 3 --base-thickness 5 --slot-width 2.80 --name mixed_3T_5T
python scripts/build_logo_diorama.py --part-thickness 3 --base-thickness 5 --slot-width 2.80 --name mixed_3T_5T
```
2.80은 실제 시험에서 그 값을 선택했을 때의 예시입니다.

## 원본 및 검증

- [가람·단팽이·로고 소스](assets/README.md)
- [추가yun 원본](assets/external/README.md)
- [티셔츠 소스 및 처리 기록](assets/tshirt/README.md)
- configs/: 실척 설정. output/: 결과물. tmp/: 중간 파일.
- 출력별 validation_report.json에 치수·레이어·폐곡선·간격 검증을 기록합니다.
- 실물 인쇄·재단·끼움·금속 게이트 개폐는 시험 전입니다.

캐릭터·로고의 권리는 원저작자에게 있습니다. 별도 공개 라이선스를 부여하지 않았습니다.
