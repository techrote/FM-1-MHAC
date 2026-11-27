# EMULATOR-QUALIFICATION-001

Issue: #7. This directory is deliberately emulator-only.

## Purpose

Turn the existing target-linked FM-1-MHAC experimental image into a bare XIP image that can be run by
`fm1-emu` and `fm1-live` without creating an installable `.fwsc` package. The bare image is for
virtual execution and audition only; it is not a physical-install approval.

Qualification pin: `joakimeriksson/fm1-emu@736aded65c8e2e9d652cf595fca248734483a877`.
The observed upstream source head on 2026-11-27 is
`69cb1ef46d86a2776112cc9279773ded3ffa293b`. The seven intervening commits only change the web/3D
presentation layer, so the qualification pin intentionally remains frozen.

## Windows evaluator

The CI workflow builds the pinned emulator on Windows x64 and packages `fm1-live.exe`,
`fm1-emu.exe`, a non-package Scope Weave XIP image, launchers, exact source/provenance material and
licenses. The evaluator contains no updater, no `.fwsc`, and no physical flashing path.

`run-scope-weave.cmd` opens the virtual FM-1. Scope Weave controls are the firmware's actual panel
controls: note keys choose one of 27 expressions; SCL changes comparison mode; PLAY starts/stops;
HOME mutes; knob 1 changes rate.

## DAW and browser boundary

Upstream's released plugin supports AU/VST3/CLAP, but its normal firmware-loading interface is
package-oriented. This mission does not manufacture a flashable package merely to make the plugin
accept the experimental firmware. Browser internals can boot a raw XIP image, but the public hosted
page exposes firmware packages/URLs rather than a raw-image file picker. Those are integration
follow-ups, not reasons to weaken physical-firmware gates.

## Tools

`elf_to_xip.py` validates an ELF32 little-endian pi32v2 executable, requires the requested entry to
be covered by a PT_LOAD segment, flattens PT_LOAD data into the emulator's 0x02000000 XIP window and
fills gaps with 0xff. It never creates installer metadata.

`analyze_wav.py` records deterministic WAV hashes and basic audio activity/silence properties for
cross-emulator and cross-flash-part comparisons.
