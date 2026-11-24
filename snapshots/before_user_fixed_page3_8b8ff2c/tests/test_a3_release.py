"""Regression checks for real-size A3 packing and rigid mechanical dimensions."""
import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'));sys.path.insert(0,str(ROOT/'scripts'))
from shapely.geometry import box,Point
from build_a3_release import pack,shifted_poly,pdf_destination,polygon_of,draw_path,SIZE,MARGIN,GAP,MM
from nest_contours import rotated

class A3PackingTests(unittest.TestCase):
    def test_master_default_layers_show_cut_and_hide_white(self):
        import tempfile
        import pymupdf as fitz
        from verify_release import verify_editor_cut_visible
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'master.pdf'
            def create(cut_on,white_on):
                doc=fitz.open();page=doc.new_page()
                art=doc.add_ocg('PRINT_ARTWORK',on=True)
                cut=doc.add_ocg('LASER_CUT',on=cut_on)
                white=doc.add_ocg('WHITE_INK_MASK',on=white_on)
                page.draw_line((20,20),(80,20),color=(1,0,0),oc=cut)
                states={art:True,cut:cut_on,white:white_on}
                doc.set_layer(-1,basestate='OFF',on=[i for i,v in states.items() if v],off=[i for i,v in states.items() if not v])
                doc.save(file);doc.close()
            create(True,False)
            with fitz.open(file) as doc:self.assertEqual(verify_editor_cut_visible(doc,file),1)
            file.unlink();create(False,False)
            with fitz.open(file) as doc:
                with self.assertRaisesRegex(AssertionError,'LASER_CUT hidden'):
                    verify_editor_cut_visible(doc,file)
            file.unlink();create(True,True)
            with fitz.open(file) as doc:
                with self.assertRaisesRegex(AssertionError,'WHITE_INK_MASK visible'):
                    verify_editor_cut_visible(doc,file)

    def test_supplied_ascent_3t_interfaces_are_measured_without_rebuilding(self):
        from ascent_size_audit import measure
        cfg=json.loads((ROOT/'configs/a3_release.json').read_text())
        data=json.loads((ROOT/'configs/individual_contours.json').read_text())['parts'];pieces=[]
        for ident in cfg['ascent_remaining']['part_ids']:
            row=data[ident];paths=[{'poly':polygon_of(path)} for path in row['paths']]
            pieces.append({'id':ident,'bounds':row['source_bounds_mm'],'paths':paths,'poly':max((p['poly'] for p in paths),key=lambda p:p.area)})
        report=measure(pieces)
        self.assertEqual(report['included_parts'],25)
        self.assertEqual(report['printed_panels'],21)
        self.assertEqual(report['bases'],4)
        self.assertEqual(len(report['findings']),4)
        self.assertFalse(report['physical_cut_or_fit_test'])

    def test_small_dot_keeps_full_size_tab_under_feet(self):
        from len_dot_part import create_dot_documents
        from shapely.geometry import LineString
        from verify_laser_paths import contours
        cfg=json.loads((ROOT/'configs/a3_release.json').read_text())['len_dot_revision']
        for t in ['3T','5T']:
            cut,art,meta=create_dot_documents(ROOT,t,draw_path,MM,cfg)
            outline=polygon_of(contours(cut[0].get_drawings()[0])[0])
            y=meta['shoulder_y_mm']+.25
            section=outline.intersection(LineString([(0,y),(150,y)]))
            self.assertAlmostEqual(section.length,18,3)
            self.assertAlmostEqual(section.centroid.x,meta['foot_center_mm'],3)
            self.assertAlmostEqual(outline.bounds[3]-meta['shoulder_y_mm'],float(t[0])-.4,3)
            bbox=art[0].get_image_info()[0]['bbox']
            self.assertAlmostEqual((bbox[3]-bbox[1])/MM,50,3)
            self.assertEqual(meta['common_base_slot_mm'],[18.8,float(t[0])])

    def test_separate_ascent_inventory_excludes_blank_and_keeps_cadena_once(self):
        cfg=json.loads((ROOT/'configs/a3_release.json').read_text())
        rows=json.loads((ROOT/'configs/a3_placements.json').read_text())['groups']
        selected=[r['id'] for group in cfg['selected_primary_groups'] for page in (rows[group] if isinstance(rows[group][0],list) else [rows[group]]) for r in page]
        personal=cfg.get('personal_fill_allocation',{})
        new=[p for ids in personal.values() for p in ids]
        pad=cfg.get('pad_fill_allocation',{})
        pad_ids=[p for ids in pad.values() for p in ids]
        logo=cfg.get('logo_fill_allocation',{})
        logo_ids=[p for ids in logo.values() for p in ids]
        stands=cfg.get('additional_stand_allocation',{})
        stand_ids=[p for ids in stands.values() for p in ids]
        self.assertEqual(len(selected),len(cfg['personal_fill_policy']['baseline_ids'])+len(new)+len(pad_ids)+len(logo_ids)+len(stand_ids))
        self.assertEqual(len(set(selected)),len(selected))
        self.assertEqual(sorted(selected),cfg['primary_inventory'])
        self.assertFalse(set(selected)&set(cfg['excluded_brand_parts']['3T']))
        migration=cfg.get('ascent_5t_migration',{}).get('three_t_excluded',False)
        self.assertEqual(sorted(x for x in selected if x.startswith('ascent_')),[] if migration else sorted(cfg['cadena_source_part_ids']+cfg['ascent_remaining']['part_ids']))
        separate_rows=rows['11_ascent_remaining/3T']
        separate_pages=separate_rows if isinstance(separate_rows[0],list) else [separate_rows]
        separate=[r['id'] for page in separate_pages for r in page]
        self.assertEqual(set(separate),set(([] if migration else cfg['ascent_remaining']['part_ids'])
                                          +personal.get('11_ascent_remaining/3T',[])+pad.get('11_ascent_remaining/3T',[])+logo.get('11_ascent_remaining/3T',[])+stands.get('11_ascent_remaining/3T',[])))
        self.assertFalse(set(separate)&set(cfg['cadena_source_part_ids']))
        self.assertNotIn('ascent_31',selected)
        if personal:
            from verify_a3_release import verify_fixed_placements
            self.assertEqual(len(new),cfg['personal_fill_policy']['stand_pieces']+cfg['personal_fill_policy']['keyring_pieces'])
            self.assertEqual(set(new),set(cfg['personal_fill_policy']['new_part_ids']))
            self.assertEqual(set(selected)-set(new)-set(pad_ids)-set(logo_ids)-set(stand_ids),set(cfg['personal_fill_policy']['baseline_ids']))
            for group in cfg['selected_primary_groups']:
                pages=rows[group] if isinstance(rows[group][0],list) else [rows[group]]
                self.assertEqual({r['id'] for page in pages for r in page if r['id'] in new},set(personal.get(group,[])))
            verify_fixed_placements(cfg,rows)
            fixed=cfg['personal_fill_policy']['fixed_existing_placements'][0]
            pages=rows[fixed['group']]
            page=pages[fixed['sheet_index']] if isinstance(pages[0],list) else pages
            next(r for r in page if r['id']==fixed['id'])['x']+=.25
            with self.assertRaisesRegex(AssertionError,'Changed fixed baseline placement'):
                verify_fixed_placements(cfg,rows)

    def test_ascent_migration_excludes_every_source_piece_from_three_t(self):
        from verify_a3_release import verify_ascent_migration
        expected=[f'ascent_{i:02}' for i in range(1,31)]
        config={'ascent_5t_migration':{'three_t_excluded':True,'source_part_ids':expected}}
        verify_ascent_migration(config,['a','b'])
        with self.assertRaisesRegex(AssertionError,'remain on 3T'):
            verify_ascent_migration(config,['a','ascent_01'])
        with self.assertRaisesRegex(AssertionError,'Incomplete 5T source inventory'):
            verify_ascent_migration({'ascent_5t_migration':{'three_t_excluded':True,'source_part_ids':expected[:-1]}},['a'])
        no_logo={'ascent_5t_migration':{'three_t_excluded':True,'source_part_ids':expected,'logo_excluded':True}}
        verify_ascent_migration(no_logo,['a','b'])
        for ident in ['danba_logo_fill_001','danba_logo_smooth']:
            with self.assertRaisesRegex(AssertionError,'Removed logo remains on 3T'):
                verify_ascent_migration(no_logo,['a',ident])

    def test_logo_aliases_preserve_both_contours_and_unique_allocation(self):
        from verify_a3_release import verify_logo_inventory
        paths=['M10 10L30 10L30 40L10 40Z','M15 13L18 13L18 16L15 16Z']
        canonical={'danba_logo_smooth':{'source_bounds_mm':[10,10,30,40],'paths':paths}}
        part={'id':'danba_logo_fill_001','scale':1,'path_count':2,'source_bounds_mm':[10,10,30,40],
              'placed_bounds_mm':[20,30,40,60],'rotation_degrees':0,'rotated_origin_mm':[0,0],
              'expected_paths':[list(shifted_poly(polygon_of(p),{'piece':{'bounds':[10,10,30,40]},'x':20,'y':30,'rotation':0,'rotated_origin':[0,0]}).exterior.coords) for p in paths]}
        cfg={'logo_fill_allocation':{'g':['danba_logo_fill_001']}}
        verify_logo_inventory(cfg,{'g':[part]},canonical)
        with self.assertRaisesRegex(AssertionError,'Changed logo allocation'):
            verify_logo_inventory(cfg,{'g':[part,part]},canonical)
        with self.assertRaisesRegex(AssertionError,'Changed logo contour or hole'):
            verify_logo_inventory(cfg,{'g':[{**part,'expected_paths':[part['expected_paths'][0],part['expected_paths'][0]]}]},canonical)

    def test_smooth_logo_keeps_original_hole_and_excludes_neighbor_art(self):
        import pymupdf as fitz
        from build_a3_release import smooth_logo_source,clip_art
        from laser_paths import cut_path
        page_doc=fitz.open();self.addCleanup(page_doc.close)
        page=page_doc.new_page(width=60*MM,height=60*MM)
        page.draw_rect(fitz.Rect(15*MM,15*MM,18*MM,18*MM),fill=(1,0,0))
        page.draw_rect(fitz.Rect(31*MM,15*MM,33*MM,18*MM),fill=(0,0,1))
        from laser_paths import audit_path
        old=box(0,0,30,30);hole_path=cut_path(Point(5,5).buffer(2,quad_segs=64));_,hole=audit_path(hole_path)
        original={'id':'extra_3T_32','bounds':old.bounds,'poly':old,'art':page_doc,'white':None,
                  'paths':[{'path':hole_path,'poly':hole},{'path':cut_path(old),'poly':old}]}
        outline=box(-4,-4,34,34)
        design={'source_id':'extra_3T_32','new_bounds_mm':outline.bounds,'paths':[hole_path,cut_path(outline)]}
        smooth=smooth_logo_source(original,design)
        expected=clip_art(page_doc,original)
        self.addCleanup(expected.close);self.addCleanup(smooth['art'].close)
        self.assertEqual(expected[0].get_pixmap(dpi=144,alpha=True).samples,
                         smooth['art'][0].get_pixmap(dpi=144,alpha=True).samples)
        self.assertLess(smooth['paths'][0]['poly'].boundary.hausdorff_distance(hole.boundary),.001)
        changed={**design,'paths':[cut_path(Point(5,5).buffer(1.9,quad_segs=64)),design['paths'][1]]}
        with self.assertRaisesRegex(AssertionError,'Changed original logo hole'):
            smooth_logo_source(original,changed)

    def test_enlarged_contour_pins_art_holes_and_tab(self):
        import pymupdf as fitz
        from shapely.ops import unary_union
        from build_a3_release import redesign_outer_contour,clip_art
        from laser_paths import cut_path,audit_path
        source_doc=fitz.open();self.addCleanup(source_doc.close)
        page=source_doc.new_page(width=60*MM,height=60*MM)
        page.draw_rect(fitz.Rect(15*MM,15*MM,18*MM,18*MM),fill=(1,0,0))
        page.draw_rect(fitz.Rect(31*MM,15*MM,32*MM,18*MM),fill=(0,0,1))
        old=unary_union([box(10,10,30,30),box(18,30,22,35)])
        enlarged=unary_union([box(8,8,32,30),box(18,30,22,35)])
        hp=cut_path(Point(15,15).buffer(2,quad_segs=64));_,hole=audit_path(hp)
        op=cut_path(old);_,old_poly=audit_path(op)
        np=cut_path(enlarged);_,new_poly=audit_path(np)
        original={'id':'fixture','bounds':old_poly.bounds,'poly':old_poly,'art':source_doc,'white':None,
                  'paths':[{'path':hp,'poly':hole,'protected':False},{'path':op,'poly':old_poly,'protected':False}],
                  'design_metadata':{'tab_width_mm':4}}
        design={'source_bounds_mm':list(old_poly.bounds),'new_bounds_mm':list(new_poly.bounds),
                'paths':[hp,np],'pin_original_art':True,
                'tab_geometry_proof':{'regions_mm':[[17.9,30.2,22.1,34.9]],'tolerance_mm':.002}}
        result=redesign_outer_contour(original,design)
        expected=clip_art(source_doc,original)
        self.addCleanup(expected.close);self.addCleanup(result['art'].close)
        self.assertEqual(expected[0].get_pixmap(dpi=144,alpha=True).samples,
                         result['art'][0].get_pixmap(dpi=144,alpha=True).samples)
        altered={**design,'paths':[cut_path(Point(15,15).buffer(1.9,quad_segs=64)),np]}
        with self.assertRaisesRegex(AssertionError,'Changed internal hole'):
            redesign_outer_contour(original,altered)
        with self.assertRaisesRegex(AssertionError,'Missing tab preservation region'):
            redesign_outer_contour(original,{**design,'tab_geometry_proof':{'regions_mm':[]}})
        bad=unary_union([box(8,8,32,30),box(18,30,22.5,35)])
        bp=cut_path(bad);_,bad_poly=audit_path(bp)
        with self.assertRaisesRegex(AssertionError,'Changed tab geometry'):
            redesign_outer_contour(original,{**design,'paths':[hp,bp],'new_bounds_mm':list(bad_poly.bounds),
                                             'tab_geometry_proof':{'regions_mm':[[17.8,30.2,22.7,34.9]],'tolerance_mm':.002}})
        with self.assertRaisesRegex(AssertionError,'Protected original'):
            redesign_outer_contour({**original,'paths':[{**original['paths'][0],'protected':True},original['paths'][1]]},design)

    def test_reviewed_small_contour_fit_requires_explicit_bounded_tolerance(self):
        import pymupdf as fitz
        from build_a3_release import redesign_outer_contour
        from laser_paths import cut_path,audit_path
        doc=fitz.open();self.addCleanup(doc.close);doc.new_page(width=50*MM,height=50*MM)
        old=box(10,10,30,30);old_path=cut_path(old);_,old_poly=audit_path(old_path)
        original={'id':'fit_fixture','bounds':old_poly.bounds,'poly':old_poly,'art':doc,'white':None,
                  'paths':[{'path':old_path,'poly':old_poly,'protected':False}]}
        new_path=cut_path(box(10.02,10,30,30));_,new_poly=audit_path(new_path)
        design={'source_bounds_mm':list(old_poly.bounds),'new_bounds_mm':list(new_poly.bounds),
                'paths':[new_path],'pin_original_art':True}
        with self.assertRaisesRegex(AssertionError,'source coverage tolerance'):
            redesign_outer_contour(original,design)
        accepted=redesign_outer_contour(original,{**design,'source_coverage_tolerance_mm':.04})
        self.addCleanup(accepted['art'].close)
        for invalid in [.04001,0,-.01,True]:
            with self.assertRaisesRegex(AssertionError,'Invalid source coverage tolerance'):
                redesign_outer_contour(original,{**design,'source_coverage_tolerance_mm':invalid})
        too_far=cut_path(box(10.05,10,30,30));_,too_far_poly=audit_path(too_far)
        with self.assertRaisesRegex(AssertionError,'exceeds source coverage tolerance'):
            redesign_outer_contour(original,{**design,'paths':[too_far],
                'new_bounds_mm':list(too_far_poly.bounds),'source_coverage_tolerance_mm':.04})

    def test_redesigned_fixed_piece_keeps_original_artwork_affine_transform(self):
        import math
        from verify_a3_release import verify_fixed_placements
        from laser_paths import cut_path
        old=box(10,20,30,40);new=box(8,18,32,42);angle=60
        original={'source_bounds_mm':list(old.bounds),'paths':[cut_path(old)]}
        current={'source_bounds_mm':list(new.bounds),'paths':[cut_path(new)]}
        _,old_origin=rotated({'bounds':old.bounds,'poly':old},angle)
        _,new_origin=rotated({'bounds':new.bounds,'poly':new},angle)
        c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
        dx,dy=new.bounds[0]-old.bounds[0],new.bounds[1]-old.bounds[1]
        expected={'id':'p','group':'g','sheet_index':0,'x':50,'y':60,
                  'rotation_degrees':angle,'source_bounds_mm':list(old.bounds)}
        actual={'id':'p','x':50+new_origin[0]-old_origin[0]+c*dx+s*dy,
                'y':60+new_origin[1]-old_origin[1]-s*dx+c*dy,
                'rotation_degrees':angle,'source_bounds_mm':list(new.bounds)}
        config={'selected_primary_groups':['g'],'personal_fill_allocation':{'g':['other']},
                'personal_fill_policy':{'baseline_ids':['p'],'fixed_existing_placements':[expected]}}
        reviewed={'g':[actual]};redesign={'p':{'original_paths':original['paths']}}
        verify_fixed_placements(config,reviewed,redesign,{'p':current},{'p':original})
        with self.assertRaisesRegex(AssertionError,'Changed fixed baseline placement of artwork'):
            verify_fixed_placements(config,{'g':[{**actual,'x':actual['x']+.25}]},redesign,{'p':current},{'p':original})
        with self.assertRaisesRegex(AssertionError,'Changed independent original contours'):
            verify_fixed_placements(config,reviewed,{'p':{'original_paths':current['paths']}},{'p':current},{'p':original})

    def test_pad_kit_cannot_drop_or_duplicate_an_allocated_part(self):
        from verify_a3_release import verify_pad_inventory
        ids=[f'len_pad_3T_{i:02}' for i in range(1,8)]
        group='19_personal_fill/3T'
        config={'pad_fill_allocation':{group:ids},
                'optional_fill_policy':{'candidate_sets':{'len_pad_3T':ids}}}
        parts=[
            {'id':ident,'scale':1,'path_count':count,'expected_paths':[None]*count}
            for ident,count in zip(ids,[3,2,2,2,2,2,2])
        ]
        verify_pad_inventory(config,{group:parts})
        with self.assertRaisesRegex(AssertionError,'Changed PAD allocation'):
            verify_pad_inventory(config,{group:parts[:-1]})
        with self.assertRaisesRegex(AssertionError,'Changed PAD allocation'):
            verify_pad_inventory(config,{group:[*parts[:-1],parts[0]]})

    def test_pad_variant_preserves_reference_and_cannot_duplicate_source(self):
        from build_a3_release import pad_production_piece
        from verify_a3_release import verify_pad_inventory
        source={'id':'len_pad_3T_01','paths':[{'path':'original'}],
                'bounds':[0,0,10,10],'design_metadata':None}
        alias='len_pad_3T_01_safe';mapping={alias:source['id']}
        variant=pad_production_piece(source,alias,mapping)
        self.assertEqual(source['id'],'len_pad_3T_01')
        self.assertEqual(variant['design_metadata']['redesign_source_id'],source['id'])
        variant['paths'][0]['path']='revised'
        self.assertEqual(source['paths'][0]['path'],'original')
        with self.assertRaisesRegex(AssertionError,'Wrong PAD variant source'):
            pad_production_piece(source,alias,{alias:'len_pad_3T_02'})
        ids=[f'len_pad_3T_{i:02}' for i in range(1,8)]
        selected=[alias,*ids[1:]];group='19_personal_fill/3T'
        cfg={'pad_fill_allocation':{group:selected},'pad_variant_sources':mapping,
             'optional_fill_policy':{'candidate_sets':{'len_pad_3T':ids}}}
        pieces=[{'id':ident,'scale':1,'path_count':count,'expected_paths':[None]*count}
                for ident,count in zip(selected,[3,2,2,2,2,2,2])]
        verify_pad_inventory(cfg,{group:pieces})
        duplicate={**cfg,'pad_fill_allocation':{group:[*selected,ids[0]]}}
        with self.assertRaisesRegex(AssertionError,'full 3T PAD kit exactly once'):
            verify_pad_inventory(duplicate,{group:[*pieces,{'id':ids[0],'scale':1,'path_count':1,'expected_paths':[None]}]})

    def test_pad_variant_canonical_keeps_source_holes(self):
        from verify_a3_release import verify_pad_inventory
        outer='M0 0L20 0L20 20L0 20Z';wide='M-2 -2L22 -2L22 22L-2 22Z'
        hole1='M3 3L5 3L5 5L3 5Z';hole2='M10 10L12 10L12 12L10 12Z'
        ids=[f'len_pad_3T_{i:02}' for i in range(1,8)];alias=ids[0]+'_safe';group='19_personal_fill/3T'
        mapping={alias:ids[0]};selected=[alias,*ids[1:]]
        original={'source_bounds_mm':[0,0,20,20],'paths':[hole1,hole2,outer]}
        variant={'source_bounds_mm':[-2,-2,22,22],'paths':[hole1,hole2,wide]}
        canonical={ids[0]:original,alias:variant}
        canonical.update({ident:{'source_bounds_mm':[0,0,20,20],'paths':[hole1,outer]} for ident in ids[1:]})
        cfg={'pad_fill_allocation':{group:selected},'pad_variant_sources':mapping,
             'optional_fill_policy':{'candidate_sets':{'len_pad_3T':ids}}}
        parts=[]
        for ident in selected:
            source=canonical[ident];bounds=source['source_bounds_mm']
            parts.append({'id':ident,'scale':1,'path_count':len(source['paths']),
                          'source_bounds_mm':bounds,'placed_bounds_mm':bounds,'rotated_origin_mm':[0,0],
                          'rotation_degrees':0,'expected_paths':[list(polygon_of(path).exterior.coords) for path in source['paths']],
                          'design_metadata':{'redesign_source_id':ids[0]} if ident==alias else None})
        verify_pad_inventory(cfg,{group:parts},canonical)
        altered={**canonical,alias:{**variant,'paths':['M3 3L5.2 3L5.2 5L3 5Z',hole2,wide]}}
        with self.assertRaisesRegex(AssertionError,'Changed PAD original hole or slot'):
            verify_pad_inventory(cfg,{group:parts},altered)

    def test_chain_requires_two_4_mm_holes_on_opposite_sides_of_artwork(self):
        from verify_a3_release import verify_chain_holes
        shell=box(10,20,42,80)
        pos={'piece':{'bounds':shell.bounds},'x':23,'y':11,'rotation':165}
        centers=[[26,26],[26,74]]
        part={'id':'fixture_keyring','source_bounds_mm':shell.bounds,'placed_bounds_mm':[23,11],
              'rotation_degrees':165,'path_count':3,
              'expected_paths':[list(shifted_poly(shape,pos).exterior.coords) for shape in
                                [shell,*(Point(*p).buffer(2,quad_segs=64) for p in centers)]],
              'design_metadata':{'hole_centers_mm':centers,'hole_diameter_mm':4,'art_rect_mm':[20,32,31,68]}}
        verify_chain_holes(part)
        with self.assertRaisesRegex(AssertionError,'two hole contours'):
            verify_chain_holes({**part,'expected_paths':part['expected_paths'][:2]})
        paths=[*part['expected_paths'][:2],list(shifted_poly(Point(*centers[-1]).buffer(1.9),pos).exterior.coords)]
        with self.assertRaisesRegex(AssertionError,'resized connector'):
            verify_chain_holes({**part,'expected_paths':paths})

    def test_rotated_stand_cannot_rely_on_a_narrow_weapon_bridge(self):
        from shapely.ops import unary_union
        from verify_a3_release import verify_stand_support
        meta={'part':'character','tab_width_mm':18,'tab_depth_mm':2.6,
              'tab_center_mm':[22.5,72],
              'components':[{'art_height_mm':60,'art_rect_mm':[0,10,45,70]}],
              'support_web':{'anchor_y_mm':30,'width_per_body_mm':26,'body_contact_mm2':[80]}}
        strong=unary_union([box(0,0,45,72),box(13.5,72,31.5,74.6)])
        weak=unary_union([box(0,0,45,40),box(21.5,40,23.5,72),box(13.5,72,31.5,74.6)])
        for shape,good in [(strong,True),(weak,False)]:
            piece={'bounds':shape.bounds,'poly':shape}
            _,origin=rotated(piece,165)
            place={'piece':piece,'x':50,'y':20,'rotation':165,'rotated_origin':origin}
            row={'id':'stand_fixture','source_bounds_mm':shape.bounds,'placed_bounds_mm':[50,20],
                 'rotation_degrees':165,'rotated_origin_mm':origin,
                 'expected_paths':[list(shifted_poly(shape,place).exterior.coords)],'design_metadata':meta}
            if good:verify_stand_support(row)
            else:
                with self.assertRaisesRegex(AssertionError,'Narrow support'):
                    verify_stand_support(row)

    def test_lower_bound_does_not_treat_extra_verified_page_as_minimum(self):
        from verify_a3_release import minimum_sheet_proof
        p={'expected_paths':[list(box(10,10,50,50).exterior.coords)]}
        cfg={'canvas_mm':[100,100],'page_margin_mm':0,'piece_gap_mm':3,'selected_primary_pages':2,
             'separate_print_batches':{'a':['a'],'b':['b']}}
        layout={'groups':{'a':[{}],'b':[{}]}}
        proof=minimum_sheet_proof(cfg,{'a':[p],'b':[p]},layout)
        self.assertEqual(proof['area_lower_bound_sheets'],1)
        self.assertEqual(proof['feasible_sheets'],2)
        self.assertFalse(proof['optimal_sheet_count_proven'])

    def test_no_zip_inventory_accepts_only_declared_retired_archives(self):
        from verify_repository import output_inventory,PAGE_FILES
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            out=Path(d);base=out/'a3_release';page=base/'19_personal_fill/3T/sheet_01'
            page.mkdir(parents=True);(base/'05_len').mkdir()
            old='a3_release/05_len_3T_A3.zip'
            (base/'manifest.json').write_text(json.dumps({
                'groups':{'19_personal_fill/3T':[{'folder':page.relative_to(out).as_posix()}]},
                'package_archives':False,'retired_package_files':[old]}))
            for file in [base/'README.md',base/'05_len/assembly.png',base/'05_len/assembly_dot.png',
                         base/'19_personal_fill/README.md',*(page/name for name in PAGE_FILES)]:
                file.touch()
            self.assertNotIn(old,output_inventory(out))
            (out/old).touch()
            self.assertIn(old,output_inventory(out))
            (base/'19_personal_fill_3T_A3.zip').touch()
            with self.assertRaisesRegex(ValueError,'Unregistered'):
                output_inventory(out)

    def test_clearance_capacity_can_prove_nonfit_when_plain_area_cannot(self):
        from optional_sheet_policy import capacity_bound
        pieces=[box(0,0,39,100) for _ in range(5)]
        self.assertLess(sum(p.area for p in pieces),2*100*100)
        report=capacity_bound(pieces,[100,100],0,3,2)
        self.assertTrue(report['impossible_proven'])
        self.assertGreater(report['expanded_piece_area_lower_mm2'],report['expanded_container_area_upper_mm2'])

    def test_PAD_ascent_failed_search_is_not_reported_as_impossibility(self):
        from optional_sheet_policy import assess
        cfg=json.loads((ROOT/'configs/a3_release.json').read_text())
        result=assess(ROOT)
        self.assertTrue(result['candidate_sets']['len_pad_3T']['impossible_proven'])
        self.assertFalse(result['ascent_with_PAD']['capacity_bound']['impossible_proven'])
        self.assertFalse(result['ascent_with_PAD']['mathematical_impossibility_proven'])
        self.assertFalse(result['ascent_with_PAD']['feasible_two_page_layout_found'])
        self.assertEqual(result['current_pad_allocation'],cfg.get('pad_fill_allocation',{}))
        self.assertEqual(result['deferred'],[] if result['current_pad_allocation'] else ['len_pad_3T'])

    def test_large_source_oblique_cut_avoids_rounded_form_matrix(self):
        import pymupdf as fitz
        from build_a3_release import transformed_cut_path
        from verify_laser_paths import contours
        source=box(402,102,512,172)
        place={'piece':{'bounds':source.bounds},'x':8,'y':8,'rotation':195}
        path='M402 102 L512 102 L512 172 L402 172 Z'
        mapped=transformed_cut_path(path,place)
        doc=fitz.open();page=doc.new_page(width=420*MM,height=297*MM)
        draw_path(page,mapped)
        actual=polygon_of(contours(page.get_drawings()[0])[0])
        expected=shifted_poly(source,place)
        self.assertLess(actual.boundary.hausdorff_distance(expected.boundary),.0001)

    def test_reviewed_layout_rejects_changed_mechanical_dimensions(self):
        from unittest.mock import patch
        import tempfile
        import build_a3_release as builder
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'configs').mkdir()
            rows=[{'id':'part','source_bounds_mm':[10,20,30,40],'x':8,'y':8,'rotation_degrees':15}]
            (root/'configs/a3_placements.json').write_text(json.dumps({'groups':{'demo':rows}}))
            source=box(10,20,30,40)
            with patch.object(builder,'ROOT',root):
                result=builder.reviewed_layout('demo',[{'id':'part','bounds':source.bounds,'poly':source}])
                self.assertEqual(result[0]['placements'][0]['rotation'],15)
                changed=box(10,20,30.2,40)
                with self.assertRaisesRegex(AssertionError,'Source dimensions changed'):
                    builder.reviewed_layout('demo',[{'id':'part','bounds':changed.bounds,'poly':changed}])

    def test_oblique_pdf_export_preserves_outline_hole_and_slot(self):
        import pymupdf as fitz
        from verify_laser_paths import contours
        paths=['M10 20L90 20L90 65L60 65L60 85L10 85Z',
               'M30 35C30 33.89543 30.89543 33 32 33C33.10457 33 34 33.89543 34 35C34 36.10457 33.10457 37 32 37C30.89543 37 30 36.10457 30 35Z',
               'M45 40L63.8 40L63.8 43L45 43Z']
        piece={'bounds':(10,20,90,85),'poly':polygon_of(paths[0])}
        source=fitz.open();page=source.new_page(width=120*MM,height=100*MM)
        for path in paths:draw_path(page,path)
        for angle in [15,105,225,345]:
            poly,origin=rotated(piece,angle)
            placement={'piece':piece,'rotation':angle,'rotated_origin':origin,'x':25,'y':30,'w':poly.bounds[2],'h':poly.bounds[3]}
            output=fitz.open();dest=output.new_page(width=420*MM,height=297*MM)
            dest.show_pdf_page(pdf_destination(placement),source,0,clip=fitz.Rect(9.85*MM,19.85*MM,90.15*MM,85.15*MM),rotate=angle)
            actual=[polygon_of(s) for d in dest.get_drawings() for s in contours(d)]
            self.assertEqual(len(actual),3)
            for a,path in zip(actual,paths):
                expected=shifted_poly(polygon_of(path),placement)
                self.assertLess(a.boundary.hausdorff_distance(expected.boundary),.002)
                self.assertAlmostEqual(expected.area,polygon_of(path).area,7)

    def test_len_dot_and_four_keyrings_5t_still_fit_one_a3(self):
        sizes=json.loads((ROOT/'tests/fixtures/len_dot_linked_5t_sizes.json').read_text())
        self.assertEqual(len(sizes),12)
        self.assertFalse(any('fit' in row['id'] or 'test' in row['id'] for row in sizes))
        pieces=[]
        for row in sizes:
            p=box(0,0,*row['size_mm'])
            pieces.append({'id':row['id'],'bounds':p.bounds,'poly':p})
        pages=pack(pieces)
        self.assertEqual(len(pages),1)
        placed=pages[0]['placements']
        self.assertEqual({p['piece']['id'] for p in placed},{p['id'] for p in pieces})
        for i,p in enumerate(placed):
            actual=shifted_poly(p['piece']['poly'],p)
            self.assertAlmostEqual(actual.area,p['piece']['poly'].area,6)
            for q in placed[:i]:self.assertGreaterEqual(actual.distance(shifted_poly(q['piece']['poly'],q)),GAP-.001)

    def test_keyrings_allocated_once_across_selected_pair(self):
        c=json.loads((ROOT/'configs/a3_release.json').read_text())
        allocated=sum(c['linked_allocation'].values(),[])
        expected={f'supplied_saetui_{i:02}' for i in range(1,5)}|{f'{n}_01' for n in ['tuiing','golden','burnt','unfried']}
        self.assertEqual(set(allocated),expected)
        self.assertEqual(len(allocated),8)
        self.assertEqual(c['cadena_source_part_ids'],['ascent_01','ascent_11','ascent_12','ascent_13','ascent_14'])
        self.assertNotIn('03_linked_keyrings',c['current_groups'])
        self.assertNotIn('04_ascent_original',c['current_groups'])

    def test_ascent_inventory_fits_two_without_scaling(self):
        pieces=[]
        for i in range(31):
            w,h=(104,62.807) if i<26 else (104,30)
            p=box(100,200,100+w,200+h)
            pieces.append({'id':str(i),'bounds':p.bounds,'poly':p})
        pages=pack(pieces)
        self.assertEqual(len(pages),2)
        self.assertEqual(sum(len(p['placements']) for p in pages),31)
        for page in pages:
            polys=[shifted_poly(p['piece']['poly'],p) for p in page['placements']]
            for i,p in enumerate(polys):
                self.assertTrue(box(MARGIN-.001,MARGIN-.001,SIZE[0]-MARGIN+.001,SIZE[1]-MARGIN+.001).contains(p))
                for q in polys[:i]:self.assertGreaterEqual(p.distance(q),GAP-.001)
    def test_rotation_preserves_hole_diameter_and_slot(self):
        place={'piece':{'bounds':(10,20,110,80)},'x':8,'y':8,'rotation':90}
        hole=Point(30,40).buffer(2,quad_segs=64)
        result=shifted_poly(hole,place)
        self.assertAlmostEqual(result.area,hole.area,8)
        self.assertAlmostEqual(result.bounds[2]-result.bounds[0],4,8)
        self.assertAlmostEqual(result.centroid.x,28,8)
        self.assertAlmostEqual(result.centroid.y,88,8)
        slot=shifted_poly(box(30,40,50.2,43.2),place)
        self.assertAlmostEqual(slot.bounds[2]-slot.bounds[0],3.2,8)
        self.assertAlmostEqual(slot.bounds[3]-slot.bounds[1],20.2,8)
    def test_oversize_part_is_rejected_not_shrunk(self):
        p=box(0,0,500,300)
        with self.assertRaises(AssertionError):pack([{'id':'oversize','bounds':p.bounds,'poly':p}])

if __name__=='__main__':unittest.main()
