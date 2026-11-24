"""Capacity proof for optional complete sets, including required cutting gaps.

Each exterior is expanded by half the gap. Expanded pieces must have disjoint
interiors and fit inside the expanded usable rectangle. Polygonal round-buffer
arcs underestimate the exact expanded area; the rectangular container bound
overestimates its area. A strict excess therefore proves non-fit without relying
on a failed heuristic search. Original contours and artwork are never modified.
"""
import json
from pathlib import Path


def capacity_bound(polygons,canvas,margin,gap,sheets):
    lower=sum(p.buffer(gap/2,quad_segs=16).area for p in polygons)
    upper=sheets*(canvas[0]-2*margin+gap)*(canvas[1]-2*margin+gap)
    return {'parts':len(polygons),'sheets':sheets,'gap_mm':gap,'margin_mm':margin,
            'expanded_piece_area_lower_mm2':lower,'expanded_container_area_upper_mm2':upper,
            'excess_area_mm2':lower-upper,'impossible_proven':lower>upper+.01,
            'scope':'Whole exterior contours with the current inter-piece gap; no scaling, overlapping or nesting parts inside mechanical openings.'}


def assess(root=None):
    from build_a3_release import polygon_of
    root=Path(root) if root else Path(__file__).resolve().parents[1]
    cfg=json.loads((root/'configs/a3_release.json').read_text(encoding='utf-8'))
    policy=cfg['optional_fill_policy']
    fixed=json.loads((root/'configs/individual_contours.json').read_text(encoding='utf-8'))['parts']
    def shapes(ids):
        return [max((polygon_of(p) for p in fixed[ident]['paths']),key=lambda p:p.area) for ident in ids]
    records={}
    for product,ids in policy['candidate_sets'].items():
        records[product]=capacity_bound(shapes(policy['baseline_ids']+ids),cfg['canvas_mm'],cfg['page_margin_mm'],cfg['piece_gap_mm'],2)
    assert records['len_pad_3T']['impossible_proven'],'Expected a valid bound for the historical two mixed sheets'
    ascent_bound=capacity_bound(shapes(cfg['ascent_remaining']['part_ids']+policy['candidate_sets']['len_pad_3T']),cfg['canvas_mm'],cfg['page_margin_mm'],cfg['piece_gap_mm'],2)
    historical_pad_allocation=cfg.get('pad_fill_allocation',{})
    fixed_page=cfg.get('fixed_source_page3')
    archived=set(fixed_page.get('archived_reference_ids',[])) if fixed_page else set()
    pad_allocation={group:[ident for ident in ids if ident not in archived]
                    for group,ids in historical_pad_allocation.items()}
    pad_allocation={group:ids for group,ids in pad_allocation.items() if ids}
    ascent_search={'capacity_bound':ascent_bound,**policy['ascent_PAD_search']}
    if pad_allocation:
        ascent_search['decision']='This earlier search concerned only the historical two Ascent sheets; current PAD placements follow current_pad_allocation.'
    result={'maximum_existing_mixed_sheets':2,'baseline_parts':len(policy['baseline_ids']),
            'candidate_sets':records,'allocation':cfg['optional_fill_allocation'],
            'ascent_with_PAD':ascent_search,
            'capacity_proof_scope':'Historical two-sheet comparisons only; these bounds do not assess the fixed user-provided third page. Current production PAD placements are reported separately.' if fixed_page else 'Historical two-sheet comparisons. Current production PAD placements are reported separately.',
            'current_pad_allocation':pad_allocation,
            'deferred':[] if pad_allocation else ['len_pad_3T'],'production_pages_added':0,'physical_cut_test':False}
    if fixed_page:
        result['historical_pad_allocation']=historical_pad_allocation
        result['archived_pad_parts']=[ident for ids in historical_pad_allocation.values() for ident in ids if ident in archived]
        result['current_pad_status']='partial_kit; archived components are not on current selected pages'
        result['production_pages_added_scope']='Historical two-sheet comparison only; not a current page-count claim.'
    return result


if __name__=='__main__':
    print(json.dumps(assess(),ensure_ascii=False,indent=2))
