# FM1-001 continuation: density-seven mode fingerprints

Refs #1 / Draft #2. Parent b72559b1a8a6e0f29fdfa3c809bc29e520b480d2; FM1 main 16c698d9e244559064a9a9a22f834d36912bf498; MHAC main 495a98ca12bae467a507031f04931aa4254b1866. Both default branches main; no release entries in either repository at inspection. FM1 main has no AGENTS/RAG; MHAC AGENTS/RAG read. Existing pins and rights/recovery HOLD in README retained. No upstream assets or code exported.

Recovered [run 45612928463](https://github.com/techrote/FM-1-MHAC/actions/runs/45612928463), job 139200887893: strict diagnostic success, static instruction audit still fails; overall failure. Three modeled DAC captures (Puya, UC25HQ80, repeated Puya) were byte-identical, 32256 stereo frames, peak 1131, six complete 799-frame groups, five onset intervals exactly 2205 frames. PCM SHA256 9e99377dfd3a973a5381fdf086633bac20e0f1d7dd0015854ce5e83609f97004. Unknown MMIO persists; repeat had 16 entries versus 21 in another case despite identical PCM. No physical claims.

New experiment: at density 7, the 64-tick positive-group counts are 7 aligned, 56 staggered, 49 fixed-loss, 0 moving-loss. This counts occupied ticks, not individual voices. Every 24-slot observation anchored on a positive group gives 3 aligned, 21 staggered, or 18/19 fixed groups. The three sets of possible rotated binary signatures are disjoint (3, 7, 49 signatures respectively). Moving is silent but cannot by itself identify mode or exclude volume/transport faults; paired positive controls required. This is not a general density or timbre decoder. The timing analyser admits up to 256 frames of onset drift and 1056-frame pulse group durations; exact event identities are not inferred.

Original C native fixture (actual phase_debt.h blob 2449615c952f196a7b900f854275e14d27cd2540): GCC 14.2 and Clang 17, strict warnings + UBSan, 110080 frames per mode, 60-byte state, all four positive contracts and all 13 negative controls passed in both builds. Hashes match across compilers:
- aligned 5a54986bae75d1cf38c8d1dff8479ca6fcdd897d6ea4e4e19a6ede6d0f32d809, peak 3707, groups 3
- staggered 544ae74e0b0a695a4005867d29bdb1fde86aa8a21c58ce09f3881351d6f863f5, peak 1584, groups 21
- fixed 302f06bca027a0b7adc5269e523adb8e3c482d48027f4e086973153f2be2ef35, peak 1584, groups 19
- moving 72d78b44cb394af6ffc886f25aadc4765a930f29d7f15c230c6343bb4af41657, peak 0.

Reproduce: compile mode_reference.c with cc -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined; run in an empty disposable directory; python3 mode_receipt.py DIR. The binary and raw PCM stay local; optional original WAV is creative audition fixture only. No human study.

New strict harness uses physical N3 (density 7 via app integer mapping) and SCL (Dinghy BTN_SEL=3; emulator key_id maps SCL=3, N3=17 at pinned 736aded65c8e2e9d652cf595fca248734483a877), then PLAY/HOME. Fresh boots per mode; 2050 ms play observation; both flash models. Longer bounded 500M requested steps/4300 ms ceiling for this experiment. Native analyzer validated; target-mode execution pending CI, not claimed. Existing static audit still fails independently. No change to app, DSP, firmware packaging or device recovery. No flash image; owner revision and combined distribution license remain gates. Next: read exact CI logs, address real panel/measurement failures, preserve negative cases, do not relax gate to make green.
