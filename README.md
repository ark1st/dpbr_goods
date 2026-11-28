# 단풍바람 굿즈 제작

현재 선택은 **3T / A3 420×297mm / 100% 실척 / 시험편 없음**입니다.

- **main**: 마스코트·로고·Len·키링 편집 소스, 현재 A3 생성·검사 코드.
- **output_len**: 현재 A3 제작 파일, 시안, ZIP과 검사 기록.
- **raw**: 이전 브랜치 전체, 구버전·사용 중지 시안·중복 원본의 보관본. 제작용이 아닙니다.

## 현재 출력

1. [혼합 A3 1 · 추가 이미지·새튀·카데나 판2개 · 41조각](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/02_extra_sheet/3T/sheet_01)
2. [혼합 A3 2 · Len 일반·DOT·튀잉·카데나 나머지3개 · 15조각](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/05_len/3T/sheet_01)

확정분은 **A3 최소2장 / 56조각**입니다. 세 제작 그룹의 조각을 두 시트에 섞었습니다. 단팽이1개·단풍바람 로고 키링2개는 제외했고 줄줄이 키링8개는 모두 포함합니다.
Python으로 실제 칼선의 회전·이동·충돌·3mm 간격을 검사했습니다. 구멍을 제외한 조각 면적이 A3 한 장보다 크고 두 장 배치가 성립하므로 최소 장수는2장입니다. 상세 수치는 출력의 `A3_VALIDATION.json`에 있습니다.
Len은 공통 받침·배경 한 세트에 일반·DOT 캐릭터를 교체합니다. 일반76mm, 도트50mm로 수정했으며 도트 돌기를 발 아래로 옮겼습니다. 공통 받침275×60mm·18.8×3mm 홈을 유지하고, 도트 돌기는18mm 폭·2.6mm 깊이로 새로 만들었습니다.

별도 선택안: [새 Len PAD · 7조각 / A3 1장](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/06_len_pad/3T/sheet_01)과 [Len ORIGIN · 7조각 / A3 1장](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/07_len_origin/3T/sheet_01)입니다.
이 둘까지 출력하면4장·70조각입니다. Len PAD의 받침은280×71.2235mm, ORIGIN의 받침도280×71.2235mm(홈8개)로 기존 Len과 치수가 다릅니다. ORIGIN V8는 소유자의 바로잡음("벚꽃-나무는 하나여야지", 별도 에셋은 "저 문")대로 매화 나무 전체(줄기·가지·꽃송이)를 한 조각 판에 인쇄하고 가지·꽃송이 사이는 실제 칼선 구멍으로 하늘·달이 보이게 한 세트입니다(떨어진 꽃송이는 2.75mm 투명 연결재로 붙이고, 좁은 틈은 뒷판 색으로 인쇄). V2–V7에서 뒷판에 인쇄하던 격자 문 좌우는 1.0mm 테두리의 별도 판(행 47)으로 뒷판 앞에 세우고, 뒷판은 하늘·파도를 그 자리로 이어 붙였습니다. 렌은 V6처럼 잘라내지 않고 통째로 받침에 앉고 뱀·달·받침·테두리 1.0mm는 V6 그대로입니다(V3·V4·V5·V7은 출시 전 대체).
[전체 출력 안내·시안·ZIP](https://github.com/ark1st/dpbr_goods/tree/output_len/output) · [보관본](https://github.com/ark1st/dpbr_goods/tree/raw)
5T는 별도 대안입니다. 현재3T와 둘 다 출력하지 않습니다. 카데나는5T용이 아닙니다.

## 재생성

Python3.11 이상과 설치된 VectorCraft CLI가 필요합니다. CLI가 PATH에 없다면 `VECTORCRAFT_CLI`에 실행 파일 경로를 지정합니다.

```sh
git fetch origin raw
python -m pip install -r requirements.txt
python scripts/build_a3_release.py
python scripts/package_a3_release.py
python -m unittest discover -s tests
python scripts/verify_release.py
```

공유 중간 파일을 사용하므로 생성 명령은 순서대로 실행합니다. 부분 생성은 `--only 02_extra`, `--only 05_len`, `--only 06_len_pad`, `--only 07_len_origin`입니다. 카데나는 앞의 두3T 시트에 포함되어 독립 출력하지 않습니다.
`configs/a3_placements.json`의 검토한 좌표로 같은 배치를 재현합니다. 고정 커밋·SHA-256의 입력은 `tmp/source_cache/`로 복원합니다. 구버전 폴더를 output에 다시 만들지 않습니다.
가람·단팽이·심벌 SVG는 `python scripts/export_art_masters.py`로 재생성합니다.

## 검사와 보존

[칼선 규칙](docs/laser-cut-quality.md) · [A3 규격과 원본](docs/a3-release.md) · [저장소 정리 기록](docs/repository-cleanup.md)

모든 현재 SVG·AI·PDF·VectorCraft 칼선, 인쇄 PDF/PNG, ZIP 구성과 해시를 검사합니다.
보호 대상 외부30조각의 원본은 수정하지 않고 수치상 특이사항을 따로 기록합니다.
미등록 출력·퇴역 파일·시험편이 현재 목록에 들어오면 검사를 실패시킵니다.
실물 재단·끼움·커프·인쇄 정합은 소프트웨어 검사만으로 검증되지 않습니다.

[마스코트·로고 소스](assets/README.md) · [제공 원본 보존](assets/external/README.md)

캐릭터·로고 권리는 원저작자에게 있습니다. 별도의 공개 라이선스를 부여하지 않았습니다.
