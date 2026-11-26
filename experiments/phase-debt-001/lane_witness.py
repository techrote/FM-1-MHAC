#!/usr/bin/env python3
"""Exact gain-interval lane attribution for isolated, aligned Phase Debt pulses.
Host-only measurement apparatus. No physical channel or perceptual claim.
"""
import hashlib
from collections import defaultdict
from itertools import combinations
import json
import struct
import sys
from pathlib import Path

N = 800
INC = (21426141,26995255,32139211,42852281,53990510,64278422,85704563,107981019)


def trunc(n, d):
    return n//d if n>=0 else -((-n)//d)


def pulse(j):
    result=[]
    for i in range(N):
        u=((i*INC[j]) & 0xffffffff)>>16
        t=2*u-32768 if u<32768 else 98303-2*u
        gain=i*25 if i<64 else (800-i)*1600//736
        result.append(trunc(t*gain,32768))
    return result


VOICES=[pulse(j) for j in range(8)]
# Each stereo side contains four disjoint lanes, so only 16 templates per side.
TEMPLATES=[[tuple(sum(VOICES[2*j+c][i] for j in range(4) if mask>>j&1)
                  for i in range(N)) for mask in range(16)] for c in range(2)]
# Cheap spaced probes first, followed by EVERY sample. No probabilistic rejection.
PROBES=list(range(0,N,17)) + [i for i in range(N) if i%17]


def interval(observed, template, error, lo=(1,8), hi=(5,4)):
    """Return exact rational feasible gain interval, or None. Inclusive bounds."""
    ln,ld=lo; hn,hd=hi
    for i in PROBES:
        y,x=observed[i],template[i]
        if not x:
            if abs(y)>error: return None
            continue
        if x<0: x,y=-x,-y
        a,b=y-error,y+error
        if a*ld>ln*x: ln,ld=a,x
        if b*hd<hn*x: hn,hd=b,x
        if ln*hd>hn*ld: return None
    return (ln,ld),(hn,hd)


def decode(frames, error=2):
    """All masks compatible with ONE common positive gain in [1/8,5/4]."""
    if len(frames)!=N or not 0<=error<=8:
        raise ValueError('invalid isolated pulse or error bound')
    sides=list(zip(*frames))
    if len(sides)!=2: raise ValueError('stereo required')
    candidates=[]
    for c in range(2):
        matches=[]
        for m,t in enumerate(TEMPLATES[c]):
            r=interval(sides[c],t,error)
            if r is not None: matches.append((m,r))
        candidates.append(matches)
    out=[]
    for a,(al,ah) in candidates[0]:
        for b,(bl,bh) in candidates[1]:
            if al[0]*bh[1]<=bh[0]*al[1] and bl[0]*ah[1]<=ah[0]*bl[1]:
                out.append(sum(((a>>j&1)<<(2*j))|((b>>j&1)<<(2*j+1)) for j in range(4)))
    return sorted(out)


def expected(mask):
    side=[sum((mask>>(2*j+c)&1)<<j for j in range(4)) for c in range(2)]
    return list(zip(TEMPLATES[0][side[0]],TEMPLATES[1][side[1]]))


def separation():
    # If the same observation fitted a*x and b*y with error <=2, then
    # |x - (b/a)*y| <= 4/a <=32 and b/a is in [1/10,10].
    # Refuting this relaxed necessary condition proves disjointness.
    checked=0
    for side in TEMPLATES:
        for x,y in combinations(side,2):
            assert interval(x,y,32,(1,10),(10,1)) is None
            checked+=1
    return checked


def cyclic_census():
    groups=defaultdict(list)
    for mode in range(4):
        for a in range(65):
            p=[]
            for t in range(64):
                mask=sum(1<<j for j in range(8)
                         if ((t+1)*a+(0 if mode==0 else j*8))//64
                         != (t*a+(0 if mode==0 else j*8))//64)
                if mode==2: mask &= ~1
                if mode==3: mask &= mask-1
                p.append(mask)
            groups[min(tuple((p+p)[t:t+64]) for t in range(64))].append((mode,a))
    aliases=[v for v in groups.values() if len(v)>1]
    assert len(groups)==247
    assert aliases==[[(0,0),(1,0),(2,0)]+[(3,a) for a in range(9)],
                     [(0,64),(1,64)],[(2,64),(3,64)]]
    return len(groups),aliases


def main(path):
    pairs=separation()
    classes,aliases=cyclic_census()
    raw=Path(path).read_bytes()
    if len(raw)!=256*N*4: raise ValueError('invalid atlas size')
    checked=0
    for mask in range(256):
        frames=list(struct.iter_unpack('<hh',raw[mask*N*4:(mask+1)*N*4]))
        assert frames==expected(mask), ('independent template mismatch',mask)
        for num,den in [(1,1),(5,13),(1,8),(5,4)]:
            observed=[tuple(trunc(v*num,den) for v in f) for f in frames]
            assert decode(observed)==[mask], ('gain ambiguity',mask,num,den)
            checked+=1
    # Out-of-contract signals must not be forced into a label.
    base=expected(255)
    bad=[[(0,0)]*799, [(-x,-y) for x,y in base],
         [(x,0) for x,y in base], [(x,y//4) for x,y in base],
         [(x+40,y) for x,y in base], [(0,0)]+base[:-1]]
    # Muting one whole side IS a valid different mask, not a refusal.
    assert decode(bad[2])==[85]
    refused=0
    for k in (0,1,3,4,5):
        try: matches=decode(bad[k])
        except ValueError: matches=[]
        assert not matches, ('negative accepted',k,matches)
        refused+=1
    # Zero is the unique template under the gain contract, not proof of transport.
    assert decode(expected(0))==[0]
    print(json.dumps(dict(atlas_sha256=hashlib.sha256(raw).hexdigest(),
          template_masks=256, gain_cases=checked, rejected=refused,
          disjoint_channel_pairs=pairs, cyclic_classes=classes, cyclic_aliases=aliases,
          channel_mute_alias=85, scope='isolated sample-aligned pulses; common gain; error <=2 PCM units'),sort_keys=True))


if __name__=='__main__': main(sys.argv[1])
