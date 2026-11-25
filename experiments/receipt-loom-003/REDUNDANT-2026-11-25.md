# Receipt Loom — repeated-token alternative (2026-11-25)

Refs #3; Draft PR #4 remains HOLD. Additive variant, not a new installable image. Original ten-mode candidate, exact alias and erasure falsifiers remain unchanged. Creative exaptation and measurement apparatus, not human or empirical validation. Source authority: existing Receipt Loom at 13f8125d71cd6b6c0fcd92305e301e18a26a8f45, inspired by synthetic MHAC Situated Relay #457 at c0db9ebcada623ad466f30ff298df25706e187f7; pinned Dinghy route 92f17b28f2d05f2f78fd1b160b58475d518902c8, GPL-3.0-only plus component terms; no combined distribution.

## Design

Each 2048-frame motif now contains two exactly repeated 1024-frame motifs, each with complete event/actor identity in oscillator 1 and low then high token nibble in oscillator 2. Each half has its own attack/decay, and the weak channel receives 3/4 rather than 1/4 amplitude. Both halves are identical by integer execution, verified for all 2560 identities. Two oscillators, no allocation, integer arithmetic, 44.1 kHz, maximum 2048 sample magnitude per channel, zeroed accumulation buffer required, bounded 2048-frame stop tail (may include the second attack). Same dialogue world and tempo. Separate five-mode panel candidate: SEL cycles conditions, note keys and knob control rate, PLAY start/stop, HOME stop; no device I/O in core.

## Host receipt

GCC 14.2 and Clang 17 with strict warnings and UBSan: 12000 transitions, 6629328 frames, 143464 partitions, 706 mute checks; 40 bytes host state. All 2560 templates rendered with exact repeated halves; identical compiler PCM atlas SHA-256 11f3405d833347260b4e7775e907539674bc63359307d58c6fe191fd951d644e. Demo peak 1985; 15 s native stereo WAV SHA-256 ce4b8ba50722e72eb4f048f184c45b34515a9ff3cef70ae8688323bdc88c0995. No physical audition.

For each of eleven profiles all 3275520 distinct template pairs are certified separated: full, left/right, every fourth stereo frame, each half stereo, each half left/right, first half right every fourth frame (256 retained values, 6.25% of original). First-quarter stereo negative control has exactly 19200 identical pairs, 16 candidates per identity, zero cross-event/actor aliases; do not claim arbitrary-quarter recovery. Certificate uses necessary ratio bounds [1/10,10] and error 32, valid for two independent gains in [1/8,5/4], error <=2 per retained sample, known aligned positions and known template family. No filtering, resampling, unknown time alignment, or arbitrary erasure guarantee.

Reproduce: cc -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined -fno-sanitize-recover=all redundant_probe.c -o probe; ./probe; ./probe atlas > atlas.pcm; cc -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined -fno-sanitize-recover=all redundant_screen.c -o screen; ./screen atlas.pcm

## Target gate

Prior exact-head run 45684668108 job 139454067288: target compilation/link and original modeled panel step succeeded, inherited static screen failed. New redundant panel source and CI compilation/link configured, not yet executed at this checkpoint. Local Git DNS failure prevents local checkout/target execution. No changes to upstream, Phase Debt, CYDaux or central MHAC. No flashable binary. Next: recover exact-head build result, apply original strict emulator harness to the new variant with an erasure-aware inverse decoder; retain physical board/recovery/distribution HOLD. No merge.
