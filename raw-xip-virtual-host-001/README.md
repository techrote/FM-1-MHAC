# RAW-XIP-VIRTUAL-HOST-001

Development-only virtual hosting for the exact emulator-qualified FM1-MHAC raw XIP images.

## Deliverables

- Windows x64 CLAP and VST3 built from pinned `fm1-emu@736aded65c8e2e9d652cf595fca248734483a877`.
- A distinct **Load raw XIP…** plugin action using `Machine::from_image`; existing `.fwsc` and `.fm1save` paths remain unchanged.
- DAW project persistence for the raw image is kept in a separate `raw-xip` state field.
- Portable `.fm1save` export remains package-only and is disabled while a raw image is active.
- Browser page `raw-xip.html` that loads a local `.xip.bin` through the existing WASM raw boot API and exposes the virtual FM-1 panel.
- Exact Phase Debt, Receipt Loom and Scope Weave raw images rebuilt from their frozen qualified heads.

This work never creates `.fwsc`, updater metadata, a physical flash image or a physical-FM-1 installation procedure. Exact corresponding source snapshots and build provenance are bundled with the evaluator artifacts.

## Windows installation and plugin controls

Keep the two plugin formats under their upstream names: the Windows VST3 wrapper locates the companion CLAP by that identity.

Per-user installation without administrator rights:

- copy `FM-1.clap` to `%LOCALAPPDATA%\\Programs\\Common\\CLAP\\FM-1.clap`;
- copy the complete `FM-1.vst3` directory to `%LOCALAPPDATA%\\Programs\\Common\\VST3\\FM-1.vst3`.

A DAW with custom scan paths may instead point at the evaluator folder, but the VST3 must still be able to locate `FM-1.clap` through a normal CLAP location or `CLAP_PATH`.

The Windows binaries are unsigned. They also import `VCRUNTIME140.dll` / UCRT; install the Microsoft Visual C++ 2015–2022 x64 Redistributable if the host does not already provide it.

Open the plugin window and choose **Load raw XIP…**. Select one of the evaluator images. The image boots at `0x02000120`.

The plugin's normal panel, MIDI routing, clock, lead/latency and recording functions remain available. Raw images use blank modeled flash and do not export portable flash saves.

## Browser

Serve the browser artifact over localhost or HTTPS and open `raw-xip.html`. Choose a raw image and press Start. The page uses the same WebAssembly machine and AudioWorklet as upstream, but its boot message explicitly selects raw-image mode.

## Acceptance boundary

This is an emulator-development host only. Virtual-host success does not authorize physical FM-1 installation. PR #8 remains the qualification baseline and all physical-install HOLD gates remain independent.
