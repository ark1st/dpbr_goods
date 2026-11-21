# 단풍바람 굿즈 제작

현재 선택은 **3T / A3 420×297mm / 100% 실척 / 시험편 없음**입니다.

- **main**: 마스코트·로고·Len·키링 편집 소스, 현재 A3 생성·검사 코드.
- **output_len**: 현재 A3 제작 파일, 시안, ZIP과 검사 기록.
- **raw**: 이전 브랜치 전체, 구버전·사용 중지 시안·중복 원본의 보관본. 제작용이 아닙니다.

## 현재 출력

1. [추가 이미지 + 새튀 4종 · 42조각](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/02_extra_sheet/3T/sheet_01)
2. [어센트 카데나 · 5조각](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/04_ascent_cadena/sheet_01)
3. [Len 일반·DOT 공통 세트 + 튀잉 4종 · 12조각](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/05_len/3T/sheet_01)

확정분은 **A3 3장 / 59조각**입니다. 줄줄이 키링8개는 두 시트에 분산되어 있습니다.
Len은 공통 받침·배경 한 세트에 일반·DOT 캐릭터 두 종류를 교체합니다. 원본 그림 높이76mm, 받침275×60mm를 유지했습니다.

별도 선택안: [새 Len PAD · 7조각 / A3 1장](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/06_len_pad/3T/sheet_01).
정리 중 원격에서 들어온 새 디자인도 보존하고, 시험편을 제외해 A3로 옮겼습니다. 이것까지 출력하면4장·66조각입니다.
PAD의 받침은280×71.2235mm로 기존 Len과 다릅니다.

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

공유 중간 파일을 사용하므로 생성 명령은 순서대로 실행합니다. 부분 생성은 `--only 02_extra`, `--only 04_ascent`, `--only 05_len`, `--only 06_len_pad`입니다.
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
