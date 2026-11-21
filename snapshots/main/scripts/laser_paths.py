"""Manufacturing paths in mm: bounded cubic fitting, exact circles, fail-closed QA.

Artwork and print masks must never pass through this module. Sharp corners and
long straight edges (including tabs) are pinned; mechanical holes are circles.
The polygon is retained for design calculations. The exported curve is checked
against it independently, including topology and bidirectional boundary error.
"""
from functools import lru_cache
import math
import numpy as np
from shapely import from_wkb
from shapely.geometry import Polygon, LineString
from svgpathtools import parse_path, Line, CubicBezier

FIT_MM = .018
MAX_DEVIATION_MM = .035
FLATNESS_MM = .001


def cross2(a,b):
    return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def unit(v):
    n = np.linalg.norm(v)
    return v/n if n > 1e-12 else np.array([1., 0.])


def evaluate(c, t):
    t = np.asarray(t)[:, None]
    return (1-t)**3*c[0]+3*(1-t)**2*t*c[1]+3*(1-t)*t*t*c[2]+t**3*c[3]


def fit_span(p, left, right, error=FIT_MM):
    """Least-squares cubic, recursively split with a shared tangent at joins."""
    if len(p) == 2:
        d = np.linalg.norm(p[-1]-p[0])/3
        return [('C', np.array([p[0], p[0]+left*d, p[-1]+right*d, p[-1]]))]
    dist = np.linalg.norm(np.diff(p, axis=0), axis=1)
    u = np.r_[0, np.cumsum(dist)]; u /= u[-1]
    b0, b1, b2, b3 = (1-u)**3, 3*(1-u)**2*u, 3*(1-u)*u*u, u**3
    a = np.stack([b1[:, None]*left, b2[:, None]*right], axis=2).reshape(-1, 2)
    rhs = (p-(b0+b1)[:, None]*p[0]-(b2+b3)[:, None]*p[-1]).reshape(-1)
    alpha = np.linalg.lstsq(a, rhs, rcond=None)[0]
    chord = np.linalg.norm(p[-1]-p[0])
    if min(alpha) < 1e-7 or max(alpha) > max(chord*3, .1):
        alpha[:] = chord/3
    c = np.array([p[0], p[0]+left*alpha[0], p[-1]+right*alpha[1], p[-1]])
    errors = np.linalg.norm(evaluate(c, u)-p, axis=1)
    split = int(np.argmax(errors))
    if errors[split] <= error:
        return [('C', c)]
    split = min(max(split, 1), len(p)-2)
    center = unit(p[split-1]-p[split+1])
    return fit_span(p[:split+1], left, center, error)+fit_span(p[split:], -center, right, error)


def flatten_cubic(c, tolerance=FLATNESS_MM):
    chord = c[3]-c[0]; length = np.linalg.norm(chord)
    if length > 1e-12:
        distances = np.abs(cross2(chord, c[1:3]-c[0]))/length
        projections = (c[1:3]-c[0])@chord/(length*length)
        flat = max(distances) <= tolerance and min(projections) >= 0 and max(projections) <= 1
    else:
        flat = np.max(np.linalg.norm(c-c[0], axis=1)) <= tolerance
    if flat:
        return [c[0], c[3]]
    a=(c[0]+c[1])/2; b=(c[1]+c[2])/2; d=(c[2]+c[3])/2
    e=(a+b)/2; f=(b+d)/2; g=(e+f)/2
    return flatten_cubic(np.array([c[0],a,e,g]),tolerance)[:-1]+flatten_cubic(np.array([g,f,d,c[3]]),tolerance)


def segments_polygon(segments):
    pts=[]
    for kind, c in segments:
        pts.extend((flatten_cubic(c) if kind=='C' else [c[0],c[-1]])[:-1])
    return Polygon(pts)


