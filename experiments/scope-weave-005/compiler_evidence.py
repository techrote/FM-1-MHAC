#!/usr/bin/env python3
"""Diagnostic compiler-assembly round trip. Never waive the original audit."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PIN = '92f17b28f2d05f2f78fd1b160b58475d518902c8'
TOOL = 'cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990'
ELFS = {'baseline': '22d4f466f4571b5f619d960a12b2a33732c8ad2ee8873f23d18669f39ce74a9e',
        'candidate': '4a5bd10a5bd5cb93e9bbe73db83051738b9f9b01b9961d05c70f43a889c25fac'}
DATA = re.compile(r'^\.(byte|short|2byte|word|long|4byte)\s+(.+)$')
WIDTH = {'byte': 1, 'short': 2, '2byte': 2, 'word': 4, 'long': 4, '4byte': 4}
LABEL = re.compile(r'^[.$\w]+:$')
ALIGN = re.compile(r'^\.(?:p2align|balign|align)\b')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(assembly):
    # Clang textual output: comments do not enter directive operands.
    return [s.split('//', 1)[0].split('#', 1)[0].strip()
            for s in assembly.splitlines()]


def block(rows, start):
    """Read only contiguous data directives, labels and optional alignment.

    Stop at executable text or section changes. Report operands only as counts
    and widths; generated assembly itself stays in the disposable directory.
    """
    entries = []
    for row in rows[start:]:
        if not row or LABEL.fullmatch(row) or ALIGN.match(row):
            continue
        m = DATA.fullmatch(row)
        if not m:
            break
        values = [x.strip() for x in m[2].split(',')]
        need(all(values), 'empty data operand')
        entries.extend([WIDTH[m[1]]] * len(values))
    return entries


def classify(assembly, variant):
    rows = lines(assembly)
    if variant == 'baseline':
        blocks = [block(rows, i + 1) for i, row in enumerate(rows)
                  if re.match(r'^tbb\b', row)]
        matches = sum(x == [1] * 5 for x in blocks)
        return {'tbb_sites': len(blocks), 'five_byte_directive_blocks': matches,
                'local_structure_observed': matches > 0}
    need(variant == 'candidate', 'invalid variant')
    labels = [i for i, row in enumerate(rows) if row == '.Ljta0:']
    table = block(rows, labels[0] + 1) if len(labels) == 1 else []
    # A labelled data block and an independent symbolic reference are necessary,
    # but not sufficient to prove dispatch bounds or absence of incoming edges.
    refs = sum(bool(re.search(r'(?<![\w.])\.Ljta0(?![\w.])', row))
               for row in rows if row != '.Ljta0:')
    literal = sum(bool(re.match(r'^\.(?:ascii|asciz|string)\s+"UNKNOWN FLASH(?:\\000|\\0)?"', row))
                  for row in rows)
    return {'table_labels': len(labels), 'table_entry_widths': table,
            'symbolic_references': refs, 'literal_directives': literal,
            'local_structure_observed': len(labels) == 1 and table == [4] * 5 and refs > 0 and literal > 0}


def selftest():
    b = 'tbb [r0]\n.Ltable:\n.byte 1,2,3\n.byte 4,5 # comment\n.p2align 1\nnop\n'
    c = 'r4 = .Ljta0\ngoto r2\n.Ljta0:\n.long .L1,.L2,.L3\n.4byte .L4,.L5\n.L1:\nnop\n.section .rodata\n.asciz "UNKNOWN FLASH"\n'
    cases = [(b, 'baseline', True), (c, 'candidate', True),
             (b.replace('tbb', 'goto'), 'baseline', False),
             (b.replace('.byte 4,5', '.short 4,5'), 'baseline', False),
             (b.replace('.byte 4,5', 'nop\n.byte 4,5'), 'baseline', False),
             (c.replace('.long', '.short'), 'candidate', False),
             (c.replace('r4 = .Ljta0', 'r4 = r0'), 'candidate', False),
             (c.replace('.asciz', 'nop'), 'candidate', False),
             (c.replace('.Ljta0:', '.Ljta0:\n.Ljta0:'), 'candidate', False)]
    for src, kind, expected in cases:
        need(classify(src, kind)['local_structure_observed'] == expected, 'synthetic classification mismatch')
    try:
        block(['.byte 1,,2'], 0)
    except ValueError:
        pass
    else:
        raise ValueError('malformed directive accepted')
    print('compiler_evidence_selftest=10/10 PASS (synthetic)')


def run(up, archive, original, repeat):
    here = Path(__file__).resolve().parent
    up, archive, original, repeat = map(lambda x: Path(x).resolve(), (up, archive, original, repeat))
    def cmd(args, cwd=None):
        return subprocess.check_output([str(a) for a in args], cwd=cwd)
    need(cmd(['git', '-C', up, 'rev-parse', 'HEAD']).decode().strip() == PIN, 'wrong upstream')
    need(not cmd(['git', '-C', up, 'status', '--porcelain']).strip(), 'dirty upstream')
    need(digest(archive) == TOOL, 'wrong compiler archive')
    for name, sha in ELFS.items():
        need(digest(original / (name + '.elf')) == sha == digest(repeat / (name + '.elf')), 'unexpected reference ELF')
    results = []
    with tempfile.TemporaryDirectory(prefix='fm1-compiler-evidence-') as tmp:
        root = Path(tmp)
        src, tool = root/'src', root/'tool'
        src.mkdir(); tool.mkdir()
        subprocess.run(['tar', '-xJf', str(archive), '-C', str(tool), '--strip-components=1'], check=True)
        tar = root/'source.tar'
        tar.write_bytes(cmd(['git', '-C', up, 'archive', '--format=tar', PIN]))
        subprocess.run(['tar', '-xf', str(tar), '-C', str(src)], check=True)
        clang, lld = tool/'bin/clang', tool/'bin/ld.lld'
        target = ['-target', 'pi32v2', '-mcpu=ac791n']
        flags = target + ['-Os', '-ffunction-sections', '-fno-builtin', '-Wall', '-Wno-unused-function',
                          '-Ifirmware/hal', '-Ifirmware/src', '-Ifirmware/gen',
                          '-DAPP_VER="dev"', '-DFELUCCA_ID="FM-1_990"']
        startup = []
        for name in ('firmware/crt0.S', 'firmware/hal/fm1_vec.S', 'firmware/hal/fm1_isr.S'):
            obj = root/(Path(name).stem + '.o')
            cmd([clang, *target, '-c', name, '-o', obj], src)
            startup.append(obj)
        for kind, expected in ELFS.items():
            if kind == 'candidate':
                shutil.copyfile(here/'app.c', src/'firmware/src/dinghy.c')
                shutil.copyfile(here/'scope_weave.h', src/'firmware/src/scope_weave.h')
            asm, obj, elf = (root/(kind + suffix) for suffix in ('.s', '.o', '.elf'))
            cmd([clang, *flags, '-S', 'firmware/src/dinghy.c', '-o', asm], src)
            result = classify(asm.read_text(), kind)
            cmd([clang, *target, '-x', 'assembler', '-c', asm, '-o', obj], src)
            cmd([lld, '--gc-sections', '-e', '_start', '-T', 'firmware/app.ld', *startup, obj, '-o', elf], src)
            actual = digest(elf)
            result.update(variant=kind, assembly_sha256=digest(asm), reassembled_elf_sha256=actual,
                          reference_elf_sha256=expected, exact_elf_match=actual == expected,
                          disposition='HOLD: local compiler evidence only; no complete control-flow proof')
            print('compiler_evidence ' + json.dumps(result, sort_keys=True), flush=True)
            results.append(result)
    need(all(x['exact_elf_match'] and x['local_structure_observed'] for x in results),
         'compiler round-trip or local structure not established; retain HOLD')
    print('compiler_roundtrip_local_structure=PASS; inherited audit unchanged')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('paths', nargs='*')
    p.add_argument('--selftest', action='store_true')
    a = p.parse_args()
    selftest()
    if not a.selftest:
        need(len(a.paths) == 4, 'expected upstream, toolchain archive, first and repeat ELF directories')
        run(*a.paths)
