"""Write the print handoff index, retire replaced layouts and package A3 files."""
from pathlib import Path
import sys,json,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
OUT=ROOT/'output';BASE=OUT/'a3_release'

def main():
    manifest=json.loads((BASE/'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['groups'])==6
    # Compact earlier VectorCraft AI exports without changing their PDF content.
    for file in BASE.rglob('02_MASTER.ai'):
        with fitz.open(file) as d:
            d.xref_set_key(d[0].xref,'PieceInfo','null')
            d.xref_set_key(d.pdf_catalog(),'Names/EmbeddedFiles','null')
            temp=ROOT/'tmp/a3_release/compact.ai';d.save(temp,garbage=4,deflate=True)
        shutil.copy2(temp,file)
    intro='''# A3 최종 출력 · 2026-11-21

**대지 420×297mm, 실제 크기 100%. 그림과 끼움부를 축소하지 않았습니다.**
추가 이미지와 Len은 실제 재료에 맞는 3T 또는 5T **한 가지씩** 선택합니다.
선택한 두께 기준 전체 A3 **5장**: 추가 이미지 1 + 키링 1 + 어센트 2 + Len 1.

| 번호 | 출력 대상 | A3 수량 | 구성 |
|---|---|---:|---|
| 2 | [추가 이미지 시트](02_extra_sheet) | 1 | 기존 38조각, 외부 30개 원본 칼선 보존 |
| 3 | [줄줄이 키링](03_linked_keyrings) | 1 | 제공 새튀 4 + 기존 튀잉 4, 각 1개 |
| 4 | [어센트](04_ascent_original) | 2 | 판 26 + 받침 5, 총 31조각 |
| 5 | [Len](05_len) | 1 | 본품 7 + 끼움 시험편 2 |

## 출력 순서

1. 해당 폴더의 `01_PRINT.pdf` 또는 `01_PRINT_300ppi.png`를 100%로 인쇄합니다. 자동 맞춤·확대·축소를 끕니다.
2. `03_CUT_ONLY.pdf` 또는 `.svg`만 재단합니다. 빨강 #FF0000, 선 두께 0.001mm, 안쪽 구멍·홈부터 가공합니다.
3. 파란 사각형은 대지 가장자리에서 4mm 들어간 위치 기준입니다. 재단선이 아닙니다. 그림·백색·재단은 같은 원점으로 정합합니다.
4. 외곽은 종이 가장자리에서 8mm 이상, 조각 사이는 3mm 이상입니다. 장비의 인쇄 가능 영역·등록 방식을 현장에서 확인합니다.

`02_MASTER.pdf`는 원본 그림 데이터를 보존한 레이어 문서입니다.
`02_MASTER.ai`는 Illustrator에서 열 수 있는 **PDF 호환 레이어 파일**이며,
전용 편집 상태는 별도 `.vectorcraft`에 있습니다. 일부 편집 파일의 그림은 600ppi로 렌더한 독립 이미지이며 칼선은 벡터입니다.
인쇄용 PDF에는 이 편집용 렌더를 대입하지 않았습니다.
`preview.png`, `cut_detail.png`, `PREVIEW_NOT_FOR_CUT.pdf`는 시안이므로 제작에 사용하지 않습니다.

ZIP은 인쇄 PNG·백색 PNG·재단 PDF/SVG·시안·치수 기록을 담습니다.
큰 편집 파일과 원본 데이터가 유지된 인쇄 PDF는 각 시트 폴더에서 별도로 받습니다.

## 확인 사항

- 새튀는 제공된 원본 그림 높이 30mm·구멍 지름 2.5mm, 튀잉은 기존 그림 높이 약 38.36mm·구멍 지름 4mm를 유지했습니다.
- 어센트는 원본 3.2mm 홈과 3mm 돌기 길이를 유지한 파일입니다. 5T용으로 변경한 파일이 아닙니다.
  좌우 홈 중심의 원본 약 0.195mm 세로 차이도 유지했습니다. 먼저 한 쌍을 끼움 시험하세요.
  원본에는 판 26개에 비해 받침은 5개뿐이며, 비어 있는 효과판도 한 조각 포함됩니다. 수량을 임의로 늘리거나 삭제하지 않았습니다.
- 백색 분판은 제공된 부분만 보존했습니다. 새튀는 원본 알파에서 백색 마스크를 만들었습니다.
  Len 등 별도 백색이 없는 그림은 RIP에서 백색 설정이 필요합니다. 빈 백색 파일이 전체 그림용 마스크라는 뜻은 아닙니다.
- 소프트웨어 검사와 실물 시험은 다릅니다. 실제 재료·장비에서 끼움·절단면·인쇄 정합 시험은 아직 하지 않았습니다.

검사: [A3 제작 검사](A3_VALIDATION.json), [전체 칼선 전수 검사](../LASER_PATH_AUDIT.json).
'''
    (BASE/'README.md').write_text(intro,encoding='utf-8')
    for category,title in [('02_extra_sheet','2. 추가 이미지 시트 · 38조각'),('05_len','5. Len · 본품 7조각 + 시험편 2개')]:
        body=f'# {title}\n\nA3 420×297mm / 원본 실제 크기 유지.\n\n- [3T 제작 파일](3T/sheet_01)\n- [5T 제작 파일](5T/sheet_01)\n\n실제 재료에 맞는 한 가지를 선택합니다. 두 버전을 모두 출력하는 것이 아닙니다.\n\n![3T 배치](3T/sheet_01/preview.png)\n\n[전체 출력 안내](../README.md)\n'
        if category=='05_len':
            shutil.copy2(OUT/'len_diorama_v1/3T/preview/assembly.png',BASE/category/'assembly.png')
            body+='\n![조립 예상](assembly.png)\n\n받침 275×60mm, 원본 6개 세움판의 크기·홈 위치를 유지했습니다. 시험편의 각 홈 옆 번호·인쇄 치수를 기준으로 확인합니다. 3T는 2.6~3.4mm, 5T는 4.6~5.4mm입니다.\n'
        (BASE/category/'README.md').write_text(body,encoding='utf-8')
    (BASE/'03_linked_keyrings/README.md').write_text('# 3. 줄줄이 키링 · 새튀 4 + 튀잉 4\n\n[A3 제작 파일](sheet_01) · 각 디자인 1개, 총 8개.\n\n![배치](sheet_01/preview.png)\n\n제공 새튀의 2.5mm 구멍과 기존 튀잉의 4mm 구멍을 보존했습니다. 금속 연결고리는 별도입니다.\n\n[전체 안내](../README.md)\n',encoding='utf-8')
    (BASE/'04_ascent_original/README.md').write_text('# 4. 어센트 · A3 2장 / 총 31조각\n\n원본 크기 100%. 판 26 + 받침 5. **원본 약 3.2mm 홈을 유지했으며 5T용이 아닙니다.**\n\n- [1번 시트 · 16조각](sheet_01)\n- [2번 시트 · 15조각](sheet_02)\n\n![1번](sheet_01/preview.png)\n\n![2번](sheet_02/preview.png)\n\n좌우 홈의 약 0.195mm 세로 차이는 원본에 있습니다. 임의 수정하지 않았으며, 본 제작 전 끼움 시험을 진행해야 합니다. 비어 있는 효과판 한 개도 원본대로 포함했습니다.\n\n[전체 안내](../README.md)\n',encoding='utf-8')
    for group,pages in manifest['groups'].items():
        for page in pages:
            p=OUT/page['folder']/'README.md';text=p.read_text(encoding='utf-8')
            note='\nAI는 PDF 호환 레이어 파일입니다. 전용 편집 상태는 `.vectorcraft`, 원본 그림 데이터를 유지한 인쇄는 `01_PRINT.pdf`를 사용합니다. 일부 편집 파일은 그림만 600ppi이며 칼선은 벡터입니다.\n'
            if note not in text:p.write_text(text+note,encoding='utf-8')
        archive=BASE/(group.replace('/','_')+'_A3.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in [BASE/'README.md',BASE/group.split('/')[0]/'README.md']:
                z.write(p,p.relative_to(OUT).as_posix())
            for page in pages:
                for p in sorted((OUT/page['folder']).iterdir()):
                    if p.name in ['01_PRINT_300ppi.png','03_CUT_ONLY.pdf','03_CUT_ONLY.svg','04_WHITE_INK_MASK_300ppi.png','preview.png','cut_detail.png','README.md','validation.json']:
                        z.write(p,p.relative_to(OUT).as_posix())
        assert archive.stat().st_size<100*1024*1024,(archive,archive.stat().st_size)
    retired={'extra_sheet':'02_extra_sheet','linked_tuiing_v1':'03_linked_keyrings','len_diorama_v1':'05_len'}
    for old,new in retired.items():
        p=OUT/old/'README.md';text=p.read_text(encoding='utf-8')
        marker=f'> **A3 전환으로 구버전 제작 대지는 퇴역했습니다. 현재 출력은 [A3 최종본](../a3_release/{new})을 사용하세요.** 원본과 조립 참고용으로 보관합니다.\n\n'
        if marker not in text:p.write_text(marker+text,encoding='utf-8')
    # Existing current-package checks still validate these retained source layouts.
    for filename in ['Extra_Sheet_38pcs_3T.zip','Extra_Sheet_38pcs_5T.zip','Tuiing_Linked_4_Separate_Plates.zip']:
        archive=OUT/filename;temp=ROOT/'tmp/a3_release/repacked.zip'
        with zipfile.ZipFile(archive) as src,zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as dst:
            for entry in src.infolist():
                current=OUT/entry.filename
                data=current.read_bytes() if current.is_file() and current.name=='README.md' else src.read(entry.filename)
                dst.writestr(entry,data)
        shutil.copy2(temp,archive)
    p=OUT/'README.md';text=p.read_text(encoding='utf-8');line='## 현재 출력: [A3 최종본 · 추가 이미지 / 줄줄이 키링 / 어센트 / Len](a3_release)\n\n'
    if line not in text:p.write_text(line+text,encoding='utf-8')
    print('A3 packages and retirement notices written',flush=True)

if __name__=='__main__':main()
