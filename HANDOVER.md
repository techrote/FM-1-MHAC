# FM-1-MHAC — Pre-hardware programme handover

**Handover date:** 2026-11-27  
**Repository:** `techrote/FM-1-MHAC`  
**Programme state:** **PRE-HARDWARE DEVELOPMENT FREEZE**  
**Owner hardware:** physical M-VAVE FM-1 not yet available for testing.

This document is the restart point for the next engineer/agent/session. It records the exact frozen source/qualification topology, what is actually proven, what remains blocked on hardware, and the required order of work when the FM-1 arrives.

Do not infer physical-install readiness from emulator, DAW, browser or target-build success.

---

## 1. Current PR topology

The instrument PRs remain independent Drafts from `main`:

| PR | Purpose | Frozen head | State |
|---|---|---|---|
| #2 | Phase Debt | `ff0e6aff91da9af49bbfe45b2af08401b89fafa0` | Draft / frozen |
| #4 | Receipt Loom | `7359337559af4d673038320a0b1eff666c74ef2f` | Draft / frozen |
| #6 | Scope Weave | `b8ce089a770945bd19d03204c536b85dbfced6af` | Draft / frozen |

The qualification stack is intentionally stacked on Scope Weave:

```text
#6 Scope Weave
  └─ #8 EMULATOR-QUALIFICATION-001
       └─ #10 RAW-XIP-VIRTUAL-HOST-001
            └─ #12 PRE-HARDWARE-CLOSURE-001
                 └─ this handover PR
```

Exact qualification heads:

- PR #8: `cc132a43b27c1d9f23bf50bca224567af49e208e`
- PR #10: `d820ad2408a2deb43aeb4c1e2e98696a72d3fe39`
- PR #12: `a7d3ae068cbca172a268fd87b5e23a742ee37364`

Do not collapse, retarget or merge this stack merely to simplify history. The stack is the evidence lineage.

---

## 2. Frozen toolchain and emulator pins

These identities are part of the qualification contract:

- Dinghy source pin:
  `92f17b28f2d05f2f78fd1b160b58475d518902c8`
- pi32v2 LLVM archive SHA-256:
  `cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990`
- fm1-emu qualification pin:
  `736aded65c8e2e9d652cf595fca248734483a877`

Do not silently update any of these and continue to cite the old evidence. A new pin requires a new qualification run and explicit comparison.

---

## 3. Frozen target identities

Original jump-table candidate ELF SHA-256:

- Phase Debt:
  `0055c9cf1e7cd1d2299963bfabca687bbe34b1bbd574eda9079a1f3b63abe9fe`
- Receipt Loom:
  `b5039aab60cf05cfad1424722d0ba60f94abcce8c645cea243a924d6cf291596`
- Scope Weave:
  `4a5bd10a5bd5cb93e9bbe73db83051738b9f9b01b9961d05c70f43a889c25fac`
- common Dinghy baseline:
  `22d4f466f4571b5f619d960a12b2a33732c8ad2ee8873f23d18669f39ce74a9e`

Emulator-only raw XIP SHA-256:

- Phase Debt:
  `ce1590987ebf8cf1024dab72c31a7978e75903009a08b3169c03518f7efb9141`
- Receipt Loom:
  `26c58a534249a90407f28a00571a6c313752a2ef01791222578aa05fec2ecd54`
- Scope Weave:
  `60fa8c6d003c15ea9bbeeb4adc2800b3a896dbc597a1b748d0f2cd747832323e`

The raw XIP files are **emulator development images**, not installable FM-1 firmware packages.

---

## 4. What is qualified

### Target construction

For the frozen instrument heads:

- pi32v2 target compilation passes;
- linked ELF32 pi32v2 output has no undefined symbols;
- independent rebuilds reproduce exact ELF identity;
- pinned source MMIO screen passes;
- the planted MMIO negative control is detected.

This is target-construction evidence, not hardware execution evidence.

### Table/data-aware static qualification

The original linear `llvm-objdump -d` screen remains preserved as an expected-fail regression witness because it decodes data embedded in executable sections as instructions.

