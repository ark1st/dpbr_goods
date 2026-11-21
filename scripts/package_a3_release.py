"""Publish a three-sheet A3 handoff and retire superseded layouts."""
from pathlib import Path
import sys,json,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
OUT=ROOT/'output';BASE=OUT/'a3_release'
CFG=json.loads((ROOT/'configs/a3_release.json').read_text(encoding='utf-8'))

def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')

def retire(folder,text):
    marker='> **퇴역 · 이번 제작에서 사용하지 마세요.** '+text+'\n\n'
    for p in [folder/'README.md',*folder.glob('sheet_*/README.md')]:
        old=p.read_text(encoding='utf-8') if p.exists() else ''
        if marker not in old:write(p,marker+old)

def main():
    manifest=json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
    assert set(manifest['groups'])==set(CFG['current_groups'])
    write(BASE/'README.md','''# A3 최종 출력 · 압축 배치 / 카데나 / Len 일반+DOT

**전체 A3 3장. 420×297mm, 실제 크기 100%, 자동 맞춤 해제.**
추가 이미지와 Len은 실제 재료에 맞는 3T 또는 5T **한 가지씩** 선택합니다.
줄줄이 키링 8개는 추가 이미지와 Len 대지의 빈 공간에 나누어 넣었습니다. 별도 키링 시트는 출력하지 않습니다.

| 출력 순서 | 파일 | 장수 | 구성 |
|---|---|---:|---|
| 1 | [추가 이미지 + 제공 줄줄이 키링](02_extra_sheet) | 1 | 기존 38 + 제공 새튀 4 = 42조각 |
| 2 | [어센트 카데나만](04_ascent_cadena) | 1 | 배경·효과·캐릭터 4판 + 받침 1 = 5조각 |
| 3 | [Len 일반+DOT + 튀잉 줄줄이 키링](05_len) | 1 | 공통 세트·교체 캐릭터 8 + 시험편 2 + 튀잉 4 = 14조각 |

Len은 **공통 배경·받침 한 세트에 일반 캐릭터와 DOT 캐릭터를 교체**하는 구성입니다.
캐릭터 두 개를 동시에 같은 홈에 꽂는 구조가 아닙니다. 중복 배경·받침은 출력하지 않습니다.
전체 물리 조각은 61개이며 키링은 각 디자인 1개씩 총 8개입니다.

## 제작 파일

- `01_PRINT.pdf` 또는 `01_PRINT_300ppi.png`: 인쇄. PDF는 원본 그림 데이터를 보존합니다.
- `03_CUT_ONLY.pdf` 또는 `.svg`: 재단 전용. 빨강 #FF0000, 0.001mm, 안쪽 구멍·홈 먼저 절단.
- `02_MASTER.ai`: PDF 호환 레이어 파일. 전용 편집 상태는 `.vectorcraft`입니다.
  편집 파일의 그림은 독립 600ppi 이미지, 칼선은 벡터입니다. 원본 그림 데이터는 `01_PRINT.pdf`와 `02_MASTER.pdf`에 유지했습니다.
- `04_WHITE_INK_MASK`: 원본 제공 백색 분판. 별도 백색이 없는 Len 등은 RIP에서 백색을 설정합니다.
- `preview.png`, `cut_detail.png`, `PREVIEW_NOT_FOR_CUT.pdf`: 시안, 제작용 아님.

파란 사각형은 가장자리에서 4mm 들어간 위치 기준이며 **자르지 않습니다**.
대지 원점과 배율을 인쇄·백색·재단에서 동일하게 사용합니다.
조각 사이 3mm 이상, 대지 가장자리 8mm 이상을 유지합니다.
그림, 구멍, 홈, 돌기 크기는 원본과 동일합니다. 회전과 이동만 적용했습니다.
보호 대상 외부 캐릭터 30개는 원래 칼선 그대로입니다.

ZIP에는 인쇄 PNG·백색 PNG·재단 PDF/SVG·시안·치수 기록을 넣었습니다.
원본 데이터 인쇄 PDF와 편집 파일은 각 시트 폴더에서 별도로 받습니다.

## 끼움과 원본 특이사항

- 카데나: 원본 첫 줄의 4개 판 + 원본 첫 번째 받침. 판 104×약62.807mm, 받침 104×30mm.
  원본 약3.2mm 홈·3mm 돌기 깊이와 좌우 홈 약0.195mm 높이 차이를 유지했습니다. **5T용이 아닙니다.**
- 제공 새튀: 원본 그림 높이30mm, 구멍2.5mm. 튀잉: 원래 그림 높이 약38.36mm, 구멍4mm.
- Len: 받침275×60mm, 두 캐릭터 각각 원본 그림 높이76mm. 3T/5T 끼움 시험편은 해당 Len 대지에 있습니다.
- 소프트웨어 검사 통과는 실물 시험을 뜻하지 않습니다. 재료 두께·커프·끼움·인쇄 정합은 현장에서 시험해야 합니다.

구 `03_linked_keyrings` 독립 대지, `04_ascent_original` 2장 합본 및 해당 ZIP은 퇴역했습니다.
구 320×370mm Len 일반·DOT 출력도 소스/조립 참고용입니다. 위 A3 파일을 사용합니다.

[A3 검사 기록](A3_VALIDATION.json) · [칼선 전수 검사](../LASER_PATH_AUDIT.json)
''')
    for category,title in [('02_extra_sheet','추가 이미지38 + 제공 새튀4 = 42조각'),('05_len','Len 일반+DOT8 + 시험편2 + 튀잉4 = 14조각')]:
        text=f'# {title}\n\n**A3 1장 · 420×297mm · 실제 크기 100%.**\n\n- [3T 제작 파일](3T/sheet_01)\n- [5T 제작 파일](5T/sheet_01)\n\n실제 두께에 맞는 한 가지를 선택합니다. 두 버전을 모두 출력하지 않습니다.\n\n![3T 배치](3T/sheet_01/preview.png)\n\n![5T 배치](5T/sheet_01/preview.png)\n'
        if category=='05_len':
            for product,name in [('len_diorama_v1','assembly.png'),('len_diorama_dot_v1','assembly_dot.png')]:
                shutil.copy2(OUT/product/'3T/preview/assembly.png',BASE/category/name)
            text+='\n공통 배경·받침 **한 세트**에 일반·DOT 캐릭터 두 종류를 교체합니다. 받침275×60mm, 각 캐릭터 원본 그림 높이76mm와 돌기·홈을 유지했습니다.\n\n![일반 조립 참고](assembly.png)\n\n![DOT 조립 참고](assembly_dot.png)\n\n위 조립 그림은 원격 원본 참고 이미지입니다. 실제 출력 대상은 위 배치도의14조각입니다.\n\n끼움 시험편: 3T 2.6~3.4mm / 5T 4.6~5.4mm, 번호와 인쇄 치수를 확인합니다. 튀잉4개는 이 대지에 있으므로 별도 키링판은 출력하지 않습니다.\n'
        else:text+='\n보호 대상 외부 캐릭터30개를 포함한 기존38조각을 유지하고, 제공 줄줄이 키링 새튀4개를 빈 공간에 추가했습니다. 기존 튀잉4개는 Len 대지에 있습니다.\n'
        write(BASE/category/'README.md',text+'\n[전체 출력 안내](../README.md)\n')
    write(BASE/'04_ascent_cadena/README.md','''# 어센트 카데나 · A3 1장 / 5조각

[제작 파일](sheet_01)

![카데나 배치](sheet_01/preview.png)

원본 첫 줄의 **배경0 → 배경 효과1 → 캐릭터2 → 전면 효과3** 순서로 받침 뒤에서 앞으로 꽂습니다.
다른 직업은 이번 출력에서 제외했습니다. 원본 파일과 이전 전체 합본은 보관합니다.
판4개 104×약62.807mm, 받침1개104×30mm, 그림·돌기·홈은 원본 크기입니다.
홈 약3.2mm, 돌기 깊이3mm로 **5T용이 아닙니다**.
좌우 홈 약0.195mm 높이 차이도 원본에 있어 보존했습니다. 실물 끼움 시험은 미완료입니다.

[전체 출력 안내](../README.md)
''')
    write(BASE/'03_linked_keyrings/README.md','''# 줄줄이 키링 배치 위치

**독립 A3 대지는 퇴역했습니다. 이 폴더의 구 sheet_01과 ZIP은 출력하지 마세요.**

- [제공 새튀4개 → 추가 이미지 대지](../02_extra_sheet)
- [기존 튀잉4개 → Len 일반+DOT 대지](../05_len)

각 디자인1개씩 총8개. 조각·구멍 크기는 그대로이며, 키링 전용 A3 한 장을 절약했습니다.
''')
    retire(BASE/'03_linked_keyrings','키링8개는 추가 이미지와 Len 대지에 나누어 들어갔습니다.')
    retire(BASE/'04_ascent_original','현재 출력은 카데나5조각만 있는 ../04_ascent_cadena 폴더입니다.')
    for group,pages in manifest['groups'].items():
        archive=BASE/(group.replace('/','_')+'_A3.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in [BASE/'README.md',BASE/group.split('/')[0]/'README.md']:
                z.write(p,p.relative_to(OUT).as_posix())
            for page in pages:
                for p in sorted((OUT/page['folder']).iterdir()):
                    if p.name in ['01_PRINT_300ppi.png','03_CUT_ONLY.pdf','03_CUT_ONLY.svg','04_WHITE_INK_MASK_300ppi.png','preview.png','cut_detail.png','README.md','validation.json']:
                        z.write(p,p.relative_to(OUT).as_posix())
        assert archive.stat().st_size<100*1024*1024
    for old,new in {'extra_sheet':'02_extra_sheet','linked_tuiing_v1':'03_linked_keyrings','len_diorama_v1':'05_len','len_diorama_dot_v1':'05_len'}.items():
        retire(OUT/old,f'현재 제작은 [A3 최종본](../a3_release/{new})을 사용합니다. 이 폴더는 원본·조립 참고용입니다.')
    for filename in ['Extra_Sheet_38pcs_3T.zip','Extra_Sheet_38pcs_5T.zip','Tuiing_Linked_4_Separate_Plates.zip','Danpungbaram_Len_Diorama_DOT_V1_MAIN_7pcs_3T_5T.zip']:
        archive=OUT/filename;temp=ROOT/'tmp/a3_release/repacked.zip'
        with zipfile.ZipFile(archive) as src,zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as dst:
            for entry in src.infolist():
                parts=entry.filename.split('/')
                if parts[0]=='Danpungbaram_Len_Diorama_DOT_V1':parts[0]='len_diorama_dot_v1'
                current=OUT.joinpath(*parts)
                data=current.read_bytes() if current.is_file() and current.name=='README.md' else src.read(entry.filename)
                dst.writestr(entry,data)
        shutil.copy2(temp,archive)
    p=OUT/'README.md';text=p.read_text(encoding='utf-8')
    line='> **현재 출력은 [A3 총3장 최종본](a3_release)입니다.** 추가 이미지+새튀 / 카데나만 / Len 일반+DOT+튀잉. 아래 이전 링크는 보관 이력입니다.\n\n'
    if line not in text:write(p,line+text)
    print('Three-sheet A3 packages and retirement notices written',flush=True)

if __name__=='__main__':main()
