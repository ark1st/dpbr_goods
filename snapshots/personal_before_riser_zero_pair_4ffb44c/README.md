# 단풍바람 굿즈 제작

현재 제작분은 **3T 아크릴, A3 가로 420 × 297 mm, 실제 크기 100%, 5장에 110조각**입니다.

[최종 제작 파일·개인별 위치](output/a3_release) · [개별 편집 에셋](output/individual_assets) · [A3 생성 규칙](docs/a3-release.md)

기존 4장에 있는 84조각의 위치와 칼선을 유지했습니다. 자투리에는 개인별 스탠드 12조각과 키링 2개를 넣었고, 나머지 키링 12개는 다섯 번째 장에 배치했습니다. 새 키링 14개는 각각 위아래 지름 4 mm 구멍으로 연결합니다. 그림 높이는 40 mm 그대로이며, 아래 연결부를 포함한 완성 높이는 약 71 mm입니다.

현재 제작에는 각 시트 폴더의 PDF, PNG, AI와 VectorCraft 파일을 사용합니다. 이전 A3 ZIP은 퇴역 보관본이며 새 ZIP은 만들지 않습니다. Len PAD는 보류 중이고 양검 단독판은 중복 참고본입니다. 이미 인쇄한 500 × 800 mm 판은 별도 재커팅용입니다.

입력은 `output_len@e0abac0`와 `dpbr_of@59c513d`로 고정합니다. 보관 원본은 해시를 확인한 뒤 `tmp/source_cache`에 복원하며, 그림은 제공 원본을 그대로 사용합니다. 검증을 마친 변경은 작업 브랜치에서 `output_len`에 반영합니다. `main`으로는 푸시하지 않습니다.

```sh
python -m pip install -r requirements.txt
python scripts/build_a3_release.py --only 11_ascent_remaining
python scripts/build_a3_release.py --only 19_personal_fill
python scripts/build_individual_assets.py --only-group 11_ascent_remaining
python scripts/build_individual_assets.py --only-group 19_personal_fill
python scripts/package_a3_release.py
python -m unittest discover -s tests
python scripts/verify_release.py
```

Python 3.11 이상, VectorCraft CLI, Poppler가 필요합니다. macOS에서도 생성과 검사가 가능합니다. 중간 파일을 공유하므로 생성 명령은 위 순서대로 실행합니다.

[칼선품질규칙](docs/laser-cut-quality.md) · [보존정책](docs/repository-cleanup.md)

5장 배치는 자동 검사로 확인했습니다. 4장 배치 가능성은 열려 있으며, 실물의 커프, 두께, 끼움, 링 간섭, 인쇄 정합은 아직 시험하지 않았습니다. 새 개인 도안의 백색 인쇄는 RIP에서 그림의 알파 채널을 기준으로 설정합니다.

캐릭터·로고 권리는 원저작자에게 있습니다. 별도의 공개 라이선스를 부여하지 않았습니다.
