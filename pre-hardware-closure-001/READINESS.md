# FM1-MHAC pre-hardware readiness ledger

Frozen 2026-11-27 for PRE-HARDWARE-CLOSURE-001. This ledger distinguishes virtual/target evidence from physical-install readiness.

| Area | Evidence lineage | State before hardware | Meaning |
|---|---|---|---|
| Phase Debt source | PR #2 `ff0e6aff91da9af49bbfe45b2af08401b89fafa0` | FROZEN / Draft | No further feature work planned before hardware. |
| Receipt Loom source | PR #4 `7359337559af4d673038320a0b1eff666c74ef2f` | FROZEN / Draft | No further feature work planned before hardware. |
| Scope Weave source | PR #6 `b8ce089a770945bd19d03204c536b85dbfced6af` | FROZEN / Draft | No further feature work planned before hardware. |
| Target compile/link | #2/#4/#6 | PASS | Pinned pi32v2 LLVM builds deterministic ELF32 pi32v2 candidates with no undefined symbols. Not packaging or physical timing. |
| Legacy linear static screen | #2/#4/#6 | EXPECTED FAIL | Linear disassembly interprets inline/computed tables and printable data as instructions. Preserved as a regression witness. |
| Table/data-aware static screen | PRE-HARDWARE-CLOSURE-001 | PASS | All legacy unknown rows are structurally classified as the bounded `tbb` byte table, Scope `.Ljta0` local-target table, or the NUL-terminated `UNKNOWN FLASH` literal. No unresolved rows, RAM-text calls or ROM hits; first/repeat ELFs are exact. |
| No-jump-table alternative | #6 | DIAGNOSTIC PASS / adoption HOLD | Zero unknown rows; 18/18 modeled cases and complete paired PCM receipts match controls. Loaded bytes differ from original candidates. |
| Textual assembly round-trip | #6 + closure probe | BOUNDED HOLD / diagnostic | Direct `-fno-jump-tables -mno-relax-all` object/ELF builds reproduce exact historical hashes. No tested `.s` → `cc1as` route reproduces them; C/codegen options are unused for assembly input and tested assembler-specific relaxation controls are unsupported or non-exact at this pin. This does not block the original jump-table candidates, whose table-aware static screen passes; the no-JT route remains diagnostic only. |
| Strict emulator qualification | PR #8 `cc132a43...` | PASS | Phase Debt, Receipt Loom and Scope Weave execute with panel/LCD/audio witnesses across modeled flash parts. |
| Native Windows virtual host | PR #8 | PASS | `fm1-live` raw-XIP host is practical and faster than real time. |
| VST3/CLAP raw-XIP host | PR #10 `d820ad24...` | PASS | Raw-XIP plugin path, 31/31 regression and Steinberg 47/47 validation pass. |
| Browser/WASM raw-XIP host | PR #10 | PASS | Local raw-XIP picker/AudioWorklet path builds and executes faster than real time in CI. |
| Owner-unit board/flash identity | hardware-arrival kit | BLOCKED ON HARDWARE | Must be observed from the actual unit; emulator model is not evidence of the purchased unit. |
| Independent full stock backup | hardware-arrival kit | BLOCKED ON HARDWARE | No accepted full owner-unit backup exists. Application-level selected-sector backup is insufficient. |
| Independent recovery from non-booting app | #6 recovery research + arrival kit | HOLD | Dinghy OCT- recovery depends on intact application components; independent rescue remains unproven. |
| First-install write set / rollback | future owner-only mission | HOLD | Do not package/flash until identity, backup and independent recovery gates are accepted. |
| Redistribution/licensing | #2/#4/#8/#10 | HOLD FOR BROADER RELEASE | Emulator is MIT; Dinghy-derived target images carry GPL obligations; original FM1-MHAC licensing decision/notice custody remains to be finalized before broad distribution. |
| Physical audio/control/timing | future owner hardware evaluation | BLOCKED ON HARDWARE | No physical audition, ISR timing or controller-fidelity claim. |

## Programme disposition

**PRE-HARDWARE DEVELOPMENT FREEZE:** manual FM1-MHAC feature development should now pause until the FM-1 arrives. New emulator-only instruments or infrastructure should not be added merely because hardware evidence is unavailable.

Permitted pre-arrival maintenance is limited to fixing a concrete qualification defect in this frozen evidence, preserving build reproducibility, or preparing read-only owner evaluation tooling.

When hardware arrives, begin with the read-only arrival kit. Physical installation remains a separate explicit authorization decision.
