"""Production artwork for Danpungbaram. All dimensions in mm unless noted.
Mascots are hand-traced vector reconstructions of the supplied Notion card.
Logo paths are taken unchanged from the supplied Illustrator file via VectorCraft.
"""
from pathlib import Path
import sys, os, math, json, copy, base64, subprocess, io
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/pylibs'))
import numpy as np
import cv2
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, MultiPoint, Point, box
from shapely import affinity, concave_hull
from shapely.ops import unary_union
from svgpathtools import parse_path
import xml.etree.ElementTree as ET

OUT=ROOT/'output/production'
ASSETS=OUT/'04_assets'
CLI=r'C:\Users\ARK\AppData\Local\Programs\ArtCraft\VectorCraft\vectorcraft-cli.exe'
ENV={**os.environ,'VECTORCRAFT_NO_PREFS':'1'}
SVG='http://www.w3.org/2000/svg'
INK='http://www.inkscape.org/namespaces/inkscape'
INK='http://www.inkscape.org/namespaces/inkscape' # actual namespace set below
INK='http://www.inkscape.org/namespaces/inkscape'

def runvc(args):
    r=subprocess.run([CLI,*map(str,args)],capture_output=True,text=True,encoding='utf-8',env=ENV)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    return r.stdout

def svg_doc(w,h,content,title=''):
    return f'<svg xmlns="{SVG}" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w:.6f}mm" height="{h:.6f}mm" viewBox="0 0 {w:.6f} {h:.6f}"><title>{title}</title>{content}</svg>'

def path(d,fill,stroke=None,sw=4.5):
    s=f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"' if stroke else ''
    return f'<path d="{d}" fill="{fill}"{s}/>'

def ellipse(cx,cy,rx,ry,fill,stroke=None,sw=4.5):
    s=f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}"{s}/>'

