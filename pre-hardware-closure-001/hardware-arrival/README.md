# FM-1 hardware-arrival qualification kit

This kit is the hand-off point from emulator-qualified development to physical-device evidence. It intentionally stops before any firmware installation.

## Gate A — receipt and read-only identity

1. Do **not** run an updater or enter an update/recovery mode yet.
2. Photograph/record the retail label and externally visible revision markings. Do not open the unit merely to satisfy this gate.
3. Power the stock unit normally and record:
   - stock firmware/version shown by the device, if any;
   - whether USB audio/MIDI enumerates;
   - basic stock audio output and all front-panel controls.
4. With the FM-1 connected normally, run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\collect-arrival.ps1 -OutDir .\arrival-evidence
   ```
5. If you have downloaded a vendor stock/recovery package, hash it without opening/running it:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\collect-arrival.ps1 -OutDir .\arrival-evidence -ReferenceFile C:\path\to\stock-package
   ```

The collector is read-only. PnP InstanceId values can contain serial identifiers; redact those before posting evidence publicly.

**Gate A PASS requires:** a coherent owner-unit identity record and ordinary stock operation. It does not establish the flash chip model or recovery capability by itself.

## Gate B — recovery and backup evidence

This is the current physical blocker.

Before any experimental install, establish **independent** recovery/backup evidence for the actual owner unit. Dinghy's documented OCT- path requires intact application startup, RAM flash driver and USB stack; it is therefore not treated here as independent mask-ROM recovery. Its application backup covers selected settings/slots rather than a demonstrated full 1 MiB stock image.

Required before progressing:

- exact stock package/recovery source matched to the owner unit;
- a read-only method, if available, to identify flash/board revision;
- a full-flash or equivalently sufficient rollback image produced **before** experimental writes, with SHA-256 and byte count;
- a recovery mechanism whose ability to recover from a non-booting experimental application is independently evidenced;
- a written rollback procedure that does not depend on the experimental application booting successfully.

If no trustworthy full-backup/independent-recovery route is available, **stop here**. Do not convert emulator success into permission to flash.

## Gate C — physical baseline

After Gate B, but still before experimental installation:

- capture stock line output through the same audio interface that will be used for experimental tests;
- record interface/sample-rate/gain settings;
- exercise all 27 note keys, SEL/SCL, PLAY, HOME, knob 1 and MASTER;
- confirm USB/MIDI behaviour relevant to the intended test;
- record the actual flash identifier only through a previously accepted read-only path.

Physical analog audio is **not** expected to hash byte-for-byte against emulator PCM. Compare event order, cadence, mute-tail behaviour, mode distinctions and gross amplitude/spectral envelopes instead.

## Gate D — first experimental install

Not authorized by this repository state.

When Gates A–C are accepted, create a new owner-only mission for packaging and first installation. That mission must re-read the exact accepted source head, package identity, write set, recovery evidence and rollback plan. Do not reuse an old package or silently promote a bare XIP image.

The first physical candidate should be the smallest/most comprehensively witnessed existing instrument, with one change at a time and immediate rollback verification.

## Expected virtual references

Frozen raw-XIP identities:

- Phase Debt: `ce1590987ebf8cf1024dab72c31a7978e75903009a08b3169c03518f7efb9141`
- Receipt Loom: `26c58a534249a90407f28a00571a6c313752a2ef01791222578aa05fec2ecd54`
- Scope Weave: `60fa8c6d003c15ea9bbeeb4adc2800b3a896dbc597a1b748d0f2cd747832323e`

These are emulator-development images, not physical firmware packages.
