# Len PAD 편집 원본

원격 커밋 bcc9d2e에서 추가된 그림과 준비된 받침 그림을 그대로 보존했습니다. 새 이미지를 생성하지 않았습니다.
`original_dimensions.json`은 원래 설계 치수를 기록한 자료입니다. 과거 시험편 설정도 기록에 남아 있지만, 현재 빌더는 그 시험편을 생성하지 않습니다.
원래 생성 코드와 전체 제작판은 [raw의 incoming 스냅샷](https://github.com/ark1st/dpbr_goods/tree/raw/snapshots/output_len_incoming)에 있습니다.

현재 A3 제작은 `scripts/build_a3_release.py --only 06_len_pad`를 사용합니다.
받침 1개 + 파츠 6개, 총 7조각입니다. 3T와 5T는 대안이며 돌기·그림 크기는 원격 원본 그대로입니다. 받침 홈만 칼 폭 보정값으로 다시 그립니다([보정 규칙](../../docs/a3-release.md#len-홈-끼움-보정-이슈-1)).
[현재 A3 파일](https://github.com/ark1st/dpbr_goods/tree/output_len/output/a3_release/06_len_pad)

`prepared/provenance.json`은 원래 기여자가 받침 그림의 예시 슬롯 흔적을 처리한 기록입니다. 이번 정리에서 그 그림을 추가로 수정하지 않았습니다.