def make_assets():
    # Exactly seven original paths form the logo-only group in the distributed AI.
    orig=ET.parse(ROOT/'tmp/sources/logo-original.svg').getroot()
    logo=next(e for e in orig.iter() if e.get('id')=='로고')
    bounds=[parse_path(e.get('d')).bbox() for e in logo]
    x0=min(b[0] for b in bounds);x1=max(b[1] for b in bounds)
    y0=min(b[2] for b in bounds);y1=max(b[3] for b in bounds)
    content=''.join(ET.tostring(e,encoding='unicode').replace('ns0:','').replace(':ns0','') for e in logo)
    assets={}
    def save(name,w,h,inner):
        assets[name]={'w':w,'h':h,'inner':inner}
        (ASSETS/f'{name}.svg').write_text(svg_doc(w,h,inner,name),encoding='utf-8')
        runvc(['convert',ASSETS/f'{name}.svg',ROOT/f'tmp/{name}.pdf'])
        doc=fitz.open(ROOT/f'tmp/{name}.pdf');pix=doc[0].get_pixmap(matrix=fitz.Matrix(4,4),alpha=True)
        pix.save(str(ASSETS/f'{name}_preview.png'))
    s=45/(y1-y0)
    save('logo_symbol',(x1-x0)*s,45,f'<g transform="scale({s}) translate({-x0} {-y0})">{content}</g>')

    # Garam: source coordinates are those of mascot_01.png, preserving its pose.
    k='#171717';white='#ffffff';orange='#f69c77';yellow='#ffdc89';red='#df6168'
    g=[]
    hat='M608 745 C580 735 572 704 586 676 C601 646 649 610 691 590 C721 576 750 578 776 594 C820 621 850 675 859 729 C864 755 853 777 835 789 L797 775 L643 756 Z'
    g.append(path(hat,orange,k))
    g.append(f'<defs><clipPath id="hat_clip"><path d="{hat}"/></clipPath></defs><g clip-path="url(#hat_clip)">')
    g.extend([ellipse(724,581,25,27,yellow),ellipse(614,633,34,34,yellow),ellipse(709,662,31,31,yellow),ellipse(827,637,47,48,yellow),ellipse(813,748,30,31,yellow),ellipse(613,702,17,19,yellow)])
    g.append(path('M828 681 C845 706 850 749 837 774 L853 768 C867 746 856 701 845 678 Z','#e68c69'))
    g.append('</g>'+path(hat,'none',k))
    # Cape and body behind head.
    g.append(path('M744 828 C769 837 789 865 805 901 L786 913 L753 908 L738 866 Z',red,k))
    g.append(path('M652 819 C665 813 707 816 744 819 C771 828 787 846 798 865 C807 862 808 867 801 874 L782 888 L770 875 L766 868 L765 905 L761 927 C746 932 730 931 720 930 L716 910 L702 907 L698 929 C685 934 664 932 653 932 C649 929 655 925 658 922 C648 900 649 877 648 860 C633 862 616 859 604 855 L599 827 C618 818 632 819 652 819 Z',white,k))
    # Wand, star and hand. Detached motion marks intentionally excluded.
    g.append(path('M571 802 L579 798 L629 878 L622 881 Z','#775f4e',k,4))
    g.append(path('M559 771 L571 779 L584 774 L585 787 L595 795 L581 800 L573 811 L566 799 L553 794 L562 785 Z',yellow,k,3.8))
    g.append(path('M599 833 C586 831 581 842 588 854 C594 867 610 865 617 855 C623 848 615 840 608 839 C609 831 604 826 600 827 C596 828 596 832 599 837 Z',white,k,4))
    # Ear behind head.
    g.append(path('M611 746 C596 745 586 764 595 789 C599 803 610 810 630 808 L637 774 Z',white,k))
    head='M612 694 C641 682 685 688 720 699 C766 714 806 736 817 763 C833 767 838 779 835 793 C831 813 812 825 794 821 L782 816 C750 830 710 834 674 827 C637 820 612 805 608 781 C604 754 605 716 612 694 Z'
    g.append(path(head,white,k))
    g.append(path('M614 697 C654 685 723 704 767 729 C787 740 804 751 813 766 C799 742 756 718 718 707 C678 694 644 691 613 701 Z','#e9e8e8'))
    g.append(ellipse(628,784,17,23,'#f7e5e7'))
    g.append(ellipse(739,798,25,25,'#f7e5e7'))
    g.extend([ellipse(645.5,764,4.2,6.5,k),ellipse(712.2,767.8,4.2,6.5,k)])
    g.append(path('M661 777 C668 769 682 771 689 780 C695 792 684 801 673 799 C660 799 655 787 661 777 Z','#b95560',k,4))
    g.append(path('M664 777 C668 773 678 774 682 778 C679 784 669 785 664 779 Z',white,k,2.6))
    g.append(path('M802 796 L810 801','none',k,4.2))
    # Neckerchief sits under chin.
    g.append(path('M679 827 C667 830 656 845 658 859 C669 861 682 850 688 840 L692 833 Z',red,k,4))
    g.append(path('M695 831 C710 827 724 841 728 853 C731 862 718 864 711 859 C701 853 696 844 693 839 Z',red,k,4))
    g.append(path('M680 831 C683 841 694 843 699 831 Z',red,k,4))
    g.append(path('M676 838 L668 848 M706 839 L715 850','none',k,3.2))
    # 311.3 source units high, normalized to 55 mm of visible artwork.
    s=55/357
    save('garam',315*s,55,f'<g transform="scale({s}) translate(-548 -577)">{"".join(g)}</g>')

    q=[]
    # Danpaengi: the original snail from the same card.
    q.append(path('M931 833 C936 805 960 791 981 796 C1012 800 1031 824 1036 849 C1040 873 1026 891 1004 895 C993 898 975 891 961 880 L943 858 Z',orange,k,4.5))
    q.append(path('M1001 804 C1023 824 1037 852 1026 874 C1020 885 1008 891 997 892 L1009 893 C1034 887 1042 868 1034 846 C1027 823 1016 811 1001 804 Z','#e98e6c'))
    q.append(path('M894 830 L893 824 M920 825 L922 819','none',k,4))
    q.append(path('M888 919 C883 901 884 870 888 849 C891 834 901 826 912 827 C926 828 938 841 947 857 L961 881 C973 891 988 896 1000 894 C1014 891 1018 905 1009 914 C1003 925 980 925 957 925 L907 924 C897 924 890 923 888 919 Z',white,k,4.5))
    q.append(path('M942 853 C948 865 953 880 961 885 L970 889 L963 880 L948 856 Z','#e5e5e5'))
    q.append(path('M960 875 C956 862 964 846 976 845 C990 843 1002 857 996 867 C994 871 989 873 985 873','none',k,4.5))
    q.extend([ellipse(899,848,3.2,3.7,k),ellipse(920,846,3.2,3.7,k),ellipse(894,855,4.5,4,'#ffd3c2'),ellipse(928,853,4.5,4,'#ffd3c2')])
    q.append(path('M904 852 C908 850 913 851 916 852 C916 860 906 864 904 856 Z','#ae4a50',k,3))
    s=32/133
    save('danpaengi',157*s,32,f'<g transform="scale({s}) translate(-882 -794)">{"".join(q)}</g>')
    (ROOT/'tmp/artwork.json').write_text(json.dumps(assets),encoding='utf-8')
    return assets

