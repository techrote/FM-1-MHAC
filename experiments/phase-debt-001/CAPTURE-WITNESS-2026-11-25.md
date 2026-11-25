# Capture witness continuation — 2026-11-25

Refs #1, #2. Measurement apparatus, not a human or analogue validation.
Source parent 3820af8dd1b18b28c79a815665fa84e016a08308. Prior exact-head workflow [45632974942](https://github.com/techrote/FM-1-MHAC/actions/runs/45632974942) completed host, target and peripheral steps; independent static audit failed and stays unchanged.

Adds bounded onset search (first nonzero minus 0..8 frames), exact 2205-frame tick lattice, 800-frame isolated templates, exact-zero inter-pulse gaps, and one shared gain interval [1/8,5/4] across both channels and 24 consecutive slots. At most 2 PCM units error within each pulse. Enumerates all positive-anchored cyclic phase sequences for density 7, rejects nonunique fits. Moving-loss silence explicitly remains unidentified. The existing occupancy gate is retained as a prerequisite; no arbitrary-density, asynchronous, filtered or noisy-channel inference.

Native GCC strict UBSan fixture run: 110080 frames per mode, 60-byte core state. Aligned gain interval 3705/3707..3709/3707; staggered and fixed 791/792..793/792; moving silent/unidentified. Twelve gain/shift replays (three transforms x four modes) passed. Three falsifiers rejected: one pulse stereo swap, one pulse half gain, unexpected nonzero gap sample. The first two passed the older occupancy gate. Native fixture source was unchanged. Local lane_witness blob 005a03b5356d3750817ea844dd77dc555bdc6768 and DSP header 2449615c952f196a7b900f854275e14d27cd2540 match the parent repo.

New source SHA256 capture_witness.py 0e7733fb113a4290a742dbce994384d69b4e4ac8e98321799cd87e6c9dd98b49; test_capture_witness.py 3c743d412b7f6fd7652aba199868f900558563df15d53ab2a6b4ee68309a0555.
Run from experiment folder: compile mode_reference.c, execute in disposable folder, then python3 capture_witness.py FOLDER and python3 test_capture_witness.py FOLDER.

CI now calls this analyser against actual emulator captures before deleting disposable data; no raw capture publication. Do not assume emulator gain/quantization fits until exact-head results are inspected. Same-boot positive witness after moving-loss silence remains future work. Native clone DNS blocked, no physical hardware, no packaging, no license decision, no changes to upstream or MHAC main. AI-assisted, independent review outstanding.
