"""Package only registered A3 plates; never recreate retired output folders."""
from pathlib import Path
import json,zipfile,shutil,time
from source_cache import source_path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output';BASE=OUT/'a3_release'

def write(p,text):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8',newline='\n')

def write_personal_release(cfg,manifest):
    """Publish the reviewed offcut allocation without creating new archives."""
    assert cfg['package_archives'] is False
    manifest.update(revision=cfg['revision'],selected_thickness='3T',
        physical_pages_per_selected_thickness=cfg['selected_primary_pages'],
        superseded_releases=cfg['superseded_releases'],
        optional_groups=cfg['optional_groups'],test_pieces_included=False,
        support_files=cfg.get('support_files',[]),recut_recoveries=cfg.get('recut_recoveries',[]),
        package_archives=False,retired_package_files=cfg['retired_package_files'])
    write(BASE/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    current=[];locations={};personal={};number=0
    for group in cfg['selected_primary_groups']:
        for page in manifest['groups'][group]:
            number+=1;folder=OUT/page['folder']
            spec=json.loads((folder/'validation.json').read_text(encoding='utf-8'))
            current.append(f'| {number} | [{group} · {folder.name}]({page["folder"].removeprefix("a3_release/")}) | {page["pieces"]} |')
            for p in spec['parts']:
                locations[p['id']]=number
                if p['id'] in cfg['personal_fill_policy']['new_part_ids']:personal[p['id']]=p
    policy=cfg['personal_fill_policy']
    assert len(personal)==policy['stand_pieces']+policy['keyring_pieces']
    on_added=set(cfg['personal_fill_allocation'].get('19_personal_fill/3T',[]))
    offcut_keys=sum(p['design_metadata']['part']=='keyring' and ident not in on_added for ident,p in personal.items())
    added_keys=sum(p['design_metadata']['part']=='keyring' and ident in on_added for ident,p in personal.items())
    pad_ids=[ident for ids in cfg.get('pad_fill_allocation',{}).values() for ident in ids]
    pad_pages=', '.join(map(str,sorted({locations[ident] for ident in pad_ids})))
    logo_count=sum(len(ids) for ids in cfg.get('logo_fill_allocation',{}).values())
    common=f'''**3T · A3 420×297mm · 실제 크기 100% · {number}장 / {cfg['selected_primary_parts']}조각.**

어센트 30조각은 3T에서 제외해 [5T 800×500mm 별도 판](../large_format/ascent_5T_800x500)에 모았습니다. 나머지 도안의 위치와 크기는 유지합니다. 개인별 스탠드 {policy['stand_pieces']}조각, 연결 키링 {offcut_keys+added_keys}개, Len PAD {len(pad_ids)}조각, 양검을 아래 A3에 포함합니다. Len PAD는 A3 {pad_pages}번에 있습니다. 더 적은 장수가 불가능하다고 증명한 것은 아닙니다.

단바 로고 키링은 이번 제작판에서 제외했습니다. 각 판의 수량은 아래 표를 따릅니다.

| 출력 순서 | 제작 폴더 | 조각 |
|---|---|---:|
'''+ '\n'.join(current)+f'''

## 제작 파일

- `01_PRINT.pdf` 또는 `01_PRINT_300ppi.png`: 인쇄. 파란 위치 기준선 포함.
- `03_CUT_ONLY.pdf` 또는 `.svg`: 재단 전용, 빨강 0.001mm. 안쪽 구멍·홈부터 자릅니다.
- `02_MASTER.pdf`, `.ai`, `.vectorcraft`: 편집본. AI는 PDF 호환 레이어이며 네이티브 편집은 VectorCraft를 사용합니다.
- `04_WHITE_INK_MASK`: 제공된 백색판만 유지합니다. 신규 개인별 도안의 백색은 RIP에서 그림 알파 기준으로 설정해야 합니다.
- `preview.png`, `PREVIEW_NOT_FOR_CUT.pdf`: 검토용입니다.

대지·파란 사각 기준선(가장자리에서 4mm)은 그대로입니다. 조각 간격 3mm 이상, 가장자리 8mm 이상이며 인쇄·백색·칼선의 원점과 배율이 같습니다. 파란 기준선은 자르지 않습니다.

## 개인별 스탠드와 줄줄이 키링

스탠드는 강민·강윤진·이상준·정지영 각각 캐릭터 판 1개와 받침 1개, 총 4세트·8조각입니다. 마가다락방과 청민예는 각각 알파·베타 원본 두 개를 한 판에 함께 인쇄합니다. 각 그림의 높이 60mm와 원래 비율은 그대로이며 합본 외곽 폭은 약95mm·103mm입니다.
몸통 중심 아래에 캐릭터당 폭26mm의 투명 보강부를 연결했습니다. 넓은 지지부가 부드러운 곡면으로 폭18mm 돌기에 이어지며, 무기 효과 쪽의 얇은 길에만 의존하지 않습니다. 탭18×2.6mm, 받침72×28mm, 홈18.8×3.0mm는 유지합니다. 자동 검사는 연속 지지 폭과 접합 면적을 확인하며 실제 강도 시험은 아닙니다.
줄줄이 키링 14개 모두 위·아래 ⌀4mm 연결 구멍이 있습니다. 기존 그림 높이 40mm와 상단 연결부를 유지하고 아래 연결부를 추가해 완성 높이는 약71mm입니다. 4×4cm 완성 외곽으로 축소한 파일이 아닙니다.
연결 금속 링·체인은 제작 칼선에 포함하지 않습니다. 링·체인의 실제 조립 간섭과 아크릴 끼움·커프·인쇄 정합은 실물 미검증입니다.

![상하 두 구멍 · 신규 키링 14개](19_personal_fill/connection_preview.png)

![개인별 스탠드](19_personal_fill/stand_preview.png)

| 개인별 부품 ID | 출력 A3 |
|---|---:|
'''+ '\n'.join(f'| {ident} | {locations[ident]} |' for ident in sorted([*personal,*pad_ids]))+'''

Len PAD의 원래 크기와 280×71.2235mm 받침·8개 홈을 유지했습니다. `06_len_pad`의 단독판은 원본 참고용이며 위 출력 순서에 더해 인쇄하지 않습니다.

이번 출력에는 ZIP을 새로 만들지 않았습니다. 남아 있는 이전 ZIP은 이전 버전의 보관 파일이며 현재 제작용이 아닙니다. 현재 시트 폴더의 파일을 사용하세요.

[배치 검사](A3_VALIDATION.json) · [개인 도안 추가 기록](PERSONAL_FILL_ASSESSMENT.json) · [칼선 검사](../LASER_PATH_AUDIT.json) · [개별 편집 에셋](../individual_assets)
'''
    write(BASE/'README.md','# A3 제작 파일 · 개인별 스탠드·상하 연결 키링\n\n'+common)
    for cat in sorted({g.split('/')[0] for g in manifest['groups']}):
        rows=[]
        for group,pages in manifest['groups'].items():
            if not group.startswith(cat+'/'):continue
            state='현재 제작' if group in cfg['selected_primary_groups'] else '별도 대안·중복 참고용 / 현재 추가 출력 금지'
            for page in pages:
                rel=page['folder'].removeprefix('a3_release/'+cat+'/')
                rows.append(f'### {state} · {group.split("/")[-1]} · {page["pieces"]}조각\n\n[제작 파일]({rel})\n\n![배치]({rel}/preview.png)\n')
        write(BASE/cat/'README.md',f'# {cat}\n\n'+'\n'.join(rows)+'\n[전체 제작 순서·개인별 부품 위치](../README.md)\n\nZIP은 새로 만들지 않았습니다. 실물 미검증입니다.\n')
    from chain_keyring_parts import render_group_preview
    from build_a3_release import polygon_of
    fixed=json.loads((ROOT/'configs/individual_contours.json').read_text(encoding='utf-8'))['parts']
    for kind,file in [('줄줄이','connection_preview.png'),('스탠드','stand_preview.png')]:
        pieces=[]
        for ident,p in sorted(personal.items()):
            meta=p['design_metadata']
            if (kind=='줄줄이' and meta['part']!='keyring') or (kind=='스탠드' and meta['part']=='keyring'):continue
            paths=fixed[ident]['paths'];poly=max((polygon_of(s) for s in paths),key=lambda q:q.area)
            pieces.append(dict(id=ident,bounds=p['source_bounds_mm'],poly=poly,design_metadata=meta))
        render_group_preview({'kind':kind,'applicant':None,'pieces':pieces},BASE/'19_personal_fill'/file)
    assessment={'revision':cfg['revision'],**cfg['personal_fill_policy'],'allocation':cfg['personal_fill_allocation'],
        'selected_pages':number,'selected_parts':cfg['selected_primary_parts'],'physical_cut_test':False}
    write(BASE/'PERSONAL_FILL_ASSESSMENT.json',json.dumps(assessment,ensure_ascii=False,indent=2)+'\n')
    rows='\n'.join(row.replace('](','](a3_release/') for row in current)
    write(OUT/'README.md',f'# 현재 제작 파일\n\n**3T · A3 420×297mm · 100% · {number}장 / {cfg["selected_primary_parts"]}조각.**\n\n| 출력 순서 | 제작 폴더 | 조각 |\n|---|---|---:|\n'+rows+f'\n\n[3T 안내](a3_release) · [어센트 5T 800×500mm](large_format/ascent_5T_800x500) · [개별 편집 에셋](individual_assets)\n\n어센트와 단바 로고는 3T에서 전부 제외했습니다. 양검과 Len PAD는 A3에 포함되어 단독 원본판은 추가 출력하지 않습니다.\n\n**백색 인쇄:** 3T 3·4번의 백색 마스크는 비어 있습니다. 인쇄소에서 그림 알파를 기준으로 백색을 생성해야 합니다(파란 기준선 제외). 5T 어센트의 백색 마스크는 RIP에서 백색 잉크로 지정해야 합니다.\n\n신규 ZIP 없음. 이전 ZIP은 퇴역 보관본입니다. 실물 미검증입니다.\n\n[이미 인쇄된 판의 재커팅 전용](recut_only/danbar_500x800) · [전체 검사](RELEASE_VALIDATION.json) · [칼선 검사](LASER_PATH_AUDIT.json)\n')
    print(f'Published {number} A3 pages; no new ZIP archives',flush=True)

def main():
    cfg=json.loads((ROOT/'configs/a3_release.json').read_text(encoding='utf-8'))
    m=json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
    assert set(m['groups'])==set(cfg['current_groups'])
    if cfg.get('personal_fill_allocation'):
        return write_personal_release(cfg,m)
    m.update(revision=cfg['revision'],selected_thickness='3T',optional_groups=cfg['optional_groups'],test_pieces_included=False,support_files=cfg.get('support_files',[]),recut_recoveries=cfg.get('recut_recoveries',[]))
    write(BASE/'manifest.json',json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    common='''**현재 선택: 3T. A3 가로 420×297mm, 실제 크기 100%, 자동 맞춤 해제.**

| 구분 | 시트 | 구성 |
|---|---|---|
| 현재 1 | [혼합 A3 1: 추가 이미지 + 새튀 + 카데나 판 2개](02_extra_sheet/3T/sheet_01) | 43조각 |
| 현재 2 | [혼합 A3 2: Len 일반·DOT + 튀잉 + 카데나 나머지](05_len/3T/sheet_01) | 16조각 |
| 현재 3·4 | [어센트 · 카데나 제외 · 별도 A3 2장](11_ascent_remaining) | 25조각 |
| 보류 | [새 Len PAD · 원본 보존](06_len_pad) | 현재 출력하지 않음 |
| 참고용 | [양검 단독 배치 원본](09_yanggum) | 혼합 2장에 포함되어 추가 출력하지 않음 |

양검 두 제품의 최종 모습 미리보기(인쇄 데이터 기준, 실물 사진 아님):

![양검 최종 미리보기](yanggum_final_preview.png)

현재 확정 목록은 **4장 / 84조각**입니다. 양검을 포함한 혼합2장59조각과 별도 어센트2장25조각입니다. 추가 대지는 만들지 않았습니다. Len PAD는 보류합니다. 어센트2장에도 원본 크기의 유효 배치를 찾지 못했으며, 이쪽의 불가능을 증명한 것은 아닙니다.
단팽이 1개·단풍바람 로고 키링 2개는 제외했습니다. 카데나는 독립 판 없이 두 시트에 나누었습니다.
Python으로 실제 외곽을 회전·이동해 충돌과 간격을 검사했습니다. 혼합59조각과 어센트25조각이 각각 한 장보다 큰 면적이며 두 장씩 배치됩니다. 어센트를 별도 대지로 분리한다는 조건에서 최소4장입니다. 수치는 `A3_VALIDATION.json`의 `minimum_sheet_proof`에 있습니다.
Len PAD를 기존 혼합2장에 추가하면 3mm 간격을 포함한 최소 확장 면적이 허용 면적보다 큽니다. [후보 검토·면적 하한 증명](OPTIONAL_FILL_ASSESSMENT.json)을 참고하세요. PAD는 다른 받침·배경을 쓰는 별도 세트이며, 일반·DOT와 공통 받침을 쓰는 것으로 합치지 않았습니다.
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
실물 재단·끼움·커프·인쇄 정합은 아직 검증하지 않았습니다.

[칼선 검사](../LASER_PATH_AUDIT.json) · [A3 검사](A3_VALIDATION.json) · [정리·원본 보존 검사](../REPOSITORY_AUDIT.json)

이전 제작판·시험편·중복 ZIP은 [raw 보관 브랜치](https://github.com/ark1st/dpbr_goods/tree/raw)에 있습니다. 새 제작에 사용하지 마세요.
'''
    common='[개별 에셋 · 원본 방향 편집본](../individual_assets) · [줄줄이 튀잉 연결 예시](../individual_assets/linked_tuiing_assembly.png)\n\n'+common
    write(BASE/'README.md','# A3 제작 파일 · 현재 3T\n\n'+common)
    from yanggum_parts import render_final_preview
    render_final_preview(ROOT,BASE/'yanggum_final_preview.png',cfg['yanggum_products'])
    titles={'02_extra_sheet':'혼합 A3 1 · 추가 이미지·새튀·카데나 판2개 · 43조각','05_len':'혼합 A3 2 · Len·튀잉·카데나 나머지3개 · 16조각','06_len_pad':'Len PAD · 출력 보류 · 원본 7조각 보존','09_yanggum':'양검 SD 스탠드+키링 · 단독 배치 참고용'}
    titles['11_ascent_remaining']='어센트 · 카데나 제외 · 별도 A3 2장 · 25조각'
    for cat,title in titles.items():
        if cat=='11_ascent_remaining':
            text='[별도 A3 1 · 14조각](3T/sheet_01) · [별도 A3 2 · 11조각](3T/sheet_02)\n\n![A3 1](3T/sheet_01/preview.png)\n\n![A3 2](3T/sheet_02/preview.png)\n\n카데나5조각은 기존 혼합판에 있으며 이 두 장에는 없습니다. 원본의 무인쇄 패널31은 사용자 요청으로 제외했습니다. 인쇄 판21개와 받침4개를 원래 크기로 배치했습니다.\n\n**크기 확인:** 판104×62.807mm(돌기3mm 포함), 받침104×30mm. 홈 약20.2×3.2mm, 돌기2개 각폭20mm·깊이3mm. 실물3T 두께와 끼움은 미검증입니다. 원본의 좌우 홈 앞뒤 차이 약0.195mm도 보존했습니다.\n\n![원본 크기 검증 · 화면 축척 주의](size_check.png)\n\n[25조각 치수·발견 사항](SIZE_VERIFICATION.json) · [개별 에셋](../../individual_assets)\n'
        elif cat=='09_yanggum':
            text='[단독 배치 참고 파일 · 추가 출력하지 않음](3T/sheet_01)\n\n![3T 배치](3T/sheet_01/preview.png)\n'
        elif cat=='06_len_pad':
            text='[보류된 3T 원본 배치](3T/sheet_01) · [보류된 5T 대안](5T/sheet_01)\n\n![3T 배치](3T/sheet_01/preview.png)\n'
        else:
            text='[현재 3T 제작 파일](3T/sheet_01) · [선택 대안 5T](5T/sheet_01)\n\n![3T 배치](3T/sheet_01/preview.png)\n\n![5T 대안 배치](5T/sheet_01/preview.png)\n'
        if cat=='02_extra_sheet':
            text+='\n현재3T는43조각(양검 캐릭터·키링과 카데나 뒤쪽 판2개 포함), 5T대안은39조각(양검·카데나 제외)입니다. 양검 받침은 혼합A3 2에 있습니다. 단팽이·단풍바람 로고 키링은 모두 제외했습니다. 카데나의 나머지3개는 혼합A3 2에 있습니다. 조립 순서는 뒤에서 배경0→효과1→캐릭터2→효과3입니다.\n'
        if cat=='05_len':
            text+='\n![줄줄이 튀잉 · 실제 조각 연결 참고](../../individual_assets/linked_tuiing_assembly.png)\n'
            for product,name in [('len_diorama_v1','assembly.png')]:
                shutil.copy2(source_path(f'output/{product}/3T/preview/assembly.png'),BASE/cat/name)
            from len_dot_part import render_comparison
            render_comparison(ROOT,BASE/cat/'assembly_dot.png',cfg['len_dot_revision'])
            text+='\n공통 배경·받침 한 세트에 일반76mm·DOT50mm 캐릭터를 교체합니다. 발 아래 돌기 폭18mm, 삽입깊이3T2.6mm. 중복 받침·시험편 없음. 3T는16조각이며 카데나 나머지3개와 양검 받침을 함께 배치했습니다. 양검 캐릭터·키링은 혼합A3 1에 있습니다. 5T 대안에는 양검·카데나가 없습니다.\n\n![일반 조립 참고](assembly.png)\n\n![일반·DOT 실제 크기 비율과 새 발 돌기](assembly_dot.png)\n'
        if cat=='06_len_pad':
            shutil.copy2(source_path('output/len_diorama_pad_v1/3T/preview/assembly.png'),BASE/cat/'assembly.png')
            text+='\n**출력 보류입니다. 이 폴더와 ZIP은 원본 배치 참고용이며 현재4장 출력에 추가하지 않습니다.** 받침280×71.2235mm, 파츠6개, 홈8개. 그림·홈·돌기는 원본 크기이며 시험편 없음.\n\n뒤→앞: 별밤·산맥 배경 → 매화 좌·우 → 용·캐릭터 → 분홍 구름.\n\n![조립 참고](assembly.png)\n'
        if cat=='09_yanggum':
            from yanggum_parts import render_assembly
            render_assembly(ROOT,BASE/cat/'assembly.png',cfg['yanggum_products']['stand'])
            shutil.copy2(BASE/'yanggum_final_preview.png',BASE/cat/'final_preview.png')
            text+='\n**단독 배치 참고용입니다. 양검 3조각은 혼합 A3 1·2에 포함되어 있으므로 이 대지를 추가 출력하지 않습니다.** 스탠드: 제공 원본 그림을 그대로 인쇄, 그림 높이 60mm, 컷 62.2×67.5mm. 받침 72×28mm(모서리 R7)는 인쇄 잉크가 없는 투명 아크릴이며, 발 아래 탭 18mm 폭·삽입깊이 2.6mm가 받침 홈 18.8×3.0mm에 끼워집니다. 키링: 그림 높이 40mm, 컷 43.1×58.0mm, 머리 위 캐리어(폭 13mm)에 ⌀4mm 구멍, 구멍까지 그림 6mm·칼선 4.5mm 여유. 줄줄이 키링 8종과는 별개입니다. 5T 대안은 아직 만들지 않았습니다.\n\n![조립 참고](assembly.png)\n\n![최종 모습 미리보기 · 인쇄 데이터 기준, 실물 사진 아님](final_preview.png)\n'
        write(BASE/cat/'README.md',f'# {title}\n\n'+text+'\n실물 검증 전입니다. [전체 출력 안내](../README.md)\n')
    included={'01_PRINT_300ppi.png','03_CUT_ONLY.pdf','03_CUT_ONLY.svg','04_WHITE_INK_MASK_300ppi.png','preview.png','cut_detail.png','README.md','validation.json'}
    for group,pages in m['groups'].items():
        archive=BASE/(group.replace('/','_')+'_A3.zip')
        temporary=ROOT/'tmp'/archive.name
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
            for p in [BASE/'README.md',BASE/group.split('/')[0]/'README.md']:
                z.write(p,p.relative_to(OUT).as_posix())
            for relative in cfg.get('support_files',[]):
                if relative.startswith('a3_release/'+group.split('/')[0]+'/') or relative=='a3_release/OPTIONAL_FILL_ASSESSMENT.json':
                    z.write(OUT/relative,relative)
            for page in pages:
                for name in sorted(included):
                    p=OUT/page['folder']/name;z.write(p,p.relative_to(OUT).as_posix())
        assert temporary.stat().st_size<100*1024*1024
        # Windows preview/AV readers can briefly hold an existing ZIP open.
        # Publish the completed archive atomically, retaining the old one if
        # replacement is still blocked after bounded retries.
        for attempt in range(15):
            try:
                temporary.replace(archive)
                break
            except OSError:
                if attempt==14:raise
                time.sleep(1)
    write(OUT/'README.md','''# 현재 제작 파일

**선택 재료 3T · A3 420×297mm · 실제 크기100%. 시험편 없음.**

[이미 인쇄된 500×800mm 판 · 재커팅 전용](recut_only/danbar_500x800) — A3 추가 인쇄 없음. 원본 위치·배율을 유지한 새 칼선입니다.

[개별 에셋 · 원본 방향 AI/PDF·그림·칼선](individual_assets) · [줄줄이 튀잉 완성 예시](individual_assets/linked_tuiing_assembly.png)
기본 파일은 개별 에셋으로 관리합니다. 아래 A3는 출력할 때 쓰는 배치본입니다.

![줄줄이 튀잉 연결 예시](individual_assets/linked_tuiing_assembly.png)

1. [혼합 A3 1 · 추가 이미지·새튀·카데나 판2개 · 43조각](a3_release/02_extra_sheet/3T/sheet_01)
2. [혼합 A3 2 · Len·튀잉·카데나 나머지3개 · 16조각](a3_release/05_len/3T/sheet_01)
3. [어센트 · 카데나 제외 · 별도 A3 2장 / 25조각](a3_release/11_ascent_remaining)

현재 확정분 **A3 4장 / 84조각**. 양검을 포함한 혼합2장59조각 + 별도 어센트2장25조각입니다. 어센트의 카데나와 무인쇄 패널31은 새 두 장에서 제외했습니다. [전체 안내·두께별 대안·검사](a3_release)

출력 보류: [새 Len PAD · 원본7조각 보존](a3_release/06_len_pad). 어센트2장도 유효 배치를 확보하지 못했습니다. 전역 불가능 증명은 아닙니다. [혼합2장 수용 검토](a3_release/OPTIONAL_FILL_ASSESSMENT.json).

양검 캐릭터·키링은 혼합1, 받침은 혼합2에 포함했습니다. [단독 배치 참고본](a3_release/09_yanggum)은 추가 출력하지 않습니다.

[이전 파일·원본 백업(raw)](https://github.com/ark1st/dpbr_goods/tree/raw) · [main 소스](https://github.com/ark1st/dpbr_goods/tree/main)

[칼선 전수 검사](LASER_PATH_AUDIT.json) · [전체 제작 검사](RELEASE_VALIDATION.json) · [저장소·보존 검사](REPOSITORY_AUDIT.json) · [퇴역 기록](RETIRED.json)

실물 재단·끼움·인쇄 정합은 미검증입니다. 5T는 대안이며 현재3T와 함께 출력하지 않습니다.
''')
    print('Packaged registered A3 pages only; current index replaced',flush=True)

if __name__=='__main__':main()
