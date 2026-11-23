"""Regression checks for real-size A3 packing and rigid mechanical dimensions."""
import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'));sys.path.insert(0,str(ROOT/'scripts'))
from shapely.geometry import box,Point
from build_a3_release import pack,shifted_poly,pdf_destination,polygon_of,draw_path,SIZE,MARGIN,GAP,MM
from nest_contours import rotated

class A3PackingTests(unittest.TestCase):
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
        self.assertEqual(len(selected),84+len(new))
        self.assertEqual(len(set(selected)),len(selected))
        self.assertEqual(sorted(selected),cfg['primary_inventory'])
        self.assertFalse(set(selected)&set(cfg['excluded_brand_parts']['3T']))
        self.assertEqual(sorted(x for x in selected if x.startswith('ascent_')),sorted(cfg['cadena_source_part_ids']+cfg['ascent_remaining']['part_ids']))
        separate=[r['id'] for page in rows['11_ascent_remaining/3T'] for r in page]
        self.assertEqual(set(separate),set(cfg['ascent_remaining']['part_ids']+personal.get('11_ascent_remaining/3T',[])))
        self.assertFalse(set(separate)&set(cfg['cadena_source_part_ids']))
        self.assertNotIn('ascent_31',selected)
        if personal:
            from verify_a3_release import verify_fixed_placements
            self.assertEqual(len(new),cfg['personal_fill_policy']['stand_pieces']+cfg['personal_fill_policy']['keyring_pieces'])
            self.assertEqual(set(new),set(cfg['personal_fill_policy']['new_part_ids']))
            self.assertEqual(set(selected)-set(new),set(cfg['personal_fill_policy']['baseline_ids']))
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
        result=assess(ROOT)
        self.assertTrue(result['candidate_sets']['len_pad_3T']['impossible_proven'])
        self.assertFalse(result['ascent_with_PAD']['capacity_bound']['impossible_proven'])
        self.assertFalse(result['ascent_with_PAD']['mathematical_impossibility_proven'])
        self.assertFalse(result['ascent_with_PAD']['feasible_two_page_layout_found'])

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