PRE-HARDWARE-CLOSURE-001 adds the accepted structural screen:

- common baseline rows `0x0200225a` / `0x0200225e` are inside the bounded five-entry inline `tbb` byte table following the `r0 > 4` guard;
- Scope rows `0x020014b8`, `0x020014c0`, `0x020014c4` are words within compiler-labelled `.Ljta0`;
- the five `.Ljta0` values resolve to local `.text` targets:
  - `0x02001394`
  - `0x020014c8`
  - `0x020013c8`
  - `0x020014cc`
  - `0x020014d0`
- Scope `0x020c9d8` is the NUL-terminated printable literal `UNKNOWN FLASH`.

The independent `direct_object.mjs` map/relocation proof binds all five Scope table words to the intended local `.LBB12_*` symbols.

Final structural screen result:

- unresolved unknown rows: **0**
- RAM-text call hits: **0**
- ROM-address hits: **0**

Therefore the original jump-table candidates pass the table/data-aware static gate.

### Emulator qualification

PR #8 established the pinned fm1-emu environment as the standard pre-hardware FM-1 development/audition platform.

Qualified surfaces include:

- deterministic batch emulator;
- native Windows `fm1-live`;
- Phase Debt;
- Receipt Loom;
- Scope Weave;
- both modeled flash parts where applicable;
- panel/control scripting;
- PCM capture;
- fresh-process execution;
- mute-tail and distinct-mode witnesses.

Final PR #8 run:

- Actions run: `46020470048`
- result: **SUCCESS**
- frozen head: `cc132a43b27c1d9f23bf50bca224567af49e208e`

### Windows standalone performance

Pinned native Windows Scope benchmark:

- 4.5 s emulated at 240 MHz in about 1.73 s wall;
- about 2.59× overall real time;
- about 2.74× steady real time;
- zero starved audio halves;
- about 68 MiB peak working set.

This makes `fm1-live` a practical audition host, not just a qualification oracle.

### VST3 / CLAP raw-XIP host

PR #10 adds a distinct emulator-only raw-XIP path without overloading `.fwsc` or `.fm1save`.

Qualified evidence:

- raw-XIP plugin engine test: PASS;
- upstream plugin library regression: **31/31 PASS**;
- Windows CLAP build: PASS;
- Windows VST3 build: PASS;
- Steinberg VST3 validator: **47/47 PASS**;
- raw-XIP state is separate from package state;
- portable save export remains package-only;
- no installable firmware package is fabricated.

Final PR #10 run:

- Actions run: `46036734273`
- result: **SUCCESS**
- frozen head: `d820ad2408a2deb43aeb4c1e2e98696a72d3fe39`

### Browser/WASM raw-XIP host

The browser evaluator uses the existing WASM raw-image boot path and a local file picker.

Qualified evidence:

- build: PASS;
- raw-XIP execution: PASS;
- Scope benchmark faster than real time in CI;
- no package/update path introduced.

The browser surface still requires owner interactive audition when practical; CI cannot substitute for browser gesture/audio-device behaviour on the owner's machine.

---

## 5. No-jump-table diagnostic route

The no-jump-table route remains useful diagnostic evidence but is **not adopted as the production build route**.

Prior evidence:

- zero legacy unknown rows;
- independent repeat builds exact;
- 18/18 existing modeled Scope/context/policy cases pass;
- 13,526,016 PCM bytes per comparison arm match;
- paired timing/edit/witness receipts match;
- no first PCM differences.

Direct no-JT identities remain reproducible:

- baseline object:
  `8211bfa04e537294b42067c9b773dd14697714f79552370fdfd803397a6b69e3`
- baseline ELF:
  `5dd622e2af4bfaffd78f9621392a646c828c5e421b93e74aa41cd3fb9e6b943d`
- Scope object:
  `ea94170826dce664018a4ffe721e9dc8af66be6741a0b5c3d091bbdc276cef86`
- Scope ELF:
  `90e098ef48f757e40f1828efd62a5c6014e9d84451b54fa983aee5325e8e0eeb`

