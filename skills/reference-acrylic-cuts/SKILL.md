---
name: reference-acrylic-cuts
description: Prepare or review acrylic cutting contours and sheet layouts in dpbr_goods using the supplied 4번째_아크릴판.ai, designated by the user as locked page 3, as the visual and geometric reference. Use for acrylic cut-path generation, repair, placement, or production-file checks in this project.
---

# 단바 아크릴 칼선 · 원본 기준

작업 루트는 `/Users/ark1st/Documents/01 Works/dpbr/dpbr_goods`다. 사용자가 제공한 기준 원본의 보존본은 `assets/incoming/fixed_page3.ai` (SHA-256 `3cfadac25e60f7650ac18dcf4f1972e078bff9a5adb6fab49b0b34ca51e82fc0`)다. 최초 제공 파일은 `/Users/ark1st/Downloads/4번째_아크릴판.ai`다. 보존본의 해시를 확인하고 칼선 확대 이미지와 수치로 실제 형상을 살펴본다. 원본이 없거나 해시가 다르면 다른 파일을 원본이라고 가정하지 말고 차이를 확인한다. 기준판의 스타일은 인쇄소 사양이나 물리 강도 보증이 아니다.

기준판은 A3 420×297mm, 외곽 26개와 내부 47개를 포함한다. 실제 측정에서 키링 구멍은 대체로 지름 약 2.5mm이고, 별 받침의 원형 구멍은 약 3mm, 홈은 약 15.91×3mm다. 원본 중 일부 원형은 약 2.26×2.50mm로 찌그러져 있다. 이 수치는 **해당 기준판의 관찰값**이며, 다른 제품의 기존 구멍·홈 규격을 덮어쓰는 지시가 아니다. 300dpi에서 알파 250 이상인 그림을 표본으로 측정하면 대다수의 그림–외곽 최소 거리는 약 1.5~2.5mm다. 흐린 효과나 다른 도안에는 동일 값이 보장되지 않으므로 실제 그림 전체와 외곽을 따로 검사한다.

## 신규 도안에 기준 스타일 적용

`scripts/reference_cut_style.py`는 기준 파일의 해시를 확인한다. 별 받침·구멍·탭은 기준 벡터를 직접 복사해 이동한다. 새 캐릭터 외곽은 원본 제작 알고리즘을 알아낸 것이 아니라 실측 스타일을 재현한 근사다. 키링 전처리는 투명 여백만 잘라 원본 RGBA 픽셀을 보존하며, 스탠드는 준비된 이미지를 입력한다. 외곽 생성은 알파 8 초과 실루엣에 2.5mm 오프셋·0.20mm 단순화·0.4mm 국소 완화·0.015mm 미세 단순화를 적용한 뒤 `cut_path`로 맞춘다. 약한 투명 효과를 포함한 원본 이미지 전체와 조립부가 제대로 유지되는지 결과를 확대 검토한다.

작업 루트에서 스탠드 또는 줄줄이 키링 후보를 생성한다. `--outdir`은 임시 작업 폴더로 지정한다. 이 명령은 JSON과 검토 이미지를 만들며, 그 자체가 생산 승인이나 인쇄 파일은 아니다.

```sh
.venv/bin/python scripts/reference_cut_style.py --kind stand --reference assets/incoming/fixed_page3.ai --images 'assets/chain_keyring/추가스탠드/렘샤_stand60_prepared.png' 'assets/chain_keyring/추가스탠드/적매화검_stand60_prepared.png' --outdir tmp/reference-cuts/stands
.venv/bin/python scripts/reference_cut_style.py --kind chain --reference assets/incoming/fixed_page3.ai --images 'assets/chain_keyring/추가스탠드/렘샤_fly300.png' --outdir tmp/reference-cuts/chains
```

프로젝트 통합에는 `build_reference_additions(reference_path, output_dir, muhani_image)`도 사용한다. 기존 그림·칼선은 그대로 보존하고 새 도안의 결과만 검사 후 승인된 빈 공간에 배치한다.

## 형상과 배치

