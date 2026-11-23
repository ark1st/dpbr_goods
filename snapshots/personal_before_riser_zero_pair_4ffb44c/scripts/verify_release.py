"""Full current-release audit: archive, contour formats, printed pages and ZIPs."""
from pathlib import Path
import sys,json,subprocess,math
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import pymupdf as fitz
from PIL import Image,ImageDraw
from artifact_hash import artifact_sha256

def main():
    from verify_repository import main as repository_audit
    from verify_laser_paths import main as laser_audit
    from verify_a3_release import main as a3_audit
    repository=repository_audit()
    laser=laser_audit()
    a3=a3_audit()
    from verify_individual_assets import main as asset_audit
    assets=asset_audit() if (ROOT/'output/individual_assets/manifest.json').exists() else None
    from verify_recut import main as recut_audit
    recut=recut_audit() if (ROOT/'output/recut_only').exists() else None
    out=ROOT/'output';qa=ROOT/'tmp/release_qa_current';qa.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((out/'a3_release/manifest.json').read_text(encoding='utf-8'))
    renders=[];images=[];tiles=[]
    for group,pages in manifest['groups'].items():
        for page in pages:
            folder=out/page['folder'];slug=group.replace('/','_')+'_'+folder.name
            for file in sorted(folder.iterdir()):
                if file.suffix.lower() in ['.pdf','.ai']:
                    prefix=qa/(slug+'_'+file.stem+file.suffix.replace('.','_'))
                    subprocess.run(['pdftoppm','-r','70','-singlefile','-png',str(file),str(prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                    with fitz.open(file) as doc:
                        assert len(doc)==1 and all(abs(a-b)<.01 for a,b in zip([doc[0].rect.width*25.4/72,doc[0].rect.height*25.4/72],[420,297])),file
                    with Image.open(str(prefix)+'.png') as im:im.verify()
                    renders.append({'file':file.relative_to(out).as_posix(),'sha256':artifact_sha256(file)})
                elif file.suffix=='.png':
                    with Image.open(file) as im:im.verify()
                    images.append({'file':file.relative_to(out).as_posix(),'sha256':artifact_sha256(file)})
            for name in ['preview.png','cut_detail.png']:
                im=Image.open(folder/name).convert('RGB');im.thumbnail((600,450))
                tile=Image.new('RGB',(620,480),'#eeeeee');tile.paste(im,((620-im.width)//2,5));ImageDraw.Draw(tile).text((10,460),slug+'/'+name,fill='black');tiles.append(tile)
    contact=Image.new('RGB',(1240,480*math.ceil(len(tiles)/2)),'white')
    for i,t in enumerate(tiles):contact.paste(t,((i%2)*620,(i//2)*480))
    contact.save(qa/'contact.png')
    report={'revision':manifest['revision'],'errors':[],'repository':repository,'laser_path_audit':{'checked_files':laser['checked_files'],'errors':laser['errors'],'protected_original_findings':laser['protected_original_findings']},
        'a3_release':a3,'individual_assets':assets,'existing_print_recut':recut,'rendered_pdf_and_ai_pages':renders,'png_files_checked':images,'physical_cut_test':False,
        'coverage':{'current_pages_including_thickness_alternatives':a3['checked_pages'],'current_cut_formats':laser['checked_files'],'packages':len(a3['packages']),'rendered_pdf_and_ai_pages':len(renders),
        'existing_print_recovery_cut_files':len(recut['records']) if recut else 0,'recut_print_pages_added':0,
        'archived_previous_cut_files':126,'archive_cut_quality':'retired; not included in current pass count; exact backup bytes checked'},
        'limitations':a3['limitations']}
    (out/'RELEASE_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report['coverage']),flush=True)
    return report

if __name__=='__main__':main()
