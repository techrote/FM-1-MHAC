"""Exact rational 2D gain feasibility for inconclusive pairs in erasure_screen.
Disjoint continuous intervals imply no integer PCM collision. For feasible
polygons, search for an explicit integer observation (not a complete search).
"""
from fractions import Fraction as F
import math
import sys
from token_decode import read_atlas, intersect, GAIN, N


def clip(poly, x, z, bound=4):
    # Constraint x*a - z*b <= bound.
    out = []
    if not poly:
        return out
    for p, q in zip(poly, poly[1:]+poly[:1]):
        v = x*p[0]-z*p[1]-bound
        w = x*q[0]-z*q[1]-bound
        if v <= 0:
            out.append(p)
        if (v < 0 < w) or (w < 0 < v):
            t = v/(v-w)
            out.append((p[0]+t*(q[0]-p[0]), p[1]+t*(q[1]-p[1])))
    return list(dict.fromkeys(out))


def refine(x, z, indices):
    lo, hi = F(1,8), F(5,4)
    poly = [(lo,lo),(hi,lo),(hi,hi),(lo,hi)]
    # Constraints are exact; no floating-point decisions.
    for i in indices:
        poly = clip(clip(poly, x[i], z[i]), -x[i], -z[i])
        if not poly:
            return 'separated', None
    center = tuple(sum(p[d] for p in poly)/len(poly) for d in (0,1))
    for a,b in [center]+poly:
        obs=[]
        for i in indices:
            l=math.ceil(max(a*x[i],b*z[i])-2)
            h=math.floor(min(a*x[i],b*z[i])+2)
            if l>h: break
            obs.append(l)
        else:
            assert all(abs(v-a*x[i])<=2 and abs(v-b*z[i])<=2 for v,i in zip(obs,indices))
            return 'integer_collision', (a,b)
    return 'continuous_overlap_only', None


def main(atlas_path, receipt_path):
    atlas=read_atlas(atlas_path)[10:]
    for line in open(receipt_path):
        if not line.startswith('refine '): continue
        _,profile,a,b=line.split(); a,b=int(a),int(b)
        indices=list(range(1,2*N,2) if profile=='right' else range(N,2*N))
        result,g=refine(atlas[a][1],atlas[b][1],indices)
        print(profile, atlas[a][0], atlas[b][0], result, g)
    # Known erasure, not zero substitution: return ALL compatible labels.
    label, x=atlas[42]
    indices=range(N)
    obs=x
    matches=[l for l,z in atlas if intersect(z,obs,GAIN,indices) is not None]
    assert len(matches)==16 and set(l[3] for l in matches)==set(range(10,256,16))
    print('first-half token 42 candidates:', [l[3] for l in matches])

if __name__=='__main__':
    main(*sys.argv[1:])