def circle_segments(center, radius):
    k=4/3*math.tan(math.pi/8); segments=[]
    for i in range(4):
        t=i*math.pi/2; u=t+math.pi/2
        a=center+radius*np.array([math.cos(t),math.sin(t)])
        d=center+radius*np.array([math.cos(u),math.sin(u)])
        b=a+k*radius*np.array([-math.sin(t),math.cos(t)])
        c=d-k*radius*np.array([-math.sin(u),math.cos(u)])
        segments.append(('C',np.array([a,b,c,d])))
    segments[-1][1][-1]=segments[0][1][0]
    return segments


@lru_cache(maxsize=1024)
def fitted(wkb):
    poly=from_wkb(wkb)
    if not poly.is_valid or poly.geom_type!='Polygon' or poly.interiors:
        raise ValueError('Each laser contour must be one valid polygon without interior rings')
    p=np.array(poly.exterior.coords[:-1],dtype=float)
    # Remove duplicate vertices before any tangent/length calculation.
    keep=np.linalg.norm(p-np.roll(p,1,axis=0),axis=1)>1e-8
    p=p[keep]
    source_vertices=len(p)
    center=np.array(poly.centroid.coords[0]); radii=np.linalg.norm(p-center,axis=1)
    circular=(len(p)>=16 and np.ptp(radii)<.0002 and
              abs(poly.length-2*math.pi*np.mean(radii))<.01)
    if circular:
        # Buffer-generated holes have exact extrema. Keep their diameter/center.
        x0,y0,x1,y1=poly.bounds
        center=np.array([(x0+x1)/2,(y0+y1)/2]); r=(x1-x0+y1-y0)/4
        segments=circle_segments(center,r)
    else:
        # Remove sub-resolution offset/buffer artifacts before tangent fitting.
        p=np.array(poly.simplify(.002,preserve_topology=True).exterior.coords[:-1])
        edges=np.roll(p,-1,axis=0)-p; lengths=np.linalg.norm(edges,axis=1)
        tangents=edges/lengths[:,None]
        angles=np.degrees(np.arccos(np.clip((tangents*np.roll(tangents,1,axis=0)).sum(1),-1,1)))
        # All true sharp corners and both endpoints of every long straight are fixed.
        pins=set(np.flatnonzero((angles>32)&(lengths>.12)&(np.roll(lengths,1)>.12)))
        axis=(np.min(np.abs(edges),axis=1)<1e-7)
        isolated=lengths>4*np.minimum(np.roll(lengths,1),np.roll(lengths,-1))
        fixed_lines=set(np.flatnonzero((lengths>=2)&(axis|isolated)))
        for i in fixed_lines:pins.update([int(i),int((i+1)%len(p))])
        # Anchor extrema, so smooth silhouettes cannot drift or be rescaled.
        pins.update(int(np.argmin(p[:,j])) for j in range(2))
        pins.update(int(np.argmax(p[:,j])) for j in range(2))
        pins=sorted(pins); segments=[]
        for start,end in zip(pins,pins[1:]+[pins[0]+len(p)]):
            span=p[np.arange(start,end+1)%len(p)]
            if len(span)==2:
                segments.append(('L',span));continue
            # Densification bounds deviation between sparse polygon vertices too.
            dense=[]
            for a,b in zip(span,span[1:]):
                n=max(1,math.ceil(np.linalg.norm(b-a)/.12))
                dense.extend(a+(b-a)*np.arange(n)[:,None]/n)
            dense=np.array(dense+[span[-1]])
            chord=span[-1]-span[0]; ln=np.linalg.norm(chord)
            if ln>0 and np.max(np.abs(cross2(chord,dense-span[0]))/ln)<.001:
                segments.append(('L',np.array([span[0],span[-1]])));continue
            # Tangents at pinned smooth points are shared across adjacent spans.
            def tangent(index, backward=False):
                index%=len(p)
                if angles[index]>32:
                    v=(p[index-1]-p[index]) if backward else (p[(index+1)%len(p)]-p[index])
                elif index in fixed_lines:
                    v=edges[index]*(-1 if backward else 1)
                elif (index-1)%len(p) in fixed_lines:
                    v=edges[(index-1)%len(p)]*(-1 if backward else 1)
                else:
                    v=p[(index+1)%len(p)]-p[index-1]
                    if backward:v=-v
                return unit(v)
            segments.extend(fit_span(dense,tangent(start),tangent(end,True)))
    curve=segments_polygon(segments)
    if not curve.is_valid or not curve.exterior.is_simple:
        raise ValueError('Fitted laser curve self-intersects')
    delta=poly.boundary.hausdorff_distance(curve.boundary)
    if delta>MAX_DEVIATION_MM:
        raise ValueError(f'Curve deviation {delta:.6f} mm exceeds {MAX_DEVIATION_MM}')
    if len(segments)>max(100,poly.length*1.5):
        raise ValueError(f'Unresolved excessive nodes: {len(segments)} / {poly.length:.2f} mm')
    return segments,{'source_vertices':source_vertices,'segments':len(segments),
                     'curves':sum(k=='C' for k,c in segments),
                     'max_boundary_deviation_mm':delta,'circle_center_diameter_preserved':bool(circular)},curve