However, emitted textual assembly does not round-trip to identical object/ELF bytes.

PRE-HARDWARE-CLOSURE-001 bounded the investigation:

- reassembly uses `cc1as`;
- C/codegen options are unused for assembly input;
- tested assembler-specific relaxation controls are unsupported or remain non-exact;
- no exact textual route was found.

Disposition: **BOUNDED HOLD / diagnostic only**.

Do not spend additional pre-hardware cycles trying to force textual identity at this pinned toolchain unless new external evidence changes the problem.

This HOLD does **not** block the original jump-table builds because their table/data-aware static screen is now qualified.

---

## 6. What is explicitly not proven

No physical FM-1 has been tested in this programme yet.

The following remain unproven or blocked:

- exact board revision of the owner's unit;
- exact flash part fitted to the owner's unit;
- actual physical ISR/timing behaviour;
- physical panel/controller fidelity;
- analog output behaviour;
- USB/MIDI behaviour on the owner's unit;
- full-stock-flash backup;
- independent recovery from a non-booting application;
- first experimental installation;
- rollback after an experimental installation;
- installer/update write set on the owner unit;
- broad redistribution/licensing closure.

No emulator result may be used as a substitute for those physical gates.

---

## 7. Recovery position

Do not treat Dinghy's OCT- recovery path as independent recovery from a non-booting application.

Existing research shows that path depends on intact application-side components including startup, RAM flash driver and USB stack.

Likewise, application backup of selected settings/slots is not accepted as proof of a full stock image.

Before any experimental write, require:

1. exact owner-unit identity;
2. trustworthy stock/recovery source for that exact unit;
3. full-flash or equivalently sufficient rollback image captured before experimental writes;
4. SHA-256 and byte count for the backup;
5. a recovery route independently evidenced to work when the experimental application does not boot;
6. a rollback procedure that does not depend on the experimental application booting.

If these cannot be established, stop before flashing.

---

## 8. Hardware-arrival restart procedure

When the FM-1 arrives, resume from:

`pre-hardware-closure-001/hardware-arrival/README.md`

Use:

`pre-hardware-closure-001/hardware-arrival/collect-arrival.ps1`

### Gate A — read-only owner-unit identity

Do not invoke any updater or recovery mode initially.

Collect:

- external unit/revision markings;
- stock firmware/version shown by the unit;
- normal USB enumeration;
- audio/MIDI device enumeration;
- basic stock audio output;
- front-panel control operation;
- hashes of any vendor stock/recovery files.

The collector is read-only and does not send device commands.

### Gate B — backup and independent recovery

Before any firmware write:

- identify the actual flash/board revision through an accepted read-only method;
- capture a sufficient pre-write rollback image;
- prove an independent recovery mechanism;
- document rollback.

If Gate B cannot pass, do not progress to installation.

### Gate C — physical baseline

Before experimental installation, capture repeatable stock evidence:

- audio interface identity;
- sample rate;
- input gain;
- stock line output;
- all 27 note keys;
- SEL/SCL;
- PLAY;
- HOME;
- knob 1;
- MASTER;
- relevant USB/MIDI behaviour.

Physical analog audio should not be expected to hash byte-for-byte against emulator PCM. Compare event order, cadence, mute tails, mode distinctions and gross spectral/amplitude characteristics.

### Gate D — first experimental installation

This is **not authorized by the current repository state**.

After Gates A–C are accepted, create a new owner-only mission specifically for first physical installation.

That mission must re-read:

- the exact chosen instrument source head;
- all current physical evidence;
- stock backup/recovery receipts;
- exact package identity;
- write set;
- rollback plan;
- licensing/distribution boundary.

Do not reuse a previously generated package or convert a raw XIP image into a physical package implicitly.

---

## 9. Candidate selection for first physical work

Do not pre-authorize a candidate in this handover.

When Gate B passes, choose the first physical candidate by:

1. smallest and clearest write surface;
2. strongest existing emulator/control witness;
3. easiest physical behaviour to recognize;
4. easiest immediate rollback;
5. no dependency on unqualified hardware behaviour.