def poly_path(p):
    c=list(p.exterior.coords)
    return 'M'+' L'.join(f'{x:.4f} {y:.4f}' for x,y in c[:-1])+' Z'

def shape_assets(assets):
    shapes={}
    for name,a in assets.items():
        im=Image.open(ASSETS/f'{name}_preview.png').convert('RGBA')
        mask=(np.array(im)[:,:,3]>64).astype('uint8')*255
        cs,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        polys=[Polygon(c[:,0,:]*[a['w']/im.width,a['h']/im.height]).buffer(0) for c in cs if cv2.contourArea(c)>10]
        art=unary_union(polys)
        if name=='logo_symbol':
            # One carrier connects the separated dot and strokes. No internal cutouts.
            body=concave_hull(art,ratio=.45).buffer(1.8,quad_segs=12)
        else:body=art.buffer(1.8,quad_segs=12)
        if body.geom_type!='Polygon':body=concave_hull(body,ratio=.45)
        body=Polygon(body.exterior).simplify(.07,preserve_topology=True)
        coords=np.array(body.exterior.coords)
        top=coords[coords[:,1]<coords[:,1].min()+.25]
        hx=float(np.mean(top[:,0]));hy=float(art.bounds[1]-2.1)
        tab=Point(hx,hy).buffer(4.6,quad_segs=24)
        outer=unary_union([body,tab]).buffer(.25).buffer(-.25).simplify(.06,preserve_topology=True)
        assert outer.geom_type=='Polygon' and outer.is_valid
        outer=Polygon(outer.exterior)
        hole=Point(hx,hy).buffer(1.5,quad_segs=32)
        assert outer.contains(hole.buffer(2.8))
        assert art.distance(hole)>.35
        shapes[name]={'poly':outer,'hole':(hx,hy),'art':art}
    return shapes

def nest(assets,shapes,W,H,order):
    # Conservative 1 mm raster search. Vector distances are checked afterwards.
    margin=8;gap=3
    occ=np.zeros((int(H),int(W)),np.float32)
    occ[:margin,:]=1;occ[-margin:,:]=1;occ[:,:margin]=1;occ[:,-margin:]=1
    variants={}
    for name,s in shapes.items():
        variants[name]=[]
        for angle in (0,180,90,270):
            p=affinity.rotate(s['poly'],angle,origin=(0,0))
            expanded=p.buffer(gap/2+.15)
            bx,by,rx,ry=expanded.bounds
            mw=math.ceil(rx-bx)+1;mh=math.ceil(ry-by)+1
            mask=np.zeros((mh,mw),np.uint8)
            pts=np.round((np.array(expanded.exterior.coords)-[bx,by])).astype(np.int32)
            cv2.fillPoly(mask,[pts],1)
            variants[name].append((angle,p,mask.astype(np.float32),bx,by))
    placed=[];counts={k:0 for k in assets};failed=set()
    while len(failed)<len(order):
        for name in order:
            if name in failed:continue
            best=None
            for angle,p,mask,bx,by in variants[name]:
                scores=cv2.matchTemplate(occ,mask,cv2.TM_CCORR)
                ys,xs=np.where(scores<.25)
                if not len(ys):continue
                # Lowest top position, then horizontal left edge. Test rotations.
                val=(ys+mask.shape[0])*.95+xs*.12
                idx=int(np.argmin(val));x=int(xs[idx]);y=int(ys[idx]);rank=float(val[idx])
                if best is None or rank<best[0]:best=(rank,angle,p,mask,bx,by,x,y)
            if best is None:failed.add(name);continue
            _,angle,p,mask,bx,by,x,y=best
            h,w=mask.shape;occ[y:y+h,x:x+w]=np.maximum(occ[y:y+h,x:x+w],mask)
            tx=x-bx;ty=y-by
            poly=affinity.translate(p,tx,ty)
            placed.append({'name':name,'angle':angle,'tx':tx,'ty':ty,'poly':poly})
            counts[name]+=1
    # Check every real vector outline; duplicate/shared cuts are forbidden.
    min_gap=999
    for i,p in enumerate(placed):
        assert box(0,0,W,H).contains(p['poly'])
        for q in placed[:i]:min_gap=min(min_gap,p['poly'].distance(q['poly']))
    assert min_gap>=3, min_gap
    area=sum(p['poly'].area-math.pi*1.5**2 for p in placed)
    return placed,{'counts':counts,'total':len(placed),'min_gap_mm':min_gap,'material_utilization':area/(W*H),'margin_mm':margin,'hole_diameter_mm':3,'art_clearance_mm':1.8}

