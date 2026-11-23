"""Deterministic contour nesting; raster masks propose placements, vectors verify them.

Masks are search aids only. Original cutting curves are never rasterized for export.
"""
import math,random
import numpy as np
import cv2
from PIL import Image,ImageDraw
from shapely import affinity


def rotated(piece,angle):
    x0,y0,_,_=piece['bounds']
    p=affinity.translate(piece['poly'],-x0,-y0)
    a=math.radians(angle);c,s=math.cos(a),math.sin(a)
    q=affinity.affine_transform(p,[c,s,-s,c,0,0])
    rx,ry,_,_=q.bounds
    return affinity.translate(q,-rx,-ry),(rx,ry)


def contour_nest(pieces,size,margin,gap,trials=48,resolution=.75):
    width,height=size[0]-2*margin,size[1]-2*margin
    nx,ny=math.floor(width/resolution)+1,math.floor(height/resolution)+1
    orientations={}
    for p in pieces:
        choices=[]
        # Straight scenery and the long base gain nothing from oblique rotation.
        angles=[0,90] if max(p['bounds'][2]-p['bounds'][0],p['bounds'][3]-p['bounds'][1])>200 else range(0,360,15)
        for angle in angles:
            poly,origin=rotated(p,angle);_,_,w,h=poly.bounds
            mask=Image.new('L',(math.ceil(w/resolution)+1,math.ceil(h/resolution)+1))
            ImageDraw.Draw(mask).polygon([(x/resolution,y/resolution) for x,y in poly.exterior.coords],fill=1)
            choices.append((angle,poly,origin,w,h,np.asarray(mask,dtype=np.float32)))
        orientations[p['id']]=choices
    rng=random.Random(20261121);best=None
    for attempt in range(trials):
        vertical=attempt%2==1
        cap=width if vertical else min(width,[404,380,360,340,320,300][(attempt//2)%6])
        active_nx=math.floor(cap/resolution)+1
        ranks={p['id']:p['poly'].area*rng.uniform(.75,1.25) for p in pieces}
        order=sorted(pieces,key=lambda p:ranks[p['id']],reverse=True)
        occupied=Image.new('L',(active_nx,ny));placed=[];shapes=[];right=bottom=0.0
        for index,p in enumerate(order):
            candidates=[];occ=np.asarray(occupied,dtype=np.float32)
            for angle,poly,origin,w,h,mask in orientations[p['id']]:
                mh,mw=mask.shape
                if mh>ny or mw>active_nx:continue
                collision=cv2.matchTemplate(occ,mask,cv2.TM_CCORR)
                ys,xs=np.where(collision<.25)
                if len(xs)==0:continue
                xx=xs*resolution;yy=ys*resolution
                xr=np.maximum(right,xx+w);yb=np.maximum(bottom,yy+h)
                score=(xr*height+yb*.02 if vertical else yb*width+xr*.02)
                score+=((xx+yy)*.00001)
                top=np.argpartition(score,min(4,len(score)-1))[:5]
                for i in top:candidates.append((float(score[i]),float(xx[i]),float(yy[i]),angle,w,h,poly,origin))
            candidates.sort(key=lambda q:q[:4]);choice=None
            for _,x,y,angle,w,h,poly,origin in candidates:
                q=affinity.translate(poly,x,y)
                if all(q.distance(other)>=gap-.00001 for other in shapes):
                    choice=(x,y,angle,w,h,poly,origin,q);break
            if choice is None:break
            x,y,angle,w,h,poly,origin,q=choice
            placed.append(dict(piece=p,x=x+margin,y=y+margin,w=w,h=h,rotation=angle,rotated_origin=origin))
            shapes.append(q);right=max(right,x+w);bottom=max(bottom,y+h)
            # Conservative occupied envelope, with exact vector distance checked above.
            inflated=q.buffer(gap+resolution*.8)
            ImageDraw.Draw(occupied).polygon([(a/resolution,b/resolution) for a,b in inflated.exterior.coords],fill=1)
        if len(placed)!=len(pieces):continue
        area=right*bottom
        if best is None or area<best[0]:
            best=(area,placed)
            print('NEST',attempt+1,'occupied',round(right,2),round(bottom,2),'area',round(area),flush=True)
    assert best is not None,'No contour layout fits at unchanged scale and clearance'
    placed=best[1]
    shapes=[affinity.translate(rotated(p['piece'],p['rotation'])[0],p['x'],p['y']) for p in placed]
    # Remove conservative raster padding using only exact vector distances.
    # Monotone left/up moves cannot enlarge the occupied rectangle.
    for step in [.75,.25,.05]:
        for _ in range(3):
            for axis in ['x','y']:
                for i in sorted(range(len(placed)),key=lambda i:placed[i][axis]):
                    while placed[i][axis]-step>=margin-1e-9:
                        dx,dy=(-step,0) if axis=='x' else (0,-step)
                        q=affinity.translate(shapes[i],dx,dy)
                        if any(q.distance(other)<gap+.01 for j,other in enumerate(shapes) if i!=j):break
                        placed[i][axis]-=step;shapes[i]=q
    for i,p in enumerate(shapes):
        assert p.bounds[0]>=margin-1e-8 and p.bounds[1]>=margin-1e-8
        assert p.bounds[2]<=size[0]-margin+1e-8 and p.bounds[3]<=size[1]-margin+1e-8
        assert all(p.distance(q)>=gap-.00001 for q in shapes[:i])
    return [{'placements':placed}]
