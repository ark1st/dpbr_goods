# 티셔츠 그림 소스

- `aing_approved.png`: 사용자가 확인한 아잉 복원 이미지. 투명 배경.
- `aing_user_reference.png`: 전달받은 비교용 원본.
- `changseop_source_1080.jpg`: [동일 구도 사진의 다운로드 출처](https://soundcloud.com/pp3arbjmwn0p).
- `changseop_user_reference.png`: 전달받은500px 참고 원본.
- `provenance.json`: 다운로드 주소와 아잉 생성 프롬프트.

**신창섭은 생성형 AI 보정본을 사용하지 않습니다.** 사용자가 거절한 이미지는 저장소에 넣지 않았습니다.
제작 파일의 확대와 투명 처리 방법은 `scripts/build_tshirt_fronts.py`에 있으며 얼굴을 다시 만들지 않습니다.
최종 PNG·시안은 `output_len` 브랜치의 `output/tshirt_fronts/`에 있습니다.
