# 그림 소스

이 폴더는 `main`에서 관리하는 그림 소스입니다. 완성된 인쇄·재단 배치는 `output_len` 브랜치의 `output/`에 있습니다.

- `mascot_card.png`: 가람·단팽이의 원본 카드 참고 이미지.
- `source_logo.ai`: 전달받은 원본 로고 AI.
- `artwork.json`: 제작용 벡터 마스터. 마스코트는 원본 카드를 대조해 다시 그린 후 눈·그림자를 수정한 버전입니다.
- `masters/garam.svg`, `masters/danpaengi.svg`: 위 마스터의 그림만 담은 편집용 SVG. 재단선·구멍·받침대가 없습니다.
- `masters/logo_symbol.svg`: 이름 없는 심벌만 담은 벡터 소스.
- `logo_full.svg`: 원본 AI에서 추출한 심벌과 ‘단풍바람’ 전체 제목. 원본 경로와 비율을 유지했습니다.
- `logo_full_provenance.json`: 전체 로고의 원본·경로 수·검증 정보.
- `linked_tuiing/`: 기본·황올·탄·안튀잉 원본 PNG와 같은 픽셀·색·투명도를 보존한 벡터 SVG.

편집용 SVG의 캔버스는 소스 기준 크기입니다. 실제 제작 치수와 끼움 규격은 `configs/` 및 `output_len`의 해당 제작 파일을 사용하세요.
`python scripts/export_art_masters.py`로 `artwork.json`의 편집용 SVG를 다시 만들 수 있습니다.
