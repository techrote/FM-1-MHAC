#!/usr/bin/env python3
"""Phase Debt capture attribution: bounded alignment search, shared gain, full masks.
Host measurement only; no claim about analogue signals or moving-loss silence.
"""
import json
import struct
import sys
from pathlib import Path
from fractions import Fraction
import lane_witness as lw
import mode_receipt as mr


def masks(mode, density=7):
    out = []
    for t in range(64):
        mask = sum(1 << j for j in range(8)
                   if ((t+1)*density+(0 if mode==0 else j*8))//64
                   != (t*density+(0 if mode==0 else j*8))//64)
        if mode==2: mask &= ~1
        if mode==3: mask &= mask-1
        out.append(mask)
    return out


def fit(frames, mask, lo, hi):
    for side, samples in enumerate(zip(*frames)):
        m = sum(((mask >> (2*j+side)) & 1) << j for j in range(4))
        r = lw.interval(samples, lw.TEMPLATES[side][m], 2,
                        (lo.numerator,lo.denominator),(hi.numerator,hi.denominator))
        if r is None: return None
        lo, hi = map(lambda x: Fraction(*x), r)
    return lo, hi


def analyse(raw, bounds, mode):
    prior = mr.analyse(raw, bounds, mode)
    if mode == 'moving':
        return dict(mode=mode, status='SILENT_UNIDENTIFIED', sha256=prior['sha256'])
    frames = list(struct.iter_unpack('<hh', raw))
    a,b,_,_ = bounds
    # Exact zero gaps are required. Bounded search includes leading quantized zeros.
    candidates = []
    for start in range(prior['anchor']-8,prior['anchor']+1):
        if start < a or start+mr.SLOTS*mr.STEP > b: continue
        slots = [frames[start+k*mr.STEP:start+(k+1)*mr.STEP] for k in range(mr.SLOTS)]
        if any(any(x or y for x,y in s[lw.N:]) for s in slots): continue
        observed = tuple(int(any(x or y for x,y in s[:lw.N])) for s in slots)
        for m in range(3):
            p = masks(m)*2
            for seq in sorted({tuple(p[i:i+mr.SLOTS]) for i in range(64) if p[i]}):
                if tuple(map(bool,seq)) != observed: continue
                lo,hi=Fraction(1,8),Fraction(5,4)
                for s,mask in zip(slots,seq):
                    r=fit(s[:lw.N],mask,lo,hi)
                    if r is None: break
                    lo,hi=r
                else:
                    candidates.append((start,m,seq,lo,hi))
    mr.need(len(candidates)==1, 'expected unique alignment/mode/masks; matches='+str(len(candidates)))
    start,m,seq,lo,hi=candidates[0]
    mr.need(mr.NAMES[m]==mode,'lane contract label mismatch')
    return dict(mode=mode,status='MATCH',start=start,masks=list(seq),gain=[str(lo),str(hi)],sha256=prior['sha256'])


def main(folder):
    results={m:analyse(*mr.load(Path(folder)/m),m) for m in mr.NAMES}
    print(json.dumps(results,sort_keys=True))


if __name__=='__main__': main(sys.argv[1])