def cut_path(poly):
    segments,_,_=fitted(poly.wkb)
    def xy(pt):return f'{pt[0]:.6f} {pt[1]:.6f}'
    text='M'+xy(segments[0][1][0])
    for kind,c in segments:
        text+=' '+kind+' '+' '.join(xy(q) for q in (c[1:] if kind=='C' else [c[-1]]))
    text+=' Z'
    audit_path(text)
    return text


def draw_cut_pdf(page,poly,color=(1,0,0),width=.001):
    from pymupdf import Point
    cut_path(poly)  # Apply the same fail-closed serialized-path gate as SVG/AI.
    mm=72/25.4; shape=page.new_shape()
    for kind,c in fitted(poly.wkb)[0]:
        pts=[Point(*(q*mm)) for q in c]
        if kind=='C':shape.draw_bezier(*pts)
        else:shape.draw_line(pts[0],pts[-1])
    shape.finish(color=color,width=width*mm,closePath=True);shape.commit()


def audit_path(d, allow_original_numerics=False):
    """Reject oversegmentation, zero edges and pathological local direction flips."""
    p=parse_path(d)
    if not p.isclosed():raise ValueError('Open laser path')
    lengths=np.array([s.length() for s in p]); perimeter=float(sum(lengths))
    numeric_notes=[]
    if min(lengths)<1e-6:
        if not allow_original_numerics:raise ValueError('Zero-length laser segment')
        numeric_notes.append({'kind':'zero_length_no_op','count':int(sum(lengths<1e-6))})
    if len(p)>max(100,perimeter*1.5):raise ValueError(f'Too many segments: {len(p)} / {perimeter:.2f} mm')
    # Three consecutive sub-0.1 mm straight moves are never a useful feature here.
    short=np.array([isinstance(s,Line) and s.length()<.1 for s in p],int)
    if any(short+np.roll(short,1)+np.roll(short,2)>=3):raise ValueError('Micro-line chain')
    points=[]
    for s in p:
        if isinstance(s,CubicBezier):
            points.extend(flatten_cubic(np.array([[z.real,z.imag] for z in [s.start,s.control1,s.control2,s.end]]))[:-1])
        elif isinstance(s,Line):points.append([s.start.real,s.start.imag])
        else:
            points.extend([[s.point(t).real,s.point(t).imag] for t in np.linspace(0,1,max(8,math.ceil(s.length()/.05)),endpoint=False)])
    poly=Polygon(points)
    if not poly.is_valid:
        repaired=poly.buffer(0)
        deviation=poly.boundary.hausdorff_distance(repaired.boundary)
        if not (allow_original_numerics and repaired.geom_type=='Polygon' and deviation<=.0001 and abs(poly.area-repaired.area)<1e-6):
            raise ValueError('Self-intersection in laser contour')
        numeric_notes.append({'kind':'export_roundoff_below_0.0001mm','boundary_difference_mm':deviation})
        poly=repaired
    return {'segments':len(p),'curves':sum(not isinstance(s,Line) for s in p),
            'perimeter_mm':perimeter,'minimum_segment_mm':float(min(lengths)),
            'original_numerical_notes':numeric_notes},poly
