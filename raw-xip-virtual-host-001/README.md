# RAW-XIP-VIRTUAL-HOST-001

Development-only virtual hosting for the exact emulator-qualified FM1-MHAC raw XIP images.

## Deliverables

- Windows x64 CLAP and VST3 built from pinned `fm1-emu@736aded65c8e2e9d652cf595fca248734483a877`.
- A distinct **Load raw XIP…** plugin action using `Machine::from_image`; existing `.fwsc` and `.fm1save` paths remain unchanged.
- DAW project persistence for the raw image is kept in a separate `raw-xip` state field.
- Portable `.fm1save` export remains package-only and is disabled while a raw image is active.
- Browser page `raw-xip.html` that loads a local `.xip.bin` through the existing WASM raw boot API and exposes the virtual FM-1 panel.
- Exact Phase Debt, Receipt Loom and Scope Weave raw images rebuilt from their frozen qualified heads.

This work never creates `.fwsc`, updater metadata, a physical flash image or an installation procedure.

## Plugin controls

Open the plugin window and choose **Load raw XIP…**. Select one of the evaluator images. The image boots at `0x02000120`.

The plugin's normal panel, MIDI routing, clock, lead/latency and recording functions remain available. Raw images use blank modeled flash and do not export portable flash saves.

## Browser

Serve the browser artifact over localhost or HTTPS and open `raw-xip.html`. Choose a raw image and press Start. The page uses the same WebAssembly machine and AudioWorklet as upstream, but its boot message explicitly selects raw-image mode.

## Acceptance boundary

This is an emulator-development host only. Virtual-host success does not authorize physical FM-1 installation. PR #8 remains the qualification baseline and all physical-install HOLD gates remain independent.
