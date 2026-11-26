#!/usr/bin/env python3
"""Build an offline audition index from the three original host fixture packs.
No target firmware, device access, network, or human-study instrumentation.
Run from any directory: python collection.py PATH_TO_EXTRACTED_COLLECTION.
"""
import argparse
import hashlib
import html
import json
import struct
import wave
from pathlib import Path

GROUPS = {
    'Phase Debt': [f'phase/wav/{m}-{d}.wav' for m in ('aligned','staggered','fixed','moving') for d in (8,24)] + ['phase/wav/performance.wav'],
    'Receipt Loom': [f'receipt/wav/{f}-{m}.wav' for f in ('legacy','tagged','redundant') for m in ('clean','first-loss','stale-bound','stale-latest','blackout','performance')],
    'Scope Weave': [f'scope/mode{m}-preset{p}.wav' for m in range(3) for p in (3,9)] + ['scope/continuous.wav'],
}
PAIRS = [
    ('Phase: aligned / staggered, density 8','phase/wav/aligned-8.wav','phase/wav/staggered-8.wav',False),
    ('Phase: fixed / moving loss, density 8','phase/wav/fixed-8.wav','phase/wav/moving-8.wav',False),
] + [(f'Receipt: {f}, clean / stale latest',f'receipt/wav/{f}-clean.wav',f'receipt/wav/{f}-stale-latest.wav',f=='legacy') for f in ('legacy','tagged','redundant')] + [
    (f'Scope: {name}, Q(N(B)) / N(Q(B))',f'scope/mode{m}-preset3.wav',f'scope/mode{m}-preset9.wav',m!=0) for m,name in enumerate(('ordered','sorted','leaf only'))]

def collect(root):
    data={}
    for group,paths in GROUPS.items():
        for rel in paths:
            path=root/rel
            with wave.open(str(path),'rb') as w:
                if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())!=(2,2,44100,'NONE'):
                    raise ValueError(f'Invalid WAV format: {rel}')
                frames=w.getnframes()
                if not 0<frames<=44100*121:
                    raise ValueError(f'Invalid frame count: {rel}')
                pcm=w.readframes(frames)
            if len(pcm)!=frames*4:
                raise ValueError(f'Truncated PCM: {rel}')
            peak=max(abs(s[0]) for s in struct.iter_unpack('<h',pcm))
            if peak>(6400 if group=='Phase Debt' else 2048) or (peak==0)!=(rel=='phase/wav/moving-8.wav'):
                raise ValueError(f'Unexpected amplitude or silence: {rel}')
            if any(pcm[-4:]):
                raise ValueError(f'Nonzero final frame: {rel}')
            data[rel]={'group':group,'frames':frames,'peak':peak,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pcm_sha256':hashlib.sha256(pcm).hexdigest()}
    for name,a,b,same in PAIRS:
        if (data[a]['pcm_sha256']==data[b]['pcm_sha256'])!=same:
            raise ValueError(f'Unexpected PCM equivalence: {name}')
    return data

def page(data):
    esc=html.escape
    options=''.join(f'<option value="{i}">{esc(p[0])}</option>' for i,p in enumerate(PAIRS))
    rows=[]
    for group,paths in GROUPS.items():
        rows.append(f'<h2>{esc(group)}</h2><table><thead><tr><th>Clip</th><th>Seconds</th><th>Peak PCM</th><th>Play / file</th></tr></thead><tbody>')
        for rel in paths:
            d=data[rel]; name=Path(rel).stem; note=' (intentional silence)' if d['peak']==0 else ''
            rows.append(f'<tr><td>{esc(name+note)}</td><td>{d["frames"]/44100:.2f}</td><td>{d["peak"]}</td><td><button data-track="{esc(rel)}">Play</button> <a href="{esc(rel)}">WAV</a></td></tr>')
        rows.append('</tbody></table>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FM-1 MHAC | Host audition</title>
<style>body{font:16px system-ui,sans-serif;background:#f5f6f7;color:#182331;max-width:900px;margin:auto;padding:20px}h1,h2{line-height:1.2}section{background:white;border:1px solid #ced4da;border-radius:8px;padding:16px;margin:16px 0}button,select,input{font:inherit}button{padding:6px 12px;cursor:pointer}select{max-width:100%;padding:6px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:7px;border-bottom:1px solid #d9dfe4;text-align:left}audio{width:100%;margin:10px 0}a{color:#125b80}.transport{position:sticky;top:0;z-index:2;box-shadow:0 2px 9px #0001}small{color:#46576a}</style>
<h1>FM-1 MHAC — host audition collection</h1><p>34 original stereo PCM fixtures. No normalization, no device connection, no target or listening claim. Start with low system volume. Installation remains HOLD.</p>
<section class="transport"><h2>Transport / A–B comparison</h2><label for="pair">Comparison</label><br><select id="pair">''' + options + '''</select><p id="pairinfo"></p><button id="a">Play A</button> <button id="b">Play B</button> <button id="stop">Stop</button><p id="now" role="status">Nothing playing</p><audio id="player" controls preload="none"></audio><label for="vol">Playback volume</label> <input id="vol" type="range" min="0" max="1" step="0.05" value="0.25"><br><small>One player only. A/B starts from frame zero. Playback gain affects audition only; stored WAV bytes are unchanged.</small></section>
''' + ''.join(rows) + '''<p><a href="manifest.json">Fixture hashes and measurements</a> · <a href="README.md">Reproduction notes</a></p><script>
const pairs=''' + json.dumps(PAIRS) + ''', $=id=>document.getElementById(id), player=$('player');
player.volume=Number($('vol').value); $('vol').oninput=()=>player.volume=Number($('vol').value);
function selected(){return pairs[Number($('pair').value)]}
function info(){const p=selected();$('pairinfo').textContent='A: '+p[1]+' | B: '+p[2]+' | '+(p[3]?'Exact same PCM':'Different PCM')}
let generation=0;
function play(path){const token=++generation;player.pause();player.src=path;player.load();$('now').textContent=path;player.play().catch(e=>{if(token===generation)$('now').textContent='Playback unavailable: '+e.message})}
$('pair').onchange=info; $('a').onclick=()=>play(selected()[1]); $('b').onclick=()=>play(selected()[2]);
$('stop').onclick=()=>{generation++;player.pause();if(Number.isFinite(player.duration))player.currentTime=0;$('now').textContent='Stopped'};
for(const button of document.querySelectorAll('[data-track]'))button.onclick=()=>play(button.dataset.track);info();
</script></html>'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);a=p.parse_args()
    data=collect(a.root)
    (a.root/'manifest.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    (a.root/'index.html').write_text(page(data),encoding='utf-8')
    print(f'PASS: {len(data)} PCM fixtures, {len(PAIRS)} comparison contracts; offline index generated')

if __name__=='__main__':main()
