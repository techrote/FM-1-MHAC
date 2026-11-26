#!/usr/bin/env python3
"""FM1-001 density-7 mode fingerprint, synthetic or bare-ELF PCM only."""
import hashlib
import json
import struct
import sys
from pathlib import Path

STEP, SLOTS, TOL = 2205, 24, 256
NAMES = ('aligned', 'staggered', 'fixed', 'moving')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def pattern(mode):
    # Independent closed-form carry differences, not the C accumulator.
    masks = []
    for t in range(64):
        mask = sum(1 << j for j in range(8)
                   if ((t+1)*7+(0 if mode == 0 else j*8))//64
                   != (t*7+(0 if mode == 0 else j*8))//64)
        if mode == 2:
            mask &= ~1
        if mode == 3:
            mask &= mask-1
        masks.append(int(bool(mask)))
    return masks


def signatures(mode):
    p = pattern(mode)
    return {tuple((p+p)[i:i+SLOTS]) for i in range(64) if p[i]}


def analyse(raw, bounds, mode):
    need(mode in NAMES, 'unknown mode')
    need(0 < len(raw) <= 4*44100*5 and len(raw)%4 == 0, 'bad PCM size')
    frames = list(struct.iter_unpack('<hh', raw))
    need(len(bounds) == 4, 'bad bounds count')
    a,b,c,d = bounds
    need(0 < a < b <= c < d == len(frames), 'bad boundaries')
    need(b-a >= 85000 and d-c >= 5000, 'short playback or mute window')
    need(not any(x or y for x,y in frames[:a]), 'boot not silent')
    need(not any(x or y for x,y in frames[c:]), 'mute not silent')
    peak = max(abs(v) for f in frames for v in f)
    need(peak <= 6400, 'peak bound')
    active = [i for i in range(a,b) if any(frames[i])]
    if mode == 'moving':
        need(peak == 0, 'moving-loss should emit nothing at density seven')
        return dict(mode=mode, peak=peak, sha256=hashlib.sha256(raw).hexdigest(),
                    signature=None, scope='silence alone does not identify the mode')
    need(active, 'no positive playback control')
    spans = []
    for i in active:
        if not spans or i-spans[-1][1] > 129:
            spans.append([i,i])
        else:
            spans[-1][1] = i
    interior = [(x,y) for x,y in spans if x>a+TOL and y<b-TOL]
    need(interior, 'no complete pulse')
    anchor = interior[0][0]
    end = anchor+SLOTS*STEP
    need(end+TOL <= b, 'not enough complete tick slots')
    observed = [0]*SLOTS
    for x,y in interior:
        if x >= end-TOL:
            break
        slot = (x-anchor+STEP//2)//STEP
        need(0<=slot<SLOTS and abs(x-anchor-slot*STEP)<=TOL, 'off-grid pulse')
        need(not observed[slot] and 0<y-x+1<=1056, 'duplicate or long pulse')
        observed[slot] = 1
    matches = [NAMES[m] for m in range(3) if tuple(observed) in signatures(m)]
    need(matches == [mode], 'wrong or ambiguous positive mode: '+str(matches))
    return dict(mode=mode, peak=peak, sha256=hashlib.sha256(raw).hexdigest(),
                signature=''.join(map(str,observed)), groups=sum(observed),
                anchor=anchor, matched=matches)


def load(prefix):
    p=Path(prefix)
    marks=list(map(int,p.with_suffix('.bounds').read_text().split()))
    need(all(x%2 == 0 for x in marks), 'unaligned sample bounds')
    return p.with_suffix('.pcm').read_bytes(), [x//2 for x in marks]


def main(folder):
    for i in range(3):
        for j in range(i):
            need(not signatures(i)&signatures(j), 'oracle fingerprints overlap')
    data={m:load(Path(folder)/m) for m in NAMES}
    report={m:analyse(*data[m],m) for m in NAMES}
    # Every cross-label substitution must fail, including silence versus positives.
    rejected=0
    for a in NAMES:
        for b in NAMES:
            if a==b:
                continue
            try:
                analyse(*data[a],b)
            except ValueError:
                rejected+=1
            else:
                raise ValueError('cross-label substitution accepted')
    # Independent cadence falsifier: shift a complete staggered pulse by 400 frames.
    raw,bounds=data['staggered']; bad=bytearray(raw)
    k=report['staggered']['anchor']; pulse=bad[4*k:4*(k+800)]
    bad[4*k:4*(k+800)]=bytes(3200)
    bad[4*(k+400):4*(k+1200)]=pulse
    try:
        analyse(bad,bounds,'staggered')
    except ValueError:
        rejected+=1
    else:
        raise ValueError('off-grid control accepted')
    print(json.dumps(dict(modes=report, negative_controls=rejected,
          scope='density-7 event occupancy, not unique density or lane identification; moving needs paired positive controls'),sort_keys=True))


if __name__ == '__main__':
    main(sys.argv[1])
