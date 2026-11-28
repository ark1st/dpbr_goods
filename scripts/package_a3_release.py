"""Package only registered A3 plates; never recreate retired output folders."""
from pathlib import Path
import json,zipfile,shutil
from source_cache import source_path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output';BASE=OUT/'a3_release'

def write(p,text):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8',newline='\n')

def main():
    cfg=json.loads((ROOT/'configs/a3_release.json').read_text(encoding='utf-8'))
    m=json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
    assert set(m['groups'])==set(cfg['current_groups'])
    m.update(revision=cfg['revision'],selected_thickness='3T',optional_groups=cfg['optional_groups'],test_pieces_included=False)
    write(BASE/'manifest.json',json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    rev=cfg['len_origin_revision'];origin_parts=rev['pieces'];origin_slots=rev['slots']
    origin_preview=rev['preview'];total_with_optional=56+7+origin_parts
    comp=rev['composition'];ch=comp['character'];sn=comp['snake'];tr=comp['tree_piece'];bd=comp['backdrop'];dl,dr=comp['doors'];seat=comp['seating'];feet=seat['feet_and_sword_runs_at_the_base_line'];riser=seat['clear_riser_mm']
    tb=tr['ink_box_in_scene_mm'];triser=next(iter(tr['bud_guard_riser'].values()));md=bd['moon_disc']
    origin_composition=(f"{rev['product'].split()[-1]} 구도(V7에서 나무를 한 조각으로, 문을 별도 판으로): 렌 {ch['configured_art_height_mm']:.0f}mm 그림({ch['effective_ppi'][0]}ppi)을 V4 위치(x={ch['art_center_x_mm']}mm, 앞행 {ch['depth_row_mm']})에서 잘라내지 않고 통째로 보여줍니다. "
        f"긴 쪽 부츠 바닥이 받침 윗면 {feet[1]['lowest_ink_above_base_top_mm']:.1f}mm(투명 테두리 1.0mm), 다른 부츠가 {feet[2]['lowest_ink_above_base_top_mm']:.1f}mm, 칼끝이 {feet[0]['lowest_ink_above_base_top_mm']:.1f}mm에 있어 다리가 받침까지 내려온 앉은 자세입니다(V6 그대로). "
        f"발밑 돌기 창에서 실루엣이 12mm 하중경로 하한보다 좁으므로 bud-guard가 다리 사이(홈 중심 x={seat['tab_cx_scene_mm'][0]:.0f}mm)에 폭 {riser['width']}mm 투명 리서를 홈 선 위 {riser['top_above_slot_line']}mm까지 세웠습니다(인쇄 없음, 엉덩이 아래 유일한 지지). "
        f"뱀 {sn['art_mm'][1]:.0f}mm는 V4 위치(x={sn['art_center_x_mm']}mm, 뒷행 {sn['depth_row_mm']}) 그대로입니다. "
        f"매화 나무는 소유자 결정(\"벚꽃-나무는 하나여야지\")대로 한 조각입니다: 03_blossom_tree.png 전체(줄기·가지·꽃송이)를 {tr['configured_art_height_mm']:.0f}mm 그림(원본 {tr['embedded_ppi']}ppi)으로 원본 해상도에서 시계방향 {tr['rotate_deg_clockwise']}° 돌려 통째로 세우는 판, x {tb['x'][0]:.0f}–{tb['x'][1]:.0f}mm·받침 위 {tb['z_above_base_top'][0]:.0f}–{tb['z_above_base_top'][1]:.0f}mm, 줄기 밑동 x≈{tr['tab_x_scene_mm']:.0f}mm 뒷행 {tr['depth_row_mm']}에 18mm 돌기, 좁은 뿌리 아래 {triser['riser_width_mm']}mm 투명 리서(홈 선 위 {triser['riser_top_above_slot_mm']}mm), 최소 테두리 {tr['minimum_art_to_cut_mm']}mm. "
        f"불투명 픽셀을 1.5mm 열기한 것이 절단 골격이라 가지·꽃송이 사이는 실제 칼선 구멍({len(tr['openings_in_scene_mm'])}개, 하늘·달이 보임)이 되고, 골격에서 떨어진 꽃송이 {tr['detached_clusters']}개는 각자의 가지를 따라 {tr['connector_width_mm']}mm 폭 투명 연결재(가지 인쇄)로 붙였으며, 칼선으로 못 자르는 좁은 틈({tr['printed_sky_fill_mm2']:.0f}mm²)은 투명 아크릴 대신 밤하늘색으로 인쇄했습니다. 최소 폭 {tr['minimum_feature_mm']}mm, 구멍 가장자리 최소 폭 {tr['minimum_feature_with_openings_mm']}mm. "
        f"문은 소유자가 별도 에셋으로 원한 것(\"저 문\")이라 06_lattice_doors.png의 격자 문 좌우를 각각 {dl['art_mm'][0]:.1f}×{dl['art_mm'][1]:.0f}mm / {dr['art_mm'][0]:.1f}×{dr['art_mm'][1]:.0f}mm 판(투명 테두리 1.0mm, 18mm 돌기, 행 {dl['depth_row_mm']})으로 V2–V7에서 인쇄했던 자리(x {dl['ink_box_in_scene_mm']['x'][0]:.0f}–{dl['ink_box_in_scene_mm']['x'][1]:.0f}mm, x {dr['ink_box_in_scene_mm']['x'][0]:.0f}–{dr['ink_box_in_scene_mm']['x'][1]:.0f}mm)에 뒷판 앞에 세웠습니다. 뒷판에는 창을 인쇄하지 않고 하늘·파도 그림을 그 자리(좌 30.4mm·우 30.5mm)로 거울 반사로 이어 붙였고 격자 구멍은 테두리 후 2.5mm 미만이라 자르지 않고 밤하늘색으로 인쇄했습니다(최소 폭 {dl['minimum_feature_mm'] or '3.75+'}mm). "
        f"달(지름 {md['diameter_mm']:.0f}mm)은 나무 판 바디에 가려지는 비율 {md['pct_behind_the_tree_plate_body']}%, 앞 판 인쇄에 가려지지 않은 비율 {md['visible_pct_against_printed_ink_of_front_plates']}%입니다.")
    common=f'''**현재 선택: 3T. A3 가로 420×297mm, 실제 크기 100%, 자동 맞춤 해제.**

| 구분 | 시트 | 구성 |
|---|---|---|
| 현재 1 | [혼합 A3 1: 추가 이미지 + 새튀 + 카데나 판 2개](02_extra_sheet/3T/sheet_01) | 41조각 |
| 현재 2 | [혼합 A3 2: Len 일반·DOT + 튀잉 + 카데나 나머지](05_len/3T/sheet_01) | 15조각 |
| 별도 선택안 1 | [새 Len PAD](06_len_pad/3T/sheet_01) | 받침 1 + 파츠 6 = 7조각, 별도 A3 1장 |
| 별도 선택안 2 | [Len ORIGIN](07_len_origin/3T/sheet_01) | 받침 1 + 파츠 {origin_parts-1} = {origin_parts}조각, 별도 A3 1장 |

현재 확정 목록은 **2장 / 56조각**입니다. PAD·ORIGIN까지 별도로 출력하면 **4장 / {total_with_optional}조각**입니다.
단팽이 1개·단풍바람 로고 키링 2개는 제외했습니다. 카데나는 독립 판 없이 두 시트에 나누었습니다.
Python으로 실제 외곽을 회전·이동해 충돌과 간격을 검사했습니다. 56조각의 구멍을 뺀 재료 면적이 A3 한 장보다 크고 두 장 배치가 성립하므로, 현재 구성의 최소 장수는 2장입니다. 수치는 `A3_VALIDATION.json`의 `minimum_sheet_proof`에 있습니다.
PAD는 다른 받침·배경을 쓰는 별도 세트이며, 일반·DOT와 공통 받침을 쓰는 것으로 합치지 않았습니다.
줄줄이 키링 8종은 추가 이미지와 Len에 4개씩 들어 있습니다. 독립 키링 대지는 없습니다.
시험편·샘플 받침·시험키는 어느 현재 파일과 ZIP에도 포함하지 않습니다.

## 제작 파일

- `01_PRINT.pdf` / `01_PRINT_300ppi.png`: 인쇄. PDF에 원래 그림 데이터를 보존했습니다.
- `03_CUT_ONLY.pdf` / `.svg`: 재단. 빨강 #FF0000, 선 두께 **0.001mm**, 안쪽 홈·구멍 먼저.
- `02_MASTER.pdf`: 원본 그림 데이터를 유지한 레이어 PDF.
- `02_MASTER.ai`: PDF 호환 레이어 AI. 편집용 그림은 600ppi, 칼선은 벡터입니다.
- `02_MASTER.vectorcraft`: 네이티브 편집본.
- `04_WHITE_INK_MASK`: 제공된 백색판만 유지. 별도 백색이 없는 그림은 RIP에서 설정합니다.
- `preview.png`, `cut_detail.png`, `PREVIEW_NOT_FOR_CUT.pdf`: 검토용. 재단 파일로 사용하지 않습니다.

파란 사각형은 대지 가장자리에서 4mm 들어간 위치 기준이며 자르지 않습니다.
인쇄·백색·재단 원점과 배율을 동일하게 사용합니다. 조각 간격 3mm 이상, 가장자리 8mm 이상입니다.
도트 렌은 요청에 따라 그림 높이76→50mm로 줄이고 발 아래 돌기를 새로 만들었습니다. 그 외 그림·홈·구멍·돌기는 원래 크기입니다. 외부 30조각의 보호 칼선도 그대로입니다.
ZIP에는 인쇄 PNG·백색 PNG·재단 PDF/SVG·시안·치수 기록이 있습니다. 편집본과 인쇄 PDF는 시트 폴더에서 받습니다.

## 두께와 조립

현재 선택은 **3T**입니다. 추가 이미지·Len·PAD의 5T 파일은 별도 대안이며 둘 다 출력하는 구성이 아닙니다.
카데나는 제공 원본의 약3.2mm 홈·3mm 돌기, 좌우 홈 약0.195mm 높이 차이를 유지했습니다. 5T용이 아닙니다.
Len 공통 받침275×60mm와8개 홈은 유지했습니다. 일반 렌76mm, 도트 렌50mm이며 같은 캐릭터 홈에 교체합니다. 도트 발 아래 돌기는18mm 폭·3T 삽입깊이2.6mm이며, 칼 때문에 왼쪽으로 치우쳤던 위치를 발 중심으로 옮겼습니다.
PAD 받침은280×71.2235mm이며 자체 8개 홈을 사용합니다. 기존 Len과 치수가 다릅니다.
ORIGIN 받침도280×71.2235mm이며 홈{origin_slots}개, 투명 테두리{rev['clear_border_mm']:.1f}mm(모든 판 동일)입니다. 뒤→앞: 하늘(창 자리까지 이어 붙임)·달구름을 인쇄한 뒷판 1장(행 56) → 격자 문 판 좌·우(행 47) → 한 조각 나무 판(줄기·가지·꽃송이, 행 31) → 뱀(행 23) → 받침에 앉은 렌(그림 전체, 행 12).
{origin_composition}
실물 재단·끼움·커프·인쇄 정합은 아직 검증하지 않았습니다.

[칼선 검사](../LASER_PATH_AUDIT.json) · [A3 검사](A3_VALIDATION.json) · [정리·원본 보존 검사](../REPOSITORY_AUDIT.json)

이전 제작판·시험편·중복 ZIP은 [raw 보관 브랜치](https://github.com/ark1st/dpbr_goods/tree/raw)에 있습니다. 새 제작에 사용하지 마세요.
'''
    write(BASE/'README.md','# A3 제작 파일 · 현재 3T\n\n'+common)
    titles={'02_extra_sheet':'혼합 A3 1 · 추가 이미지·새튀·카데나 판2개 · 41조각','05_len':'혼합 A3 2 · Len·튀잉·카데나 나머지3개 · 15조각','06_len_pad':'Len PAD · 별도 선택안 7조각','07_len_origin':f'Len ORIGIN · 별도 선택안 {origin_parts}조각'}
    for cat,title in titles.items():
        text='[현재 3T 제작 파일](3T/sheet_01) · [선택 대안 5T](5T/sheet_01)\n\n![3T 배치](3T/sheet_01/preview.png)\n\n![5T 대안 배치](5T/sheet_01/preview.png)\n'
        if cat=='02_extra_sheet':
            text+='\n현재3T는41조각(카데나 뒤쪽 판2개 포함), 5T대안은39조각(카데나 제외)입니다. 단팽이·단풍바람 로고 키링은 모두 제외했습니다. 카데나의 나머지3개는 혼합A3 2에 있습니다. 조립 순서는 뒤에서 배경0→효과1→캐릭터2→효과3입니다.\n'
        if cat=='05_len':
            for product,name in [('len_diorama_v1','assembly.png')]:
                shutil.copy2(source_path(f'output/{product}/3T/preview/assembly.png'),BASE/cat/name)
            from len_dot_part import render_comparison
            render_comparison(ROOT,BASE/cat/'assembly_dot.png',cfg['len_dot_revision'])
            text+='\n공통 배경·받침 한 세트에 일반76mm·DOT50mm 캐릭터를 교체합니다. 발 아래 돌기 폭18mm, 삽입깊이3T2.6mm. 중복 받침·시험편 없음. 3T에 카데나 나머지3개를 함께 배치했습니다. 5T 대안에는 카데나가 없습니다.\n\n![일반 조립 참고](assembly.png)\n\n![일반·DOT 실제 크기 비율과 새 발 돌기](assembly_dot.png)\n'
        if cat=='06_len_pad':
            shutil.copy2(source_path('output/len_diorama_pad_v1/3T/preview/assembly.png'),BASE/cat/'assembly.png')
            text+='\n별도 세트입니다. 현재 확정2장에 자동 추가하지 않습니다. 받침280×71.2235mm, 파츠6개, 홈8개. 그림·홈·돌기는 원본 크기이며 시험편 없음.\n\n뒤→앞: 별밤·산맥 배경 → 매화 좌·우 → 용·캐릭터 → 분홍 구름.\n\n![조립 참고](assembly.png)\n'
        if cat=='07_len_origin':
            shutil.copy2(source_path(origin_preview),BASE/cat/'assembly.png')
            text+=f'\n별도 세트입니다. 현재 확정2장에 자동 추가하지 않습니다. 받침280×71.2235mm, 파츠{origin_parts-1}개, 홈{origin_slots}개, 투명 테두리{rev["clear_border_mm"]:.1f}mm(모든 판 동일). 그림·홈·돌기는 원본 크기이며 시험편 없음.\n\n뒤→앞: 하늘(창 자리까지 이어 붙임)·달구름을 인쇄한 뒷판 1장 → 격자 문 판 좌·우(행 47) → 한 조각 나무 판(줄기·가지·꽃송이, 행 31, 시안처럼 왼쪽 아래에서 오른쪽 위로, 가지 사이 구멍으로 하늘·달이 보임) → 뱀 → 받침에 앉은 렌(그림 전체, 다리·부츠·칼 포함). 조립 시안은 투명 아크릴을 투명하게 그립니다.\n\n{origin_composition}\n\n![조립 참고](assembly.png)\n'
        write(BASE/cat/'README.md',f'# {title}\n\n'+text+'\n실물 검증 전입니다. [전체 출력 안내](../README.md)\n')
    included={'01_PRINT_300ppi.png','03_CUT_ONLY.pdf','03_CUT_ONLY.svg','04_WHITE_INK_MASK_300ppi.png','preview.png','cut_detail.png','README.md','validation.json'}
    for group,pages in m['groups'].items():
        archive=BASE/(group.replace('/','_')+'_A3.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in [BASE/'README.md',BASE/group.split('/')[0]/'README.md']:
                z.write(p,p.relative_to(OUT).as_posix())
            for page in pages:
                for name in sorted(included):
                    p=OUT/page['folder']/name;z.write(p,p.relative_to(OUT).as_posix())
        assert archive.stat().st_size<100*1024*1024
    write(OUT/'README.md',f'''# 현재 제작 파일

**선택 재료 3T · A3 420×297mm · 실제 크기100%. 시험편 없음.**

1. [혼합 A3 1 · 추가 이미지·새튀·카데나 판2개 · 41조각](a3_release/02_extra_sheet/3T/sheet_01)
2. [혼합 A3 2 · Len·튀잉·카데나 나머지3개 · 15조각](a3_release/05_len/3T/sheet_01)

현재 확정분 **A3 최소2장 / 56조각**. 단팽이·단바 로고 키링 제외. 도트 렌50mm·발 아래 돌기 수정. [전체 안내·두께별 대안·검사](a3_release)

별도 선택안: [새 Len PAD · 7조각 / A3 1장](a3_release/06_len_pad/3T/sheet_01)과 [Len ORIGIN · {origin_parts}조각 / A3 1장](a3_release/07_len_origin/3T/sheet_01). 이 둘까지 출력하면 총4장·{total_with_optional}조각입니다.

[이전 파일·원본 백업(raw)](https://github.com/ark1st/dpbr_goods/tree/raw) · [main 소스](https://github.com/ark1st/dpbr_goods/tree/main)

[칼선 전수 검사](LASER_PATH_AUDIT.json) · [전체 제작 검사](RELEASE_VALIDATION.json) · [저장소·보존 검사](REPOSITORY_AUDIT.json) · [퇴역 기록](RETIRED.json)

실물 재단·끼움·인쇄 정합은 미검증입니다. 5T는 대안이며 현재3T와 함께 출력하지 않습니다.
''')
    print('Packaged registered A3 pages only; current index replaced',flush=True)

if __name__=='__main__':main()
