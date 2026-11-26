#!/usr/bin/env python3
"""Native fixture replays and falsifiers for capture_witness; no external input."""
import json
import struct
import sys
from pathlib import Path
import capture_witness as cw
import mode_receipt as mr


def transform(raw, num, den, shift):
    frames=list(struct.iter_unpack('<hh',raw))
    def scale(x): return (1 if x>=0 else -1)*(abs(x)*num//den)
    moved=[(0,0)]*shift+[tuple(map(scale,f)) for f in frames[:len(frames)-shift]]
    return b''.join(struct.pack('<hh',*f) for f in moved)


def main(folder):
    cases=0
    for mode in mr.NAMES:
        raw,bounds=mr.load(Path(folder)/mode)
        for num,den,shift in [(1,8,0),(5,13,97),(5,4,13)]:
            # Shift within existing silent guard windows; retain observation boundaries.
            moved=transform(raw,num,den,shift)
            r=cw.analyse(moved,bounds,mode)
            assert r['status']==('SILENT_UNIDENTIFIED' if mode=='moving' else 'MATCH')
            cases+=1
    raw,bounds=mr.load(Path(folder)/'staggered')
    k=cw.analyse(raw,bounds,'staggered')['start']
    bad=[]
    # Occupancy-preserving channel swap, per-pulse gain change, one extra sample in gap.
    for kind in range(3):
        b=bytearray(raw)
        if kind==2:
            struct.pack_into('<hh',b,4*(k+900),10,0)
        else:
            for i in range(k,k+800):
                x,y=struct.unpack_from('<hh',b,4*i)
                struct.pack_into('<hh',b,4*i,*( (y,x) if kind==0 else (x//2,y//2)))
        # The occupancy gate accepts channel swap and pulse gain alteration.
        if kind<2: mr.analyse(b,bounds,'staggered')
        bad.append(b)
    for b in bad:
        try: cw.analyse(b,bounds,'staggered')
        except ValueError: pass
        else: raise AssertionError('falsifier accepted')
    print(json.dumps(dict(scaled_shifted_replays=cases,negative_controls=len(bad),
                          scope='synthetic native capture transforms only'),sort_keys=True))


if __name__=='__main__': main(sys.argv[1])
