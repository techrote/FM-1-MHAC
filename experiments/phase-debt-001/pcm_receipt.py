#!/usr/bin/env python3
"""Analyse candidate-only, emulator-produced interleaved PCM16. No audio export."""
import hashlib
import json
import struct
import sys
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def analyse(raw, bounds):
    require(0 < len(raw) <= 4 * 44100 * 2 and len(raw) % 4 == 0,
            'invalid stereo capture size')
    frames = list(struct.iter_unpack('<hh', raw))
    require(len(bounds) == 4, 'expected four frame boundaries')
    start, end, mute_start, mute_end = bounds
    require(0 < start < end <= mute_start < mute_end == len(frames),
            'invalid phase boundaries')
    require(end - start >= 10000 and mute_end - mute_start >= 5000,
            'insufficient observed playback or mute duration')
    peak = max(abs(v) for frame in frames for v in frame)
    require(0 < peak <= 6400, 'invalid PCM peak')
    require(not any(l or r for l, r in frames[:start]), 'boot not silent')
    require(not any(l or r for l, r in frames[mute_start:]), 'mute not silent')
    active = [i for i in range(start, end) if any(frames[i])]
    require(active, 'playback not active')
    # Join nonzero spans separated by <=128 frames, bridging oscillator zero
    # crossings but not the ~1405-frame gaps between 800-frame pulses.
    spans = [[active[0], active[0]]]
    for i in active[1:]:
        if i - spans[-1][1] > 129:
            spans.append([i, i])
        else:
            spans[-1][1] = i
    # Exclude window-edge fragments. The first run might begin before the
    # measurement window; no assumption of exact onset phase at button-down.
    interior = [(a, b) for a, b in spans if a > start + 128 and b < end - 129]
    gaps = [b[0] - a[0] for a, b in zip(interior, interior[1:])]
    require(len(interior) >= 3, 'too few complete pulse groups')
    # Conservative cadence diagnostic: allow 4 frames for output quantisation,
    # and a whole DMA block for modeled block-level effects. Report actual gaps.
    require(all(abs(g - 2205) <= 256 for g in gaps), '20 Hz cadence mismatch')
    require(all(0 < b - a + 1 <= 1056 for a, b in interior), 'pulse group too long')
    return dict(sha256=hashlib.sha256(raw).hexdigest(), frames=len(frames),
                boundaries=bounds, peak=peak, active_frames=len(active),
                play_channel_energy=[sum(f[c] ** 2 for f in frames[start:end]) for c in (0, 1)],
                interior_spans=interior, onset_gaps=gaps)


def load(prefix):
    path = Path(prefix)
    raw = path.with_suffix('.pcm').read_bytes()
    bounds = [int(s) for s in path.with_suffix('.bounds').read_text().split()]
    require(all(x % 2 == 0 for x in bounds), 'unaligned interleaved sample boundary')
    return raw, analyse(raw, [x // 2 for x in bounds])


def main(args):
    require(len(args) == 3, 'usage: pcm_receipt.py PUYA UC25HQ80 PUYA_REPEAT')
    a, b, c = map(load, args)
    report = dict(puya=a[1], uc25hq80=b[1], puya_repeat=c[1],
                  same_model_exact=(a == c), cross_model_exact=(a == b),
                  scope='bare-ELF modeled DAC PCM; not physical audition')
    print(json.dumps(report, sort_keys=True), flush=True)
    require(report['same_model_exact'], 'same-model repeat differs')
    # Cross-model equivalence is observational, not a compatibility requirement.


def selftest():
    n = 32000
    bounds = [4000, 21000, 25000, n]
    frames = [(0, 0)] * n
    for onset in range(4500, 20000, 2205):
        for j in range(800):
            frames[onset+j] = (100 if j % 17 else 0, -80)
    def pack(f):
        return b''.join(struct.pack('<hh', *v) for v in f)
    raw = pack(frames)
    report = analyse(raw, bounds)
    assert set(report['onset_gaps']) == {2205}
    cases = [(raw[:-1], bounds), (raw, [4000, 21000, 24999, n-1]),
             (bytes(len(raw)), bounds), (raw, [4000, 4100, 25000, n])]
    for pos, sample in [(0, (1, 0)), (26000, (0, 1)), (5000, (6401, 0))]:
        bad = frames.copy(); bad[pos] = sample; cases.append((pack(bad), bounds))
    bad = frames.copy(); bad[6705:7505] = [(0, 0)] * 800
    cases.append((pack(bad), bounds))
    for sample, marks in cases:
        try:
            analyse(sample, marks)
        except ValueError:
            continue
        raise AssertionError('negative control accepted')
    print(f'PCM receipt selftest PASS: 1 positive, {len(cases)} negative cases')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        selftest()
    else:
        main(sys.argv[1:])