- 도안의 자연스러운 실루엣을 따른 원본 외곽과 필요한 여백을 사용한다. 오목한 곳을 없애기 위해 볼록 껍질, 일률적인 큰 라운드, 임의의 3mm closing, 커다란 투명판을 덧씌우지 않는다. 미세한 재단 불량을 고칠 때도 필요한 부분에 한정하고 원본과 확대 비교한다.
- `scripts/laser_paths.py`의 `cut_path` 또는 `draw_cut_pdf`로 레이저 곡선을 내보낸다. 래스터 추적 결과를 수천 개의 직선으로 그대로 직렬화하지 않는다. 상세 규칙은 작업 루트의 `docs/laser-cut-quality.md`를 따른다.
- 그림·흰색·칼선은 동일한 원점과 배율을 유지한다. 구멍의 위치·지름, 받침 홈과 돌기, 조립 간섭, 사용자 지정 외곽을 보존한다. 명시된 홈 보정 요청과 같은 승인된 예외는 치수를 기록하고 원본과 따로 비교한다.
- 기존 배치·인쇄물을 임의로 옮기거나 크기를 줄이지 않는다. 사용자가 자투리를 채우라고 하면 기존 조각의 실제 칼선과 충분한 재단 간격을 유지하면서 빈 공간에만 추가한다. 1·2번 판이 동결된 현재 작업에서는 그 판을 다시 쓰지 않는다. 새로운 지시가 동결 범위를 바꾸면 그 지시를 따른다.
- 1·2번은 이미 인쇄한 옛 실물판을 사용한다. 저장소 사본은 현재 HEAD `8b8ff2c`의 파일 해시로 고정하며 재출력 대상으로 안내하지 않는다. 전체 `build_a3_release.py` 무인자 빌드는 실행하지 않는다. 3번 판은 `python scripts/build_a3_release.py --only 11_ascent_remaining` 경로가 고정판 전용 빌더로 라우팅되는지 확인한 뒤에만 생성한다.
- 기존 외곽이 그림을 가리거나 새 외곽이 인접 그림을 불러오지 않도록, 분리 전후 그림·백색을 별도로 비교한다. 이미지를 생성하거나 다시 그리지 않는다.

## 출력과 검증

- 신규 재단 벡터는 빨강 RGB `255, 0, 0`, 선폭 `0.001 mm`로 유지하고, 파란 위치 기준선은 재단에서 제외한다. 고정 원본73곡선은 두 종류 실측 선폭(0.001mm 및0.01pt≈0.003528mm) 자체를 보존한다. 인쇄·백색·재단 원점과 대지 크기를 맞춘다.
- AI/PDF 편집본은 `LASER_CUT` 레이어를 기본 표시하고 `WHITE_INK_MASK`는 기본 숨김으로 둔다. `01_PRINT.pdf`에는 재단선을 섞지 않는다. AI가 PDF 호환본인지 네이티브 편집본인지 명시한다.
- `python -m unittest discover -s tests`와 `python scripts/verify_release.py`를 실행하고, 대상 AI/PDF/SVG/VectorCraft 칼선과 레이어 상태를 대조한다. 전체 판, 상세 외곽·구멍·홈을 확대해 직접 확인하고 `output/LASER_PATH_AUDIT.json`에 검사 범위와 결과를 기록한다. 원본에서 벗어난 사항이나 검증하지 못한 부분은 따로 보고한다.
- 소프트웨어 검사만으로 실물의 끼움·강도·커프·인쇄 정합이 검증됐다고 말하지 않는다. 사용자가 금지한 시험편·샘플 받침·시험키와 새 ZIP을 만들지 않는다.

SVG는 PDF에서 되읽어 양자화하지 말고 승인된 원문 베지어 제어점을 직접 강체변환해 직렬화한다. native 보존은 `scripts/native_cut_preservation.py`를 쓰며 LASER_CUT만 원문 좌표로 구성하고 나머지 레이어 JSON·내장 이미지 바이트가 불변인지 검사한다. 복사한 탭에 어깨 접속선이 되돌아가면 원본 탭을 바꾸지 말고 이웃 직선의 접속만 단축한다. 개별0도와 실제 판 배치 각도에서 PDF·SVG·native 왕복을 모두 검사한다.
