# MMIO census checkpoint — 2026-11-26

Run 45782044589 job 139779600076 passed pinned direct ELF diagnostics for both independent builds: all ten destination rows match ELF bytes, no marker at destinations, recovery literal verified. Original audit failures remain. No artifacts returned.

Pinned emulator 736aded65c8e2e9d652cf595fca248734483a877, crates/fm1-soc/src/lib.rs:61–66, 861–877 exposes the full Vec of UnknownAccess (address, width, direction, value), without issuing PC. Prior full log: 18 sessions, 303 reported, 216 printed. The old harness's take(12) caused truncation. New harness prints every record; no emulator or firmware source changed. Matched boot-only comparison ends 100 modeled ms after audio/display readiness, with candidate silent, no scheduled keys or flash change. Not a matched instruction trace or full workload comparison. Compare exact ordered tuples and counts for four linked variants and both flash models. No harmless classification or waiver. PC attribution requires separate instrumentation at actual issuing instruction, including core identity and bus/DMA origin, not final CPU PC.

Local execution: 11/11 census and matched-boot synthetic controls PASS; census on real previous CI log reproduced truncation. Rust compile/target execution and standalone Node CLI pending CI. No new image, merge, redistribution or physical test.
