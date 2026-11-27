"""Native audition CLI acceptance. Supply GCC and Clang executable paths."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
import struct

bins = [str(Path(p).resolve()) for p in sys.argv[1:]]
assert len(bins) == 2

def render(exe, path, *events):
    p = subprocess.run([exe, str(path), *events], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    with wave.open(str(path), 'rb') as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2,2,44100)
        assert w.getnframes() == sum(int(e.split(':')[0]) for e in events)+2304
        raw = w.readframes(w.getnframes())
    values = struct.unpack('<'+'h'*(len(raw)//2),raw)
    assert max(map(abs,values)) <= 2048
    assert not any(values[-512:])
    return raw

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    results = []
    for i, exe in enumerate(bins):
        data = {}
        for mode in range(3):
            for preset in (3,9):
                key = (mode,preset)
                data[key] = render(exe,root/f'{i}-{mode}-{preset}.wav',f'57600:{preset}:{mode}:26:1')
        assert data[0,3] != data[0,9]
        assert data[1,3] == data[1,9]
        assert data[2,3] == data[2,9]
        a = render(exe,root/f'{i}-one.wav','57600:3:0:26:1')
        b = render(exe,root/f'{i}-split.wav','333:3:0:26:1','57267:3:0:26:1')
        assert a == b
        c = render(exe,root/f'{i}-mute.wav','333:3:0:26:1','4096:3:0:26:0')
        assert not any(c[(333+2048)*4:])
        assert any(c[:333*4])
        bad = ('0:3:0:26:1','1:27:0:26:1','1:3:3:26:1','1:3:0:27:1','1:3:0:26:2','-1:3:0:26:1','1:3:0:26:1x','99999999999999999:3:0:26:1','1:3:0:26','1:3:0:26:1:0')
        for event in bad:
            target = root/'bad.wav'
            p = subprocess.run([exe,str(target),event],capture_output=True)
            assert p.returncode == 2 and not target.exists(), event
        target = root/'bad.wav'
        p = subprocess.run([exe,str(target),'5292000:0:0:0:0','1:0:0:0:0'],capture_output=True)
        assert p.returncode == 2 and not target.exists()
        target = root/'exists.wav'; target.write_bytes(b'preserve')
        p = subprocess.run([exe,str(target),'1:0:0:0:0'],capture_output=True)
        assert p.returncode != 0 and target.read_bytes() == b'preserve'; target.unlink()
        results.append(data)
        print(f'{Path(exe).name}: 9 renders; ordered contrast, sorted/leaf alias, partition and mute checks PASS; 12 rejection controls PASS')
    assert results[0] == results[1]
    print('GCC/Clang: all six independent motif PCM pairs identical across compilers')
