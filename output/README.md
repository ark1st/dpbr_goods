# 출력 파일 — V3

현재 도안은 **4세트 + 로고 단독 4개 = 총 16조각**입니다.
한 세트는 가람·단팽이·미니 로고 각 1개입니다. 기본 작업영역은 **300×160mm**입니다.

![16조각 배치 미리보기](production_v3/preview/board_layout.png)

빨간 선은 확인용 미리보기에서 보이도록 두껍게 표시했습니다. 실제 커팅 파일은 0.001mm 선입니다.

## 아크릴 키링

- [아크릴 파일 ZIP 다운로드](Danpungbaram_V3_SMALL_BATCH_16pcs.zip)
- [사용 안내서와 실물 크기 시안](production_v3/00_REVISION_GUIDE.pdf)
- [UV 인쇄용 투명 PNG · 300ppi](production_v3/01_PRINT_300ppi.png)
- [Illustrator 원본](production_v3/02_MASTER.ai) / [VectorCraft 원본](production_v3/03_MASTER.vectorcraft)
- [커팅 전용 SVG](production_v3/04_CUT_ONLY.svg) / [커팅 전용 PDF](production_v3/04_CUT_ONLY.pdf)
- [규격 및 간격 검증 결과](production_v3/validation_report.json)

파란 기준선은 위치 맞춤용이며 커팅 대상이 아닙니다. UV 인쇄에는 그림과 파란 선만 사용합니다.
인쇄와 커팅은 **같은 크기·같은 원점, 실제 크기 100%**를 사용합니다.
커팅선은 외곽 16개 + 구멍 16개, 총 32개 폐곡선입니다.

`production_v3/optional_800x600/`은 동일한 16조각을 800×600mm 판 좌표로 옮긴 대안입니다.
기본 파일과 함께 중복 출력하지 않습니다. 안내문의 장비 작업영역은 800×500mm이므로 큰 판을 사용할 수 있는지는 현장에서 확인해야 합니다.

## 밝은색 티셔츠

- [로고 PNG · 300ppi](tshirt/tshirt_logo_70mm_300ppi.png) / [600ppi](tshirt/tshirt_logo_70mm_600ppi.png)
- [Illustrator 원본](tshirt/tshirt_logo_70mm.ai) / [PDF](tshirt/tshirt_logo_70mm.pdf) / [SVG](tshirt/tshirt_logo_70mm.svg)
- [A4 실물 크기 확인용](tshirt/tshirt_70mm_A4_ACTUAL_SIZE.pdf)

이름 없는 로고만 들어 있으며 높이는 70mm입니다. A4 시안의 글자와 확인자는 전사 대상이 아닙니다.

소스 코드와 원본 자료는 [`main` 브랜치](https://github.com/ark1st/dpbr_goods/tree/main)에 있습니다.
