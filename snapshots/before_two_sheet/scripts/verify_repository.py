"""Audit archive preservation and reject obsolete/unregistered release artifacts."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
PAGE_FILES={'01_PRINT.pdf','01_PRINT_300ppi.png','02_MASTER.pdf','02_MASTER.ai',
    '02_MASTER.vectorcraft','03_CUT_ONLY.pdf','03_CUT_ONLY.svg','04_WHITE_INK_MASK.pdf',
    '04_WHITE_INK_MASK_300ppi.png','PREVIEW_NOT_FOR_CUT.pdf','preview.png','cut_detail.png',
    'validation.json','README.md'}
ROOT_FILES={'README.md','LASER_PATH_AUDIT.json','RELEASE_VALIDATION.json','REPOSITORY_AUDIT.json','RETIRED.json'}

def output_inventory(out):
    manifest=json.loads((out/'a3_release/manifest.json').read_text(encoding='utf-8'))
    required={'a3_release/README.md','a3_release/manifest.json','a3_release/05_len/assembly.png','a3_release/05_len/assembly_dot.png'}
    if any(g.startswith('06_len_pad/') for g in manifest['groups']):
        required.add('a3_release/06_len_pad/assembly.png')
    for group,pages in manifest['groups'].items():
        required.add('a3_release/'+group.split('/')[0]+'/README.md')
        required.add('a3_release/'+group.replace('/','_')+'_A3.zip')
        for page in pages:
            required.update(page['folder']+'/'+f for f in PAGE_FILES)
    allowed=required|ROOT_FILES|{'a3_release/A3_VALIDATION.json'}
    actual={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
    unexpected=actual-allowed;missing=required-actual
    if unexpected:raise ValueError('Unregistered or retired output artifacts: '+', '.join(sorted(unexpected)))
    if missing:raise ValueError('Missing release artifacts: '+', '.join(sorted(missing)))
    return sorted(actual)

def archive_audit(policy):
    ref=policy['raw_commit']
    manifest=json.loads(subprocess.check_output(['git','show',ref+':BACKUP_MANIFEST.json'],cwd=ROOT))
    assert manifest['heads']==policy['previous_heads']
    tree={}
    for row in subprocess.check_output(['git','ls-tree','-rz',ref],cwd=ROOT).split(b'\0'):
        if row:
            meta,p=row.split(b'\t',1);tree[p.decode('utf-8')]=meta.split()[2].decode()
    blobs={};logical=0
    # A single Git process avoids thousands of process launches and checks all
    # archived source/output bytes, not just the branch names or file counts.
    proc=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    def digest(oid):
        if oid in blobs:return blobs[oid]
        proc.stdin.write((oid+'\n').encode());proc.stdin.flush()
        head=proc.stdout.readline().split();assert head[1]==b'blob'
        left=int(head[2]);h=hashlib.sha256()
        while left:
            data=proc.stdout.read(min(left,1024*1024));assert data;h.update(data);left-=len(data)
        assert proc.stdout.read(1)==b'\n'
        blobs[oid]=(h.hexdigest(),int(head[2]));return blobs[oid]
    try:
        for r in manifest['files']:
            if 'git_blob' in r:
                assert tree[r['path']]==r['git_blob'],r['path']
                assert digest(r['git_blob'])==(r['sha256'],r['bytes']),r['path']
            else:
                logical+=1;h=hashlib.sha256();size=0
                for part in r['split_parts']:
                    data=subprocess.check_output(['git','cat-file','blob',tree[part]],cwd=ROOT);h.update(data);size+=len(data)
                assert (h.hexdigest(),size)==(r['sha256'],r['bytes'])
    finally:
        proc.stdin.close();proc.stdout.close();assert proc.wait()==0
    assert set(tree)=={r['path'] for r in manifest['files'] if 'git_blob' in r}|{'README.md','BACKUP_MANIFEST.json'}
    return {'commit':ref,'file_records':len(manifest['files']),'stored_files':len(tree),
        'unique_blobs_sha256_checked':len(blobs),'split_originals_verified':logical,
        'status':'retired_archive_bytes_verified_not_current_cut_quality_approval'}

def main():
    policy=json.loads((ROOT/'configs/repository_inventory.json').read_text(encoding='utf-8'))
    from artifact_hash import artifact_sha256
    source_assets=[]
    for asset in policy['preserved_source_assets']:
        assert artifact_sha256(ROOT/asset['file'])==asset['sha256'],('Source asset changed without review',asset['file'])
        source_assets.append(asset['file'])
    for rel in policy['retired_source_files']:
        assert not (ROOT/rel).exists(),('Retired source returned',rel)
    scripts={p.name for p in (ROOT/'scripts').glob('*.py')}
    assert scripts==set(policy['active_source_scripts']),('Unregistered scripts',scripts^set(policy['active_source_scripts']))
    archive=archive_audit(policy)
    from source_cache import restore_inputs,input_records
    restored=restore_inputs()
    assert len(restored)==len(input_records())
    files=output_inventory(ROOT/'output')
    report={'date':policy['date'],'errors':[],'archive':archive,'current_output_files':files,
        'pinned_inputs_sha256_checked':len(restored),'preserved_source_assets_sha256_checked':source_assets,
        'retired_source_files':policy['retired_source_files'],
        'selected_thickness':'3T','selected_pages':3,'selected_parts':59,'physical_cut_test':False,
        'limitations':['Raw backups are byte-verified archives; obsolete artwork is not approved for cutting.',
        'Temporary generated caches and installed libraries are not repository deliverables.']}
    (ROOT/'output/REPOSITORY_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'archive_records':archive['file_records'],'pinned_inputs':len(restored),'current_output_files':len(files),'errors':0}),flush=True)
    return report

if __name__=='__main__':main()
