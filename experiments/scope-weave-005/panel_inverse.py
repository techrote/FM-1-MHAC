#!/usr/bin/env python3
"""Strict panel PCM witness; known rate, search bounded integer onset offsets."""
import argparse
import array
import pathlib
import sys
from fractions import Fraction as F
from scope_inverse import native, inverse, tokens, REST, ENV, GAIN

RATE=12
TICK=10000-200*RATE
SPAN=12*TICK


def verify(pcm,bounds,atlas,mode,preset):
    if not 0<=mode<3 or not 0<=preset<27:
        raise ValueError('panel selection')
    if len(bounds)!=4 or not 0<=bounds[0]<bounds[1]<=bounds[2]<bounds[3]==len(pcm) or any(b%2 for b in bounds):
        raise ValueError('capture bounds')
    start,end,mute,stop=bounds
    if any(pcm[:start]) or any(pcm[mute:stop]):
        raise ValueError('boot/mute not silent')
    first=next((i for i in range(start,end,2) if max(abs(pcm[i]),abs(pcm[i+1]))>2),None)
    if first is None:
        raise ValueError('no positive witness')
    seq=tokens(preset,mode)
    first_slot=next(j for j,t in enumerate(seq) if t!=REST)
    expected={q for q in range(27) if tokens(q,mode)==seq}
    matches=[]
    for shift in range(33):
        origin=first-2*(shift+first_slot*TICK)
        if origin<start or origin+2*SPAN>end or any(pcm[start:origin]):
            continue
        g=GAIN
        for j in range(2):
            a=origin+j*SPAN
            candidates=inverse(pcm[a:a+SPAN],atlas,RATE,modes=(mode,))
            if {p for _,p,_ in candidates}!=expected:
                break
            lo,hi=candidates[0][2]
            g=max(g[0],lo),min(g[1],hi)
            if g[0]>g[1]:
                break
        else:
            matches.append((origin//2,g))
    if len(matches)!=1:
        raise ValueError(f'expected unique alignment; found {matches}')
    print(f'mode={mode} preset={preset} compatible={sorted(expected)} origin_frame={matches[0][0]} gain={matches[0][1]} two_phrases=PASS')
    return matches[0]


def selftest(atlas):
    for mode in range(3):
        for preset in (3,9):
            phrase=array.array('h')
            for t in tokens(preset,mode):
                phrase.extend(round(F(77,200)*v) for v in atlas[t]);phrase.extend([0]*(2*(TICK-ENV)))
            pcm=array.array('h',[0])*400+phrase*2+array.array('h',[0])*1000
            bounds=(200,len(pcm)-800,len(pcm)-400,len(pcm))
            assert verify(pcm,bounds,atlas,mode,preset)[0]==200
            if mode==0:
                try: verify(pcm,bounds,atlas,mode,9 if preset==3 else 3)
                except ValueError: pass
                else: raise AssertionError('wrong ordered preset accepted')
    print('native modeled-panel fixture controls PASS (not emulation)')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('prefix',nargs='?',type=pathlib.Path)
    ap.add_argument('mode',nargs='?',type=int);ap.add_argument('preset',nargs='?',type=int)
    args=ap.parse_args()
    atlas,_,_=native('gcc')
    if args.prefix is None:
        selftest(atlas)
    else:
        pcm=array.array('h');pcm.frombytes(args.prefix.with_suffix('.pcm').read_bytes())
        if sys.byteorder!='little':pcm.byteswap()
        bounds=tuple(map(int,args.prefix.with_suffix('.bounds').read_text().split()))
        verify(pcm,bounds,atlas,args.mode,args.preset)
