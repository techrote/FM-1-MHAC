# EMULATOR-QUALIFICATION-001

Issue #7 / Draft PR #8. This delivery is deliberately **emulator-only**. The included `.xip.bin`
files are bare execution images for fm1-emu/fm1-live; they are not `.fwsc` packages and are not
approved for physical installation.

## Quick start on Windows x64

Open `choose-instrument.cmd`, or run one of the individual launchers:

- `run-phase-debt.cmd`
- `run-receipt-loom.cmd`
- `run-scope-weave.cmd`
- `run-scope-weave-uc25hq80.cmd` to exercise the second modeled flash part

The launcher opens the native `fm1-live` virtual FM-1. Use the on-screen panel directly. MIDI
controllers can also be used through the emulator's normal MIDI mapping support. Close the emulator
window to return to the selector.

Generated qualification WAVs are under `demos\`. They are execution receipts and audition material,
not physical-device recordings.

## Instruments

### Phase Debt

Exact source head: `ff0e6aff91da9af49bbfe45b2af08401b89fafa0`.

- 27 note keys select event density from 0 to 64.
- Knob 1 fine-tunes density.
- SEL cycles ALIGNED / STAGGER / FIXED LOSS / MOVING LOSS.
- PLAY starts/stops; HOME mutes/stops.

### Receipt Loom

Exact source head: `7359337559af4d673038320a0b1eff666c74ef2f`.

- 27 note keys select event rate 0..26.
- Knob 1 fine-tunes rate.
- SEL cycles legacy and token-witness conditions.
- PLAY starts/stops; HOME mutes/stops.

### Scope Weave

Built from the frozen PR #6 qualification parent `b8ce089a770945bd19d03204c536b85dbfced6af`.

- Note keys select one of 27 expressions.
- SCL/SEL changes comparison mode.
- Knob 1 changes rate.
- PLAY starts/stops; HOME mutes/stops.

## What is being qualified

The evaluator uses `joakimeriksson/fm1-emu@736aded65c8e2e9d652cf595fca248734483a877`.
That is also the existing strict qualification pin in PR #6.

The source head observed during this mission is
`69cb1ef46d86a2776112cc9279773ded3ffa293b`. The seven commits from the qualification pin to that
head change only the web/3D presentation layer, so changing the qualification pin would not improve
ISA/SoC/audio fidelity.

The latest published release observed during this mission is v0.5.1 (2026-11-14), which predates the
qualification pin by 218 commits. CI exercises the released Linux batch binary as a historical A/B
comparison, but the Windows evaluator is built from the newer frozen qualification pin.

The Linux qualification separately preserves the inherited physical-install static-audit failure.
It does not turn that result into an emulator gate or suppress it.

## Bare XIP conversion

`elf_to_xip.py` validates an ELF32 little-endian pi32v2 executable, requires the requested entry
point to be covered by a PT_LOAD segment, bounds all initialized segments to the emulator XIP window,
rejects overlap, and fills gaps with 0xff. It creates no flash/update metadata.

`analyze_wav.py` records deterministic WAV hashes plus frame count, peak, RMS, audio activity and
required mute-tail properties.

## DAW and browser boundary

Upstream's Windows plugin supports VST3 and CLAP and is permissively licensed, but its firmware-load
contract is `.fwsc` / `.fm1save`. This mission does **not** manufacture a flashable package just to
make the plugin accept these experiments. A raw-XIP plugin loader is a sensible follow-up.

The WebAssembly core itself has a raw-image boot entry point. The public hosted page, however, is
package/catalog oriented rather than exposing a raw-XIP file picker. A small raw-XIP web adapter is
therefore feasible follow-up work; it is not required for this standalone evaluator.

## Source and licence material

The evaluator bundles:

- exact fm1-emu source at the qualification pin plus its MIT licence;
- exact Dinghy source at `92f17b28f2d05f2f78fd1b160b58475d518902c8` plus GPL-3.0 licence;
- the Scope Weave replacement source/build scripts;
- exact archived FM1-MHAC experiment source for Phase Debt and Receipt Loom.

This is an owner-directed evaluator artifact, not a public firmware release. Before broader
redistribution, explicitly resolve the original FM1-MHAC code licensing/redistribution decision and
retain all applicable corresponding-source and notice obligations.

## Physical-install boundary

The evaluator contains no `.fwsc`, updater, flash writer, stock image, bootloader replacement or
physical-device procedure. Existing physical gates remain separate: static/compiler provenance,
board identity, controller/peripheral fidelity, stock backup/recovery, first-install/rollback and
redistribution rights. Successful virtual execution is not physical installation approval.
