# 단풍바람 굿즈 제작

현재 제작분은 **3T A3 4장·87조각**, 그리고 **어센트 5T 800×500mm 1장·30조각**입니다.

[최종 3T 출력·개인별 위치](output/a3_release) · [어센트 5T 800×500](output/large_format/ascent_5T_800x500) · [개별 편집 에셋](output/individual_assets) · [A3 제작 규칙](docs/a3-release.md)

개인 스탠드4세트·8조각과 적매화검·렘샤 스탠드2세트·4조각입니다. 마가다락방과 청민예는 각각 알파·베타 그림을 한 판에 나란히 넣고 받침 하나를 사용합니다. 원본 픽셀 기준으로 몸 크기와 발선을 맞추고 몸통 중심 간격을25mm로 좁혔습니다. 무기·효과는 일부 겹칩니다. 이상준과 정지영의 스탠드는 단독 캐릭터입니다.

몸통 아래에 캐릭터당 폭26mm의 투명 지지부를 연결하고, 곡면으로 폭18mm 돌기에 이어지게 했습니다. 무기·효과의 얇은 부분에만 힘이 걸리는 구조를 보강했습니다. 탭18×2.6mm, 받침72×28mm, 홈18.8×3.0mm는 그대로입니다. 실제 강도와 끼움은 미검증입니다.

어센트 전체 30조각은 3T에서 제외하고 5T 별도 판으로 옮겼습니다. 단독 단풍바람 로고도 제외했습니다. 4번의 캐릭터10개를3번으로 옮기고 적매화검·렘샤 스탠드4조각을3번에 추가했습니다. 보강 스탠드 8조각과 연결 키링 14개, Len PAD 7조각은 네 장에 배치했습니다. 줄줄이 키링14개는 알파·베타를 합치지 않으며 기존 상하4mm 구멍과 그림을 유지하고 외곽을 단순화합니다.

새 ZIP은 만들지 않습니다. 이전 ZIP은 퇴역 보관본이며 현재 제작에는 시트 폴더의 PDF·PNG·AI·VectorCraft를 사용합니다. Len PAD와 양검 모두 위 4장에 포함되어 단독 원본판은 중복 출력하지 않습니다. 신규 도안의 백색은 RIP에서 그림 알파 기준으로 설정합니다.

```sh
python scripts/build_a3_release.py --only 11_ascent_remaining
python scripts/build_a3_release.py --only 19_personal_fill
python scripts/build_individual_assets.py --only-group 11_ascent_remaining
python scripts/build_individual_assets.py --only-group 19_personal_fill
python scripts/package_a3_release.py
python -m unittest discover -s tests
python scripts/verify_release.py
```

Python3.11 이상, requirements.txt 의존성, VectorCraft CLI와 Poppler가 필요합니다. 중간 파일을 공유하므로 순서대로 실행합니다. macOS에서도 생성·검사합니다.

변경 전 제작본은 raw의 before_ascent_5t_e4d03cd 스냅샷에 같은 바이트로 보존했습니다. 변경은 작업 브랜치와 output_len에 반영하며 main에는 푸시하지 않습니다. 4장 배치는 검증하지만 3장의 불가능이나 전역 최적을 증명한 것은 아닙니다.

[칼선 품질 규칙](docs/laser-cut-quality.md) · [원본 보존 정책](docs/repository-cleanup.md)

캐릭터·로고 권리는 원저작자에게 있습니다. 별도의 공개 라이선스를 부여하지 않았습니다.
