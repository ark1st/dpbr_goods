# 단풍바람 굿즈 제작

티셔츠, 아크릴 키링, 끼움형 디오라마의 벡터 원본과 출력 파일 생성 코드입니다.

## 브랜치

- `main`: 소스 코드와 제작에 필요한 원본 자료.
- [`output`](https://github.com/ark1st/dpbr_goods/tree/output/output): 생성된 출력 파일. 인쇄할 때는 이 브랜치의 최신 파일을 사용합니다.

## 끼움형 디오라마 V2 (2026-11-20)

**가람 + 단팽이 + 받침대, 1세트 3조각**의 기본형입니다.
받침대 **100×36mm**로 V1보다 면적을 약54% 줄였습니다.
가람 그림56.78×65mm, 단팽이28.30×24.65mm로 원본 카드의 가로세로 비율과 상대 높이를 유지했습니다.
가람 갓의 그림자와 단팽이 눈 모양·기울기·위치를 원본과 대조해 수정했습니다.
두 캐릭터의 돌기 폭은18mm로 같아 위치를 바꾸거나 다른 캐릭터로 교체할 수 있습니다.

- [3T/5T 제작 파일과 조립 시안](https://github.com/ark1st/dpbr_goods/tree/output/output/diorama_v2)
- [전체 ZIP](https://github.com/ark1st/dpbr_goods/blob/output/output/Danpungbaram_Diorama_V2_3T_5T.zip)
- `scripts/build_diorama.py`: 두께별 파일 생성.
- `configs/diorama.json`: 기본 디자인의 설계 치수.

홈 너비는 **캐릭터 판**의 두께, 돌기 길이는 **받침대 판**의 두께를 기준으로 따로 설정합니다.
기본 돌기 길이는 받침대 두께에서0.40mm 뺀 값(3T 2.60mm /5T 4.60mm)입니다.
3T/5T 기본 홈 너비3.00/5.00mm는 커프 보정 전 절단경로의 시작값입니다.
실물 끼움은 아직 시험하지 않았습니다. 동봉된9개 홈 시험판을 같은 판·같은 가공 설정으로 잘라 홈 너비를 먼저 선택하세요.

```powershell
python scripts/build_diorama.py
# 아래 2.80은 시험에서 그 값을 선택했을 때의 예시입니다.
python scripts/build_diorama.py --part-thickness 3 --base-thickness 3 --slot-width 2.80 --name calibrated_3T
# 캐릭터3T + 받침대5T 조합도 지원합니다. 각 부품은 해당 두께의 판에 따로 출력합니다.
python scripts/build_diorama.py --part-thickness 3 --base-thickness 5 --slot-width 2.80 --name mixed_3T_5T
```

출력은 `output/diorama_v2/`에 저장됩니다. 두께 인수에는 실측 소수값도 입력할 수 있습니다.
기본 디자인 크기를 바꾸면 배치와 안내서도 함께 검토해야 합니다. 두께와 홈 너비를 조정할 때에는 위 명령의 인수를 사용하세요.

## 아크릴 키링 도안 (V3)

4세트 + 로고 단독 4개, 총 **16조각**입니다. 한 세트는 가람·단팽이·미니 로고 각 1개입니다.
V2의 12조각보다 조금 늘리고 작업영역은 320×180mm에서 **300×160mm**로 줄였습니다.
조각 사이 실제 최소 간격은 **7.07mm**입니다. [배치 미리보기](https://github.com/ark1st/dpbr_goods/blob/output/output/production_v3/preview/board_layout.png).

| 그림 | 높이 |
|---|---:|
| 가람 | 55mm |
| 단팽이 | 20.86mm |
| 미니 로고 | 18mm |
| 단독 로고 | 30mm |

단팽이는 같은 원본 카드에서 측정한 가람과의 높이 비율 `135/356`을 유지합니다.
그림과 재단선은 최소 3.5mm, 구멍 가장자리와 그림은 5mm 이상, 구멍과 아크릴 외곽은 4mm 이상입니다. 고리 구멍은 지름 4mm입니다.

## 출력 파일

`output` 브랜치의 `output/production_v3/`:

- `01_PRINT_300ppi.png`: UV 인쇄용, 투명 배경, 파란 사각 기준선 포함.
- `02_MASTER.ai`, `03_MASTER.vectorcraft`: 3개 레이어를 보존한 편집 원본.
- `04_CUT_ONLY.svg`, `04_CUT_ONLY.pdf`: 빨간 커팅선만 포함, 0.001mm.
- `00_REVISION_GUIDE.pdf`: 사용 순서와 A4 실측 시안.
- `optional_800x600/`: 동일한 16조각을 800×600mm 판 좌표에 둔 대안. 기본 파일과 함께 중복 출력하지 않습니다.

티셔츠용 70×70mm 로고 파일은 같은 브랜치의 `output/tshirt/`에 있습니다.

파란 기준선은 인쇄와 커팅의 위치·방향을 맞추는 표식이며 커팅 대상이 아닙니다.
인쇄·커팅에서 같은 버전을 사용하고 실제 크기 100%로 출력합니다.

## 실행

macOS 또는 Windows에서 Python 3.11 이상과 [VectorCraft CLI](https://github.com/storytold/vectorcraft/releases)를 사용합니다. macOS에서는 앱과 별도로 CLI ZIP을 받아 실행 파일을 PATH나 가상환경의 `.venv/bin/`에 두거나, `VECTORCRAFT_CLI`에 실행 파일의 절대 경로를 지정합니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/build_goods_v3.py
.venv/bin/python scripts/build_tshirt.py
```

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts/build_goods_v3.py
.\.venv\Scripts\python scripts/build_tshirt.py
```

Windows에서는 PATH나 기본 설치 경로에서 CLI를 찾습니다. 필요하면 `VECTORCRAFT_CLI`에 `vectorcraft-cli.exe` 경로를 지정합니다. 한글 안내서는 macOS에서 AppleGothic, Windows에서 맑은 고딕으로 생성합니다.

빌드 중간 파일은 `tmp/`, 최종 파일은 `output/`에 생성됩니다. `main`에서는 둘 다 Git 추적 대상에서 제외합니다.
검증은 실제 판 크기·레이어·PNG 해상도·기준선 네 변·폐곡선 수·간격을 검사하며 `validation_report.json`으로 저장합니다. 실물 인쇄·커팅 시험을 대신하지 않습니다.

### 첨부 AI 두 파일 합본

```sh
.venv/bin/python scripts/build_extra_sheet.py "/path/to/아크릴키링.ai" "/path/to/yun_image.ai"
```

`output/extra_sheet/`의 합본은 **640 × 225 mm 한 장**입니다. 원본의 그림과 칼선을 크기 변형 없이 함께 이동하고, 커팅선은 #FF0000 / 0.001 mm로 출력합니다. `01_COMBINED_SHEET.pdf`는 기본으로 컬러 인쇄 레이어만 표시합니다. UV 인쇄에는 `02_PRINT_300ppi.png`, 커팅에는 `03_CUT_ONLY.pdf`를 같은 원점과 실제 크기 100%로 사용합니다. `04_WHITE_INK_MASK_300ppi.png`는 yun 도안의 백색 잉크 영역을 검게 표시한 분판 데이터입니다. VectorCraft에서 편집하려면 세 레이어가 들어 있는 `05_MASTER.vectorcraft`를 엽니다.

## 원본

- 로고: 제공된 배포용 AI의 이름 없는 심볼 경로. `assets/source_logo.ai`에 보관.
- 마스코트: [노션의 단바 굿즈 자료](https://ark1st.notion.site/4199cd9d18388078b431c5573819102d)의 카드뉴스를 참고한 벡터 재구성본. 원본 캐릭터 AI는 제공되지 않았습니다.
- 재사용 가능한 벡터: `assets/artwork.json`. 비율 확인용 카드: `assets/mascot_card.png`.

캐릭터·로고의 권리는 원저작자에게 있습니다. 이 저장소에 별도 공개 라이선스를 부여하지 않았습니다.
