# FM1-001 — Phase Debt

Draft/HOLD, 2026-11-25. Refs #1. First catalogue entry: phase-staggered event synthesis, original C11 core and proposed native FM-1 panel app. Not a MIDI controller, not a flashable release.

## Operation and scope

Eight lanes receive one shared increment 0..64 at 20 ticks/s (2205 internal 44100-Hz frames). Each carries into a short triangle pulse, with fixed pitch and alternating left/right pan. PLAY toggles the clock; HOME mutes new events and existing pulses finish within 800 frames (~18.2 ms); SEL cycles aligned, staggered, fixed loss of lane zero, moving loss of the lowest-index emitting lane. Keys select density (lowest=0, highest=64); knob 1 fine-tunes. MASTER is handled by upstream platform. Boot stopped. Screen reports mode, density and transport. No saved state, audio input, network, MIDI control or flash writes by the app. Restart preserves residues, mode change reinitializes them; transitions may suppress a pulse if the previous envelope is still active. Mathematical counts refer to pd_tick, not audible pulses during transitions.

Direct implementation: integer phase-bank identity from [MHAC draft #451](https://github.com/techrote/MachineHumanAudioCybersemiotics/pull/451), head 388500841b5ee2fe54850707b588645573a393ac (unaccepted synthetic research). Original independent C implementation, no upstream MHAC code copied. Creative exaptation: pitch, stereo placement, pulse shape, transport and controls. Not a psychoacoustic or semantic validation. For staggered phases s_j=8j, integer cumulative input C gives total floor(8C/64) since summing the eight carry floors counts crossings of multiples of eight. Fixed missing observations preserve bounded count discrepancy; moving mask can delete every carry when a=8. This is not a broadband SNR guarantee.

## Host replay

From this folder: `cc -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined -o verify verify.c && ./verify`. Outputs phase-debt.wav, 8 s stereo PCM16 44100 Hz; four 2-s segments in order aligned, staggered, fixed loss, moving loss, constant increment 24. No independent normalization. Test also proves the 64-tick a=8 fixed-loss count 56 versus moving-loss count zero by direct execution. Host block partition equality for constant commands (1024 frames vs single-frame calls). 270400 prefix checks cover every pair of alternating increments 0..64 over 64 ticks. No claim that exhaustive arbitrary sequences were tested. Peak bound 6400 per channel from four lanes x 1600; sample arithmetic fits int32. No dynamic allocation, floating point or 64-bit division. No target CPU timing claim.

Receipt: GCC Debian 14.2.0-19, native x86-64 UBSan build, two executions:
```
carry_checks=270400 fixed=56 moving=0 block_invariance=PASS mute=PASS peak=3707 state_bytes=60
SHA256 phase-debt.wav 6da379e5841e8b05f2f9a05bcbacdae7f00343661b93a56c6a4b3635bb5a624c
```
Host freestanding -Os object wrapper: text 615 B, data 0 B, bss 60 B; nm -u empty. This is not target flash/RAM or cycle cost.

## Candidate platform and hardware evidence

Read-only [Dinghy 0.6 exact source](https://github.com/zvenson/dinghy/tree/92f17b28f2d05f2f78fd1b160b58475d518902c8); read README, LICENSE, LICENSING.md, docs/API.md, docs/RULES.md, firmware/src/platform.c and app examples. API: AC791N proprietary pi32v2 target; integer-only guidance, 256 frames per 44.1 kHz ISR (~5.8 ms), zeroed interleaved Q15 stereo buffer, DAC over ALNK0 I2S, USB recording, 27 keys, 14 buttons, 7 encoders, MASTER, 240x240 screen, USB MIDI and TRS MIDI IN. Platform reports 1 MiB flash, 568 KB app code/constants, 96 KB static RAM, 336 KB pool, 24 KB stack. These are platform budget claims, not measured chip capacity. Dinghy reports two flash IDs: Puya 0x856014 and UC25HQ80 0xB36014. Exact owner unit/board revision, stock image, flash chip and recovery compatibility unknown. No SD, microphone, BLE or Wi-Fi assumptions for this app. Some other firmwares offer BLE, not established for this candidate. Secondary community hardware notes disagree about FPU; follow Dinghy integer-only contract.

Dinghy is GPL-3.0-only with notices and separate MIT/OFL/SDK components; its logo is explicitly excluded. No upstream files or assets copied into this repository. No new repository-wide license assigned. Combined derivative distribution must comply with GPL-3.0-only including corresponding source and retained notices; owner license decision for original code and exact third-party audit outstanding. No combined image distributed. Keep vendor SDK terms and original artwork separate.

Read-only alternate leads, live main pins (not qualified build pins):
- [Melodee](https://github.com/keremimo/melodee/tree/165d177a425944f3d30b0b669255a6ed0050c3a5), GPL-3.0-only per README, community reports stable 1.6.1.
- [SLOOP](https://github.com/isod89/sloop-fm1/tree/bac9c05ea7627449405aa10e48da21d75b6c8c56), GPL-3.0 per README.
- [Skiff](https://github.com/illuminus5/skiff/tree/5eab213620248b3af99eeeea30900fc6266128c4), open Felucca derivative, exact component license audit pending.
- [X0X](https://github.com/charlesvestal/fm1-x0x/tree/6515e77d978c23414c80162558532f0b4312dd4f), GPL-3.0-only per README.
- [Vendor FM1 Open V14](https://github.com/m-vave/fm1_open/tree/4c7496daac04a95ff10d1afdcc8f9ead2dbabc41), GPLv3 with SDK linking exception; binary SDK separate terms. Vendor documents Windows toolchain 2.5.3 with manifest verification. Different from stock V16 (vendor download page dates V16 2026-10-21). Do not equate these versions.
- [Vendor downloads](https://www.m-vave.com/appdownload); stock restore package must match unit and backup. [Community emulator](https://github.com/joakimeriksson/fm1-emu) is a future qualification route, not used here.

## Next build gate (no flashing)

Native git ls-remote failed: Could not resolve host github.com. JieLi toolchain absent at ~/.jieli/toolchain. Target build not attempted beyond dependency check. Candidate upstream instructions: Linux x86-64, tools/get_toolchain.sh and AC79NN_SDK_V1.2.1_2023-12-13 tag from JieLi AC79 SDK. Resolve toolchain/SDK hashes and audit terms before build. First reproduce unchanged pinned Dinghy host and target builds. In disposable local checkout only, stage app.c as firmware/src/dinghy.c and phase_debt.h beside it; check actual app contract and host mode. Before packaging, assign unique product identity, name and loader artwork according to upstream MAKE-IT-YOURS.md; preserve OTA and bootguard, no changes to HAL or flash map. Do not release inherited package identity. No physical flashing in this run. Upstream documents OCT- USB rescue and stock return via updater; this is not verified for this candidate/unit. Confirm revision, matching stock package and backup/rollback before any owner audition. Measure ISR worst-case with documented timer; target <2.9 ms budget, then emulate and inspect panel/audio. Add scripted host app UI scenarios and target build receipt in this same PR. No release, no hardware claim.

Repository reconciliation: FM-1-MHAC was empty (GitHub contents 404 explicitly said empty, repository size zero, no open issues). Initialized minimal README at 16c698d9e244559064a9a9a22f834d36912bf498. MHAC main 495a98ca12bae467a507031f04931aa4254b1866, AGENTS/RAG read, #451 open draft. CYDaux README read only. No changes to MHAC, CYDaux or any upstream. AI-assisted, no independent reviewer.