def transform(p):
    a=math.radians(p['angle']);c=round(math.cos(a));s=round(math.sin(a))
    return f'matrix({c} {s} {-s} {c} {p["tx"]:.5f} {p["ty"]:.5f})'

def layer(name,content):
    return f'<g inkscape:groupmode="layer" inkscape:label="{name}" id="{name}" data-name="{name}">{content}</g>'

def write_cut_pdf(placed,shapes,W,H,destination):
    # Explicit PDF closepath operators, with every hole preceding outer contours.
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    c=canvas.Canvas(str(destination),pagesize=(W*mm,H*mm))
    c.setTitle(f'Danpungbaram laser cut only {W}x{H} mm')
    c.transform(mm,0,0,-mm,0,H*mm);c.setStrokeColorRGB(1,0,0);c.setLineWidth(.001)
    for obj in placed:
        hx,hy=shapes[obj['name']]['hole']
        pt=affinity.translate(affinity.rotate(Point(hx,hy),obj['angle'],origin=(0,0)),obj['tx'],obj['ty'])
        p=c.beginPath();p.ellipse(pt.x-1.5,pt.y-1.5,3,3);p.close();c.drawPath(p,stroke=1,fill=0)
    for obj in placed:
        coords=list(obj['poly'].exterior.coords);p=c.beginPath();p.moveTo(*coords[0])
        for xy in coords[1:-1]:p.lineTo(*xy)
        p.close();c.drawPath(p,stroke=1,fill=0)
    c.save()

def board_files(assets,shapes,W,H,folder):
    tries=[]
    for order in [('garam','logo_symbol','danpaengi'),('logo_symbol','garam','danpaengi')]:
        placed,stats=nest(assets,shapes,W,H,order)
        tries.append((placed,stats))
    placed,stats=max(tries,key=lambda x:x[1]['material_utilization'])
    print(W,H,stats,flush=True)
    arts=[];cuts=[];reviewcuts=[]
    for i,p in enumerate(placed):
        name=p['name'];sh=shapes[name];t=transform(p)
        # Prefix clip IDs so multiple instances are independently editable.
        inner=assets[name]['inner'].replace('hat_clip',f'hat_clip_{i}')
        arts.append(f'<g id="item_{i+1:03d}_{name}" transform="{t}">{inner}</g>')
        hx,hy=sh['hole']
        outline=path(poly_path(sh['poly']),'none','#ff0000',.001)
        hole=f'<circle cx="{hx:.5f}" cy="{hy:.5f}" r="1.5" fill="none" stroke="#ff0000" stroke-width="0.001"/>'
        cuts.append(f'<g id="cut_{i+1:03d}_{name}" transform="{t}">{hole}{outline}</g>')
        reviewcuts.append(cuts[-1].replace('0.001','0.18'))
    # Blue reference corners, reserved outside all artwork, never in CUT_ONLY.
    guides=''.join(path(f'M{x+dx*6} {y} L{x} {y} L{x} {y+dy*6}','none','#0000ff',.15) for x,y,dx,dy in [(3,3,1,1),(W-3,3,-1,1),(3,H-3,1,-1),(W-3,H-3,-1,-1)])
    artwork=layer('3_ARTWORK',''.join(arts));guide=layer('2_REFERENCE',guides);cut=layer('1_LASER_CUT',''.join(cuts))
    stem=f'acrylic_{W}x{H}'
    files={'MASTER':artwork+guide+cut,'PRINT':artwork+guide,'CUT_ONLY':cut,'REVIEW':artwork+guide+layer('1_LASER_CUT',''.join(reviewcuts))}
    for typ,content in files.items():
        file=folder/f'{stem}_{typ}.svg'
        file.write_text(svg_doc(W,H,content,f'{W}x{H}mm {typ}'),encoding='utf-8')
    native=folder/f'{stem}_MASTER.vectorcraft'
    runvc(['convert',folder/f'{stem}_MASTER.svg',native])
    # Set mm units and export genuine AI and layered PDF using VectorCraft.
    commands=[{'command':'document.setUnits','params':{'units':'Millimeters'}},
              {'command':'document.save','params':{'path':str(native),'format':'vectorcraft','compress':False}},
              {'command':'document.export','params':{'path':str(folder/f'{stem}_MASTER.ai'),'format':'ai','createLayers':True,'preserveEditing':True}}]
    cmdfile=ROOT/f'tmp/commands_{H}.json';cmdfile.write_text(json.dumps(commands),encoding='utf-8')
    log=runvc(['run','--in',native,'--commands',cmdfile])
    (ROOT/f'tmp/vectorcraft-export-{H}.log').write_text(log,encoding='utf-8')
    write_cut_pdf(placed,shapes,W,H,folder/f'{stem}_CUT_ONLY.pdf')
    runvc(['convert',folder/f'{stem}_REVIEW.svg',ROOT/f'tmp/board_{H}_review.pdf'])
    doc=fitz.open(ROOT/f'tmp/board_{H}_review.pdf');doc[0].get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False).save(str(OUT/f'05_preview/acrylic_{W}x{H}_layout.png'))
    # PNG keeps transparent background + interior white artwork; CMYK TIFF is a RIP fallback.
    commands=[{'command':'document.export','params':{'path':str(folder/f'{stem}_UV_300ppi.png'),'format':'png','ppi':300,'background':'transparent','includeArtboardFill':False}},
              {'command':'document.export','params':{'path':str(folder/f'{stem}_UV_CMYK_300ppi.tif'),'format':'tiff','ppi':300,'colorModel':'cmyk','lzw':True,'embedIcc':True,'background':'white','includeArtboardFill':False}}]
    cmdfile.write_text(json.dumps(commands),encoding='utf-8')
    log=runvc(['run','--in',folder/f'{stem}_PRINT.svg','--commands',cmdfile])
    (ROOT/f'tmp/vectorcraft-raster-{H}.log').write_text(log,encoding='utf-8')
    records=[{k:v for k,v in p.items() if k!='poly'} for p in placed]
    (folder/'layout_manifest.json').write_text(json.dumps({'width_mm':W,'height_mm':H,**stats,'placements':records},indent=2),encoding='utf-8')
    # The review is not an output file used in production; move it to previews.
    (folder/f'{stem}_REVIEW.svg').replace(OUT/f'05_preview/{stem}_REVIEW.svg')
    return stats

