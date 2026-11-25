# FM1-002 — Receipt Loom

Draft/HOLD, 2026-11-25, Refs #3. Second catalogue entry: fictional two-agent acoustic dialogue instrument. Not an installable image.

## Operation

27 keys select rate 0..26, knob 1 fine adjustment, SEL cycles conditions, PLAY starts/stops, HOME stops new events with a bounded tail. MASTER handled by Dinghy. Boot silent. Tick period 12000..6800 frames at 44100 Hz. Two fixed-point triangles per motif; speaker B doubles pitches and reverses stereo emphasis. 2048-frame envelope, 128-frame attack; mute tail <=46.5 ms. Restart/mode change resets fictional world and waits for remaining envelope; rate changes at next tick. Assumes zeroed interleaved Q15 int32 stereo buffer. No heap, network, storage, audio input, MIDI dependency or external action.

| Mode | Cycle |
|---|---|
| Clean | ASK ACK |
| First loss | ASK silence REPAIR ACK |
| Stale bound | ASK REJECT REPAIR ACK |
| Stale latest | ASK ACK (wrong token) |
| Blackout | ASK silence REPAIR silence EXPIRE |

Initiator alternates at terminal events; one pending transaction, one retry; age <=4. Token uint8 wraps, injected stale token toggles low bit. No external receipt queue or arbitrary latency; delayed receipts after wrap could alias. Bound/latest policies are constructed toy alternatives, not representative protocols. ACK is symbolic, not task completion. Creative mapping of actor and event kind to pitch/pan, not token: clean and stale-latest generate identical PCM. No human perception or real communication claim.

## Provenance and host receipt

Read-only MHAC Situated Relay #457, c0db9ebcada623ad466f30ff298df25706e187f7, README and PR metadata: unaccepted synthetic draft. Bound/latest and finite repair inspire original smaller implementation; no source copied. FM1-001 #2 at bb10a746ddc8b2246f2d567bb87d06d388eee979 supplied known panel API and build route. Dinghy pin 92f17b28f2d05f2f78fd1b160b58475d518902c8 GPL-3.0-only with separate component terms; see FM1-001 README for hardware/alternative provenance. No combined distribution, license grant or upstream modifications.

From this folder: gcc -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined verify.c -o verify && ./verify
GCC 14.2 and Clang 17 independently: 2560 transactions (512 per mode), 512 intentionally wrong-token accepts in stale-latest, zero elsewhere; 661500 frames per replay, block partition and mute PASS, peak 2005 (bound 2048), 36 B host state. Freestanding GCC -Os wrapper 808 B text, 36 B bss, no undefined symbols. Host only. WAV 15 s stereo PCM16 44100 Hz, 3 s per condition. SHA256 6efbbf221d5b357153426ab13d1091bae7762b97f6edd17e6c8509e0e4ec5498. Clean and stale-latest raw segment hash both 5b2797497ef14927e866f018ed664a69468de8adff65e7d44f4c893601d4acd4. No actual listening or SPL measurement. Constant-mode tests only.

## Continuation

Local Git DNS failure and no local pi32v2 toolchain. Reuse pinned Dinghy/LLVM 23.1.5-2 route from #2 for actual target compile/link, then panel replay and emulator. Static audit/MMIO HOLD inherited, exact owner board and recovery unknown, rights decision pending. No target execution, package, flashing or merge. Next add transition stress and an audible token witness to contrast the exact alias; keep this candidate rather than starting another.
