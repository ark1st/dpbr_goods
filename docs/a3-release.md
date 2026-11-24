# 아크릴판 제작 규칙

사용자 최종 고정:1·2페이지는 옛 인쇄 실물판을 사용하며 파일도 수정하지 않습니다. 현재 파일의28개 원시 SHA256은 configs/a3_release.json의 fixed_source_page3.frozen_pages와8b8ff2c 원본에 고정했습니다. 무인자 전체 빌드와1·2페이지 재생성은 생성기가 차단합니다.

3페이지는 assets/incoming/fixed_page3.ai(SHA256 3cfadac25e60f7650ac18dcf4f1972e078bff9a5adb6fab49b0b34ca51e82fc0)의 기존26조각/73폐곡선/21이미지와 파란 기준선을 유지합니다. 추가 배치만 configs/fixed_page3_additions.json에 저장하고, 원본곡선·이미지·마스크·기준선과 모든새 도안을 독립 검증합니다.

원본의 세 쌍 간격은2.2580706/2.3025761/2.7087347mm입니다. 원본의8mm 미만 여백8곳도 그대로 잠그며 다른 도안에는 예외가 적용되지 않습니다. 모든새조각은 간격3mm/여백8mm 이상이어야 합니다.

원본 별받침/구멍/돌기는 직접 복제합니다. 새 캐릭터의 다른 외곽은 알파8 초과 그림에2.5mm 여백과 국소적 곡선 정리를 적용하고 cubic으로 맞춥니다. 키링 새 고리구멍 약2.5mm, 별받침 고리3mm와 장착홈 약15.91×3mm를 구분합니다. 기존 튀잉4종의4mm 구멍은 보존합니다. 정확한 외곽·돌기·홀·홈은 고정 AI 및 canonical곡선으로 대조합니다.

[인쇄소용 페이지 목록](../output/print_delivery/README.md)에서 3·4페이지 A3와 800×500mm 5T 어센트 판을 확인할 수 있습니다. 렘샤·적매화검·마가다락방 제로 합본·무한이의 신규 키링에는 상단 연결 구멍이 하나씩 있습니다. 튀잉 네 종류에는 상하 연결 구멍이 있습니다.

PDF에서 native로 가져올 때 극미세 원본선이 바뀌는 문제는 SVG 원문 좌표/제어점으로 LASER_CUT만 구성하는 scripts/native_cut_preservation.py로 방지합니다. 원본 이미지는 다시 그리지 않습니다. 인쇄소에는 같은 폴더의 01_PRINT_300ppi.png와 02_CUT_WITH_BLUE.ai를 보냅니다. AI 안의 파란 선은 위치 맞춤용입니다. native의 아트 레이어와 내장 이미지 바이트가 변하지 않았는지도 확인합니다.

ZIP/시험쿠폰/테스트키는 만들지 않습니다. 검증은유닛테스트 및 scripts/verify_release.py 전수검사를 사용하며, source이미지/벡터/기계치수와1·2페이지 파일 해시를 함께 검증합니다. 실제 절단·끼움·백색잉크는 별도 물리 검증이 필요합니다.

이전 설계 규칙과 가이드 비교판의 기록은 [8b8ff2c 보관본](https://github.com/ark1st/dpbr_goods/blob/8b8ff2c/docs/a3-release.md)에 있습니다. 사용자가 제공한 [제작 가이드](https://docs.google.com/document/d/1zasgvxLgu7rkULyPR1h_cZRGx2P14C4--0cpYaosGhA)의 원형받침 비교안은 이전 선택안이며 현재 고정3페이지와 별개입니다.
