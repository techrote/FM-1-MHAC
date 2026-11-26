# FM1-001 — lane witness continuation (2026-11-25)

Refs #1 / Draft #2. Parent b3fb37c425340c4e24e778149ec2e7ad7367e493. FM1 main 16c698d9e244559064a9a9a22f834d36912bf498; both repositories default main; FM1 AGENTS/RAG absent, MHAC AGENTS/RAG read, issue #1 read. Native checkout DNS failure persists. Earlier provenance, rights, hardware identity and recovery holds unchanged.

## Recovered target evidence

[Run 45621944425, job 139232106125](https://github.com/techrote/FM-1-MHAC/actions/runs/45621944425/job/139232106125) completed. Overall failure remains due to original independent static instruction audit. Strict diagnostic passed eight density-seven panel cases (4 modes x 2 flash models); all four PCM hashes match across models. Aligned 3 occupied slots / peak 1429; staggered 21 / 610; fixed 19 / 610; moving silent. Both models: no observed resets, processor faults or changed modeled flash sectors. Unknown MMIO 16/21 records remains; moving silence not sufficient to prove transport. Earlier host/target compilation and repeat ELF controls retained. These are bare-ELF modeled results, not physical hardware or packaged boot.

## New apparatus: exact lane attribution

Original host-only measurement apparatus for the exact existing core (phase_debt.h blob 2449615c952f196a7b900f854275e14d27cd2540). C renderer generates each of 256 isolated masks via actual pd_render after explicitly preparing the residue bank; Python independently computes every sample using oscillator and envelope equations. No new firmware synthesis code, no physical input assumed.

Observation contract: 800 sample-aligned stereo frames, unchanged oscillator phase and envelope, one constant positive gain g in [1/8,5/4], additive error at most 2 integer PCM units per sample; no overlapping pulses. For each side and each of 16 subsets, intersect all linear gain intervals |y_i-g*x_i|<=2 using exact rational arithmetic. Combine left/right only if their intervals intersect. Return every compatible mask; do not force a label. A full channel mute can masquerade as a different valid mask (255 becomes 85). Silence cannot distinguish no events from stopped transport or disconnected output.

Finite separation certificate: if two distinct templates x,z fit one observation with gains a,b, then |x-(b/a)z|<=4/a<=32 and b/a in [1/10,10]. Exhaustively refuting this relaxed necessary condition for all 240 unordered channel-template pairs proves disjointness for every admissible gain and arbitrary error bounded by 2, not merely the sampled gain tests. Distinct stereo masks differ on at least one side. This is a narrow computational certificate, not robustness to timing, resampling, unknown filters or hardware gain staging.

Independent cyclic oracle enumerates 260 mode/density settings (four modes, 0..64) and canonicalizes the exact mask word over 64 ticks up to rotation. 247 classes; only non-singletons are (aligned,0),(staggered,0),(fixed,0), moving 0..8 (all silent); aligned/staggered 64; fixed/moving 64. Thus 244 settings are unique under this ideal complete tick-observation contract. The earlier occupancy-only aliases at density 7 are separated by full mask words. Does not imply general PCM decoding from arbitrary streaming windows.

## Reproduction and native receipt

Run in this folder:
    cc -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined lane_reference.c -o /tmp/lane-reference
    /tmp/lane-reference > /tmp/lane-atlas.pcm
    python3 lane_witness.py /tmp/lane-atlas.pcm

GCC Debian 14.2.0-19 and Clang 17.0.0 UBSan compiled independently, generated identical 819200-byte PCM atlases. Native Python 3.13.5 matched all 256 masks sample-for-sample, 1024 gain-case decodes, 240 pairwise separation refutations, 5 negative refusals, 1 preserved channel-mute alias, 247 cyclic classes. Atlas SHA256 10d3bcaf23ad7a1c900655d0fc0976232db8dd3b1078d1a2221461dba0bb8946. Native source blobs lane_reference.c babaffbd94dd398c5f4396cedf241540d570c989 and lane_witness.py 005a03b5356d3750817ea844dd77dc555bdc6768. No upstream data, audio or combined binary distributed. Existing CI remains unchanged; new tests executed standalone, not an emulator lane attribution claim.

Next: establish sample alignment and actual gain/error contract from retained modeled DAC PCM; run matcher as diagnostic, not relaxed gate. Add same-boot positive witness after moving-loss. Keep static audit, MMIO, physical revision/recovery and licensing HOLD. No package/flash/merge.
