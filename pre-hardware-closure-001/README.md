# PRE-HARDWARE-CLOSURE-001

Final pre-hardware closure for FM1-MHAC. This mission ends emulator-only feature expansion and hands the programme to physical-device evidence when the owner FM-1 arrives.

## Closure results

- The frozen Phase Debt, Receipt Loom and Scope Weave target ELFs rebuild byte-for-byte from their accepted Draft heads.
- The legacy linear LLVM screen is preserved and is still expected to reject known data as instructions.
- The replacement table/data-aware screen passes all frozen candidates:
  - the common baseline rows at `0x0200225a` / `0x0200225e` are inside a bounded five-entry `tbb` byte table;
  - Scope rows at `0x020014b8`, `0x020014c0`, `0x020014c4` are words inside compiler-labelled `.Ljta0`; the independent direct-object proof binds all five table words to local relocation symbols;
  - Scope `0x020c9d8` is the NUL-terminated printable literal `UNKNOWN FLASH`, with matching source bytes in allocated non-executable rodata.
- No table-aware screen has unresolved unknown rows, RAM-text calls or ROM hits.
- The no-jump-table alternative remains diagnostically strong, including prior exact modeled PCM equivalence, but textual emitted-assembly round-trip identity remains HOLD. The bounded probe found no exact `.s` reassembly route at the pinned pi32v2 LLVM revision; this is not promoted into a new production build rule.
- The hardware-arrival kit is read-only-first and explicitly refuses to treat application-dependent OCT- recovery as independent recovery from a non-booting application.

## Frozen programme state

The virtual development stack is complete enough for the current hardware-free phase: target ELF construction, strict emulator qualification, Windows standalone hosting, VST3/CLAP hosting, browser/WASM hosting and static table/data classification are all qualified.

Physical installation remains **HOLD** pending the actual unit. The next evidence must come from the owner device: unit/flash identity, trustworthy stock backup, independent recovery, physical baseline audio/control behaviour, and an explicit first-install/rollback authorization.

No `.fwsc` or physical installer is produced here. No upstream repository is modified. PRs remain Draft.

## When the FM-1 arrives

Start with `hardware-arrival/README.md` and `collect-arrival.ps1`. Complete Gate A read-only identity first. Do not proceed to an experimental write unless the recovery/backup requirements in Gate B have been independently satisfied.

Until then, feature development is frozen. Pre-arrival changes should be limited to fixing a concrete reproducibility/qualification defect or maintaining read-only evaluation tooling.