Phase Debt, Receipt Loom and Scope Weave are all frozen and available for comparison; select deliberately at the time of the hardware mission.

---

## 10. Artefact and run custody

Important completed workflow runs:

### EMULATOR-QUALIFICATION-001

- run: `46020470048`
- status: SUCCESS

### RAW-XIP-VIRTUAL-HOST-001

- run: `46036734273`
- status: SUCCESS

Final Windows host artifact from that run:

- artifact ID: `15219465787`
- Actions SHA-256:
  `a6f02a528448cc23290caff8d3f06e20d0a0c1cbdb04dcf28db4fcd18a15ba3a`

Final browser artifact:

- artifact ID: `15218056280`
- Actions SHA-256:
  `bc62af1b556b888bc2d6e1f7df39152e3c2b1414897e24566ae5f28fb7dd91e2`

### PRE-HARDWARE-CLOSURE-001

- run: `46063192323`
- status: SUCCESS
- exact head:
  `a7d3ae068cbca172a268fd87b5e23a742ee37364`
- evidence artifact ID:
  `15228844382`
- Actions SHA-256:
  `b717dba05194b69974370f1d253bc92effb72eb076198260ad5268ef15a989ab`

Artifacts are convenience copies, not the sole evidence source. The checked-in workflows, source pins and exact commit identities are authoritative and must be able to reproduce the evidence after artifact expiry.

---

## 11. Licensing and redistribution boundary

No repository-wide license has been declared.

Relevant boundaries:

- fm1-emu is MIT-licensed;
- Dinghy-derived target material has GPL obligations and retained-notice/source requirements;
- broad redistribution of FM1-MHAC target firmware remains a separate decision.

The virtual-host delivery bundles corresponding source/provenance for the included derived images, but this does not automatically settle the repository's broader publication/licensing policy.

Before any public physical-firmware release, explicitly review licensing, source-offer/notices and any third-party package content.

---

## 12. What scheduled/manual development should do now

Current default is **freeze**, not continued feature generation.

Until hardware arrives, permitted work should be limited to:

- fixing a concrete reproducibility defect;
- maintaining qualification infrastructure;
- preserving buildability against infrastructure changes;
- improving read-only owner evaluation tooling;
- correcting documentation/evidence errors.

Do not:

- add new FM-1 instruments merely because emulator capacity exists;
- add more emulator hosts without a concrete hardware-driven requirement;
- silently change compiler/emulator pins;
- weaken static/recovery gates;
- create `.fwsc` or physical installers;
- flash or simulate owner authorization;
- merge this Draft stack simply to tidy branches.

If scheduled development is re-enabled, its prompt should explicitly respect this freeze and avoid new firmware-feature work until owner hardware evidence exists.

---

## 13. First-session checklist for the successor

At the start of the next substantive FM1-MHAC session:

1. Read this file.
2. Read PR #12 and `pre-hardware-closure-001/READINESS.md`.
3. Confirm PR heads #2/#4/#6/#8/#10/#12 still match this handover.
4. Confirm no scheduled worker has advanced a frozen branch.
5. If hardware is still unavailable: stop unless there is a concrete qualification defect.
6. If hardware has arrived: execute hardware-arrival Gate A only.
7. Do not ask the owner to flash anything until Gate B has passed and the rollback route is explicit.
8. Create a new issue/branch/PR for any physical-install mission rather than modifying the frozen qualification stack.

---

## 14. Programme handover verdict

The pre-hardware software side is intentionally complete enough to stop.

Qualified before hardware:

- deterministic pi32v2 target construction;
- table/data-aware static qualification;
- strict fm1-emu execution;
- Windows standalone audition;
- VST3/CLAP raw-XIP hosting;
- browser/WASM raw-XIP hosting;
- frozen source/provenance identities;
- read-only hardware-arrival tooling.

Still blocked on the physical unit:

- owner-unit identity;
- trustworthy stock backup;
- independent recovery;
- physical timing/control/audio;
- first installation;
- rollback;
- physical-release/licensing decisions.

**Do not resume broad development until physical evidence can change engineering decisions.**
