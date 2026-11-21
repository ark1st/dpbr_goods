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
    common='''**현재 선택: 3T. A3 가로 420×297mm, 실제 크기 100%, 자동 맞춤 해제.**

| 구분 | 시트 | 구성 |
|---|---|---|
| 현재 1 | [추가 이미지 + 새튀](02_extra_sheet/3T/sheet_01) | 42조각 |
| 현재 2 | [어센트 카데나](04_ascent_cadena/sheet_01) | 판 4 + 받침 1 = 5조각 |
| 현재 3 | [Len 일반·DOT + 튀잉](05_len/3T/sheet_01) | 공통 세트·교체 캐릭터 8 + 키링 4 = 12조각 |
| 별도 선택안 | [새 Len PAD](06_len_pad/3T/sheet_01) | 받침 1 + 파츠 6 = 7조각, 별도 A3 1장 |

기존 확정 목록은 **3장 / 59조각**입니다. 새로 병합된 PAD까지 출력하면 **4장 / 66조각**입니다.
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
모든 그림·홈·구멍·돌기 크기를 유지하고 회전·이동으로 배치했습니다. 외부 30조각의 보호 칼선도 그대로입니다.
ZIP에는 인쇄 PNG·백색 PNG·재단 PDF/SVG·시안·치수 기록이 있습니다. 편집본과 인쇄 PDF는 시트 폴더에서 받습니다.

## 두께와 조립

현재 선택은 **3T**입니다. 추가 이미지·Len·PAD의 5T 파일은 별도 대안이며 둘 다 출력하는 구성이 아닙니다.
카데나는 제공 원본의 약3.2mm 홈·3mm 돌기, 좌우 홈 약0.195mm 높이 차이를 유지했습니다. 5T용이 아닙니다.
Len 받침은275×60mm, 두 캐릭터의 그림 높이는 각각 원본76mm입니다. 공통 세트에 일반·DOT 캐릭터를 교체합니다.
PAD 받침은280×71.2235mm이며 자체 8개 홈을 사용합니다. 기존 Len과 치수가 다릅니다.
실물 재단·끼움·커프·인쇄 정합은 아직 검증하지 않았습니다.

[칼선 검사](../LASER_PATH_AUDIT.json) · [A3 검사](A3_VALIDATION.json) · [정리·원본 보존 검사](../REPOSITORY_AUDIT.json)

이전 제작판·시험편·중복 ZIP은 [raw 보관 브랜치](https://github.com/ark1st/dpbr_goods/tree/raw)에 있습니다. 새 제작에 사용하지 마세요.
'''
    write(BASE/'README.md','# A3 제작 파일 · 현재 3T\n\n'+common)
    titles={'02_extra_sheet':'추가 이미지 + 제공 새튀 · 42조각','04_ascent_cadena':'어센트 카데나 · 5조각','05_len':'Len 일반·DOT + 튀잉 · 12조각','06_len_pad':'Len PAD · 별도 선택안 7조각'}
    for cat,title in titles.items():
        if cat=='04_ascent_cadena':
            text='[현재 3T 제작 파일](sheet_01)\n\n![배치](sheet_01/preview.png)\n\n뒤에서 앞으로 배경0 → 배경효과1 → 캐릭터2 → 전면효과3 순서입니다. 판104×약62.807mm, 받침104×30mm. 원본 홈을 보존했으며 5T용이 아닙니다.\n'
        else:
            text='[현재 3T 제작 파일](3T/sheet_01) · [선택 대안 5T](5T/sheet_01)\n\n![3T 배치](3T/sheet_01/preview.png)\n\n![5T 대안 배치](5T/sheet_01/preview.png)\n'
        if cat=='05_len':
            for product,name in [('len_diorama_v1','assembly.png'),('len_diorama_dot_v1','assembly_dot.png')]:
                shutil.copy2(source_path(f'output/{product}/3T/preview/assembly.png'),BASE/cat/name)
            text+='\n공통 배경·받침 한 세트에 일반·DOT 캐릭터 두 종류를 교체합니다. 중복 받침이나 시험편은 없습니다.\n\n![일반 조립 참고](assembly.png)\n\n![DOT 조립 참고](assembly_dot.png)\n'
        if cat=='06_len_pad':
            shutil.copy2(source_path('output/len_diorama_pad_v1/3T/preview/assembly.png'),BASE/cat/'assembly.png')
            text+='\n새로 병합된 별도 세트입니다. 기존 확정3장에 자동 추가하지 않습니다. 받침280×71.2235mm, 파츠6개, 홈8개. 그림·홈·돌기를 원본 크기로 보존하고 A3에 재배치했습니다. 시험편은 제외했습니다.\n\n뒤→앞: 별밤·산맥 배경 → 매화 좌·우 → 용·캐릭터 → 분홍 구름.\n\n![조립 참고](assembly.png)\n'
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
    write(OUT/'README.md','''# 현재 제작 파일

**선택 재료 3T · A3 420×297mm · 실제 크기100%. 시험편 없음.**

1. [추가 이미지 + 새튀 · 42조각](a3_release/02_extra_sheet/3T/sheet_01)
2. [어센트 카데나 · 5조각](a3_release/04_ascent_cadena/sheet_01)
3. [Len 일반·DOT + 튀잉 · 12조각](a3_release/05_len/3T/sheet_01)

기존 확정분 **A3 3장 / 59조각**. [전체 안내·두께별 대안·검사](a3_release)

별도 선택안: [새 Len PAD · 7조각 / A3 1장](a3_release/06_len_pad/3T/sheet_01). 이것도 출력하면 총4장·66조각입니다.

[이전 파일·원본 백업(raw)](https://github.com/ark1st/dpbr_goods/tree/raw) · [main 소스](https://github.com/ark1st/dpbr_goods/tree/main)

[칼선 전수 검사](LASER_PATH_AUDIT.json) · [전체 제작 검사](RELEASE_VALIDATION.json) · [저장소·보존 검사](REPOSITORY_AUDIT.json) · [퇴역 기록](RETIRED.json)

실물 재단·끼움·인쇄 정합은 미검증입니다. 5T는 대안이며 현재3T와 함께 출력하지 않습니다.
''')
    print('Packaged registered A3 pages only; current index replaced',flush=True)

if __name__=='__main__':main()
