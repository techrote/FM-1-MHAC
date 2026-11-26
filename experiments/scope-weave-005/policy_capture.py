#!/usr/bin/env python3
"""Live panel policy differential witness; exact PCM, not analogue/privacy proof."""
import array
import pathlib
import sys
from context_inverse import atlas, pcm, synth, SLOT

SEQ = [0, 1, 10, 4, 3, 9]
FRAMES = 110250  # 2.5 seconds, before HOME in the 3.1 s play window
N = 2 * FRAMES


def align(a, bounds, templates):
    start, end, mute, stop = bounds
    if not 0 <= start < end <= mute < stop == len(a) or any(x % 2 for x in bounds):
        raise ValueError('capture bounds')
    if any(a[:start]) or any(a[mute:stop]):
        raise ValueError('boot/mute violation')
    first = next((i for i in range(start, end, 2) if max(abs(a[i]), abs(a[i+1])) > 2), None)
    if first is None:
        raise ValueError('no onset')
    from scope_inverse import feasible, GAIN
    matches = []
    for shift in range(65):
        origin = first - 2*shift
        if origin < start or origin+N > end or any(a[start:origin]):
            continue
        if feasible(templates[0], a[origin:origin+len(templates[0])], GAIN) is not None:
            matches.append(origin)
    if len(matches) != 1:
        raise ValueError(f'onset ambiguity {matches}')
    o = matches[0]
    return o, a[o:o+N]


def judge(ref, got, edit, restart):
    if len(ref) != N or len(got) != N or not 0 < edit < N:
        raise ValueError('invalid comparison')
    if not restart:
        if got != ref:
            raise ValueError('equivalent edit changed PCM')
        return None
    if got == ref:
        raise ValueError('expected restart absent')
    diff = next(i for i,(a,b) in enumerate(zip(ref,got)) if a != b)
    # Restart can precede first differing sample by initial shared zeros.
    candidates = []
    for k in range(max(0, (diff//2-64)*2), (diff//2)*2+1, 2):
        if not edit-1024 <= k <= edit+22050:  # DMA allowance, 250 ms upper bound
            continue
        if got[k:] == ref[:N-k]:
            candidates.append(k//2)
    if len(candidates) != 1:
        raise ValueError(f'expected one exact restart, got {candidates}')
    return candidates[0]


def load(prefix, templates):
    p=pathlib.Path(prefix)
    a=pcm(p.with_suffix('.pcm').read_bytes())
    bounds=tuple(map(int,p.with_suffix('.bounds').read_text().split()))
    o, x=align(a,bounds,templates)
    e=int(p.with_suffix('.edit').read_text())
    if not bounds[0] < e < bounds[1] or e%2:
        raise ValueError('missing or invalid edit receipt')
    return x,e-o


def selftest(templates):
    raw=synth(SEQ,templates)
    ref=(raw*4)[:N]
    for gain in (1, 0.385, 0.125):
        x=array.array('h',(round(v*gain) for v in ref))
        a=array.array('h',[0])*400+x+array.array('h',[0])*800
        o,y=align(a,(200,len(a)-800,len(a)-400,len(a)),templates)
        assert o==400 and y==x
        for k in (16000, 17002, 18000):
            z=x[:k*2]+x[:N-k*2]
            assert judge(x,z,k*2-500,True)==k
        assert judge(x,x,32000,False) is None
        for z,e,r in [(x,32000,True),(x[:32000]+x[:N-32000],31500,False),(x[:32000]+x[:N-32000],60000,True)]:
            try: judge(x,z,e,r)
            except ValueError: pass
            else: raise AssertionError('negative control accepted')
    print('native atlas synthetic policy witness: 12 positive / 9 negative PASS')


def main():
    templates=atlas('gcc')
    if len(sys.argv)==1:
        selftest(templates);return
    if len(sys.argv)!=5:
        raise SystemExit('usage: policy_capture.py CONTROL EQ EXPLICIT RAW')
    ref,edit=load(sys.argv[1],templates)
    # Verify control is the expected periodic phrase, not merely any matching stream.
    span=2*SLOT*len(SEQ)
    from scope_inverse import feasible, GAIN
    if feasible(synth(SEQ,templates),ref[:span],GAIN) is None or ref != (ref[:span]*4)[:N]:
        raise ValueError('control is not the expected periodic phrase')
    for p,restart in zip(sys.argv[2:],(False,True,True)):
        x,e=load(p,templates)
        at=judge(ref,x,e,restart)
        print(f'{p}: edit_frame={e//2} restart_frame={at} exact PCM PASS')
    print('live policy modeled DAC comparison PASS')

if __name__=='__main__':main()
