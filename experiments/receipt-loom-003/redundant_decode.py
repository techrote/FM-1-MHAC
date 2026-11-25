"""Receipt Loom repeated-motif inverse: known aligned erasures, not audio input.
Missing positions are absent, never interpreted as measured silence.
"""
import array
import pathlib
import sys
from token_decode import N, GAIN, pcm16, intersect, capture, groups, decode

PROFILES = {
    'full': tuple(range(2*N)),
    'half_right_stride4': tuple(2*i+1 for i in range(0,N//2,4)),
    'first_quarter': tuple(range(N//2)),
}


def atlas_read(path):
    a = pcm16(pathlib.Path(path).read_bytes())
    labels = [(1,k,b,t) for k in range(1,6) for b in range(2) for t in range(256)]
    if len(a) != len(labels)*2*N:
        raise ValueError('invalid repeated atlas length')
    return [(label,a[i*2*N:(i+1)*2*N]) for i,label in enumerate(labels)]


def project(atlas, positions):
    if not positions or tuple(sorted(set(positions))) != tuple(positions) or not 0 <= positions[0] <= positions[-1] < 2*N:
        raise ValueError('invalid retained positions')
    return [(label,array.array('h',(x[i] for i in positions))) for label,x in atlas]


def invert(projected, y, gain=GAIN):
    if not projected or not y or len(y) != len(projected[0][1]):
        raise ValueError('invalid projected observation')
    probes = tuple(j*len(y)//25 for j in range(1,25))
    result = []
    for label,x in projected:
        b = intersect(x,y,gain,probes)
        if b is not None:
            b = intersect(x,y,b,range(len(y)))
            if b is not None:
                result.append((label,b))
    return result


def selftest(atlas):
    p = project(atlas,PROFILES['half_right_stride4'])
    q = project(atlas,PROFILES['first_quarter'])
    for i,(label,x) in enumerate(p):
        a,b = ((1,8),(385,1000),(5,4))[i%3]
        y = array.array('h',(v*a//b+((j+i)%3-1) for j,v in enumerate(x)))
        m = invert(p,y)
        if len(m)!=1 or m[0][0]!=label:
            raise ValueError(f'wrong sparse identity {label}: {m}')
    for i in (0,42,255,256,1023,2559):
        label,x = q[i]
        expected = {(*label[:3],t) for t in range(label[3]&15,256,16)}
        if {l for l,_ in invert(q,x)} != expected:
            raise ValueError('quarter ambiguity was not preserved')
    y = array.array('h',p[42][1]); y[0]=30000
    if invert(p,y) or invert(p,array.array('h',[0])*len(y)):
        raise ValueError('negative control accepted')
    print('sparse identities=2560 gain endpoints/interior with bounded error; quarter ambiguity=6/6; negative=2/2 PASS')


def check_capture(atlas,prefix,mode):
    # Full capture establishes boot/mute, sequence, timing and independent oracle.
    # Sparse inversion below is conditional on that alignment, not blind acquisition.
    if not 0 <= mode < 5:
        raise ValueError('invalid redundant mode')
    labels = capture(atlas,prefix,mode+5)
    p = pathlib.Path(prefix)
    pcm = pcm16(p.with_suffix('.pcm').read_bytes())
    start,stop,_,_ = [int(v)//2 for v in p.with_suffix('.bounds').read_text().split()]
    first = next(groups(pcm,start,stop))[0]
    candidates = []
    for offset in range(1,5):
        base = first-offset
        if base < start:
            continue
        m = decode(atlas,pcm[2*base:2*(base+N)],1)
        if len(m)==1 and m[0][0]==labels[0][1]:
            candidates.append(base)
    if len(candidates)!=1:
        raise ValueError('first-motif alignment not unique')
    base = candidates[0]
    pos = PROFILES['half_right_stride4']; proj = project(atlas,pos)
    gain = GAIN
    for tick,label in labels:
        onset = base+tick*6800
        y = array.array('h',(pcm[2*onset+i] for i in pos))
        m = invert(proj,y,gain)
        if len(m)!=1 or m[0][0]!=label:
            raise ValueError(f'sparse mismatch tick {tick}: {m}')
        gain = m[0][1]
    print(f'redundant mode={mode} sparse_pulses={len(labels)} retained=256 common_gain={gain} PASS')


if __name__=='__main__':
    atlas = atlas_read(sys.argv[1])
    if sys.argv[2]=='--selftest':
        selftest(atlas)
    else:
        check_capture(atlas,sys.argv[2],int(sys.argv[3]))