def shirt_files(assets):
    a=assets['logo_symbol'];folder=OUT/'01_tshirt'
    # 70 mm square, logo 70 mm high; original aspect ratio preserved.
    scale=70/a['h'];w=a['w']*scale
    inner=f'<g transform="translate({(70-w)/2} 0) scale({scale})">{a["inner"]}</g>'
    p=folder/'tshirt_logo_70mm.svg';p.write_text(svg_doc(70,70,inner,'Left chest logo 70 mm square'),encoding='utf-8')
    runvc(['convert',p,folder/'tshirt_logo_70mm.ai'])
    runvc(['convert',p,folder/'tshirt_logo_70mm.pdf'])
    commands=[{'command':'document.export','params':{'path':str(folder/'tshirt_logo_70mm_300ppi.png'),'format':'png','ppi':300,'background':'transparent','includeArtboardFill':False}},
              {'command':'document.export','params':{'path':str(folder/'tshirt_logo_70mm_600ppi.png'),'format':'png','ppi':600,'background':'transparent','includeArtboardFill':False}}]
    c=ROOT/'tmp/shirt_export.json';c.write_text(json.dumps(commands),encoding='utf-8')
    (ROOT/'tmp/vectorcraft-shirt.log').write_text(runvc(['run','--in',p,'--commands',c]),encoding='utf-8')
    return {'canvas_mm':[70,70],'art_mm':[w,70]}

if __name__=='__main__':
    if '--assets-only' in sys.argv:make_assets();raise SystemExit()
    assets=json.loads((ROOT/'tmp/artwork.json').read_text(encoding='utf-8'))
    shirt=shirt_files(assets)
    shapes=shape_assets(assets)
    stats={}
    for H,folder in [(500,'02_acrylic_800x500'),(600,'03_acrylic_800x600')]:
        stats[str(H)]=board_files(assets,shapes,800,H,OUT/folder)
    (OUT/'production_summary.json').write_text(json.dumps({'shirt':shirt,'boards':stats},indent=2),encoding='utf-8')
