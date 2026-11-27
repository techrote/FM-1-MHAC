#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve()

def edit(rel, pairs):
    p = ROOT / rel
    s = p.read_text()
    for old, new in pairs:
        n = s.count(old)
        if n != 1:
            raise SystemExit(f"{rel}: expected one match, got {n}: {old[:80]!r}")
        s = s.replace(old, new)
    p.write_text(s)

edit("crates/fm1-plugin/src/lib.rs", [
("""/// A flash sector the firmware wrote, saved with the project.
#[derive(Clone, Serialize, Deserialize)]
pub struct Sector {""",
"""/// A development-only bare XIP image. This is intentionally distinct from Firmware:
/// it has no update-package semantics and no portable .fm1save export.
#[derive(Clone, Default, Serialize, Deserialize)]
pub struct RawImage {
    pub name: String,
    #[serde(with = "b64")]
    pub image: Arc<Vec<u8>>,
    pub entry: u32,
}

/// A flash sector the firmware wrote, saved with the project.
#[derive(Clone, Serialize, Deserialize)]
pub struct Sector {"""),
("""    #[persist = "flash"]
    pub flash: Mutex<Vec<Sector>>,
""",
"""    #[persist = "flash"]
    pub flash: Mutex<Vec<Sector>>,
    /// Emulator-only bare XIP state. Existing package projects leave this empty.
    #[persist = "raw-xip"]
    pub raw_xip: Mutex<RawImage>,
"""),
("""            flash: Mutex::new(Vec::new()),
            rec: Mutex::new(RecView::default()),""",
"""            flash: Mutex::new(Vec::new()),
            raw_xip: Mutex::new(RawImage::default()),
            rec: Mutex::new(RecView::default()),"""),
])

edit("crates/fm1-plugin/src/engine.rs", [
("""use fm1_soc::{machine, Action, Board};""",
"""use fm1_soc::{machine, Action, Board, XIP_BASE};"""),
("""    Boot { pkg: Arc<Vec<u8>>, sectors: Vec<(u32, Vec<u8>)> },
""",
"""    Boot { pkg: Arc<Vec<u8>>, sectors: Vec<(u32, Vec<u8>)> },
    /// Boot a development-only raw XIP image at an explicit entry. No package/flash metadata.
    BootRaw { image: Arc<Vec<u8>>, entry: u32 },
"""),
("""    Load { firmware: crate::Firmware, sectors: Vec<crate::Sector>, reply: mpsc::Sender<Result<(), String>> },
""",
"""    Load { firmware: crate::Firmware, sectors: Vec<crate::Sector>, reply: mpsc::Sender<Result<(), String>> },
    /// Validate and replace the running machine with an emulator-only raw XIP image.
    LoadRaw { raw: crate::RawImage, reply: mpsc::Sender<Result<(), String>> },
"""),
("""        Ok(Machine { m, key_free: [0; 256], key_last: [false; 256] })
    }

    /// A press""",
"""        Ok(Machine { m, key_free: [0; 256], key_last: [false; 256] })
    }

    fn boot_raw(image: &[u8], entry: u32, mhz: u64, lcd_timed: bool) -> Result<Self, String> {
        const MAX_RAW: usize = 16 << 20;
        if image.is_empty() || image.len() > MAX_RAW {
            return Err("raw XIP image is empty or too large".into());
        }
        let off = entry.checked_sub(XIP_BASE).ok_or("raw XIP entry below XIP base")? as usize;
        if entry & 1 != 0 || off.checked_add(4).is_none_or(|end| end > image.len()) {
            return Err("raw XIP entry is not mapped by the image".into());
        }
        let opts = machine::Options { mhz, jit: true, lcd_timed, sfc: false, ..Default::default() };
        let m = machine::Machine::from_image(image.to_vec(), entry, &opts);
        Ok(Machine { m, key_free: [0; 256], key_last: [false; 256] })
    }

    /// A press"""),
("""fn boot(pkg: &[u8], sectors: &[(u32, Vec<u8>)], mhz: u64, lcd_timed: bool) -> Result<Machine, String> {
    caught(|| Machine::boot(pkg, sectors, mhz, lcd_timed))
}
""",
"""fn boot(pkg: &[u8], sectors: &[(u32, Vec<u8>)], mhz: u64, lcd_timed: bool) -> Result<Machine, String> {
    caught(|| Machine::boot(pkg, sectors, mhz, lcd_timed))
}

fn boot_raw(image: &[u8], entry: u32, mhz: u64, lcd_timed: bool) -> Result<Machine, String> {
    caught(|| Machine::boot_raw(image, entry, mhz, lcd_timed))
}
"""),
("""    let mut active_pkg: Option<Arc<Vec<u8>>> = None;
    let mut pending = Vec::new();""",
"""    let mut active_pkg: Option<Arc<Vec<u8>>> = None;
    let mut active_raw: Option<(Arc<Vec<u8>>, u32)> = None;
    let mut pending = Vec::new();"""),
("""            let (c, prepared, loaded) = match c {
                Cmd::Load { firmware, sectors, reply } => {
                    let sectors: Sectors = sectors.iter().map(|s| (s.at, s.data.to_vec())).collect();
                    match boot(&firmware.pkg, &sectors, params.clock.value().mhz(), lcd_timed) {
                        Ok(next) => (Cmd::Boot { pkg: firmware.pkg.clone(), sectors }, Some(next), Some((firmware, reply))),
                        Err(error) => { let _ = reply.send(Err(error)); continue; }
                    }
                }
                Cmd::Init => {
                    let pkg = params.firmware.lock().unwrap().pkg.clone();
                    if pkg.is_empty() {
                        continue;
                    }
                    let sectors = params.flash.lock().unwrap().iter().map(|s| (s.at, s.data.to_vec())).collect();
                    (Cmd::Boot { pkg, sectors }, None, None)
                }
                other => (other, None, None),
            };""",
"""            let (c, prepared, loaded, loaded_raw) = match c {
                Cmd::Load { firmware, sectors, reply } => {
                    let sectors: Sectors = sectors.iter().map(|s| (s.at, s.data.to_vec())).collect();
                    match boot(&firmware.pkg, &sectors, params.clock.value().mhz(), lcd_timed) {
                        Ok(next) => (Cmd::Boot { pkg: firmware.pkg.clone(), sectors }, Some(next), Some((firmware, reply)), None),
                        Err(error) => { let _ = reply.send(Err(error)); continue; }
                    }
                }
                Cmd::LoadRaw { raw, reply } => {
                    match boot_raw(&raw.image, raw.entry, params.clock.value().mhz(), lcd_timed) {
                        Ok(next) => (Cmd::BootRaw { image: raw.image.clone(), entry: raw.entry }, Some(next), None, Some((raw, reply))),
                        Err(error) => { let _ = reply.send(Err(error)); continue; }
                    }
                }
                Cmd::Init => {
                    let raw = params.raw_xip.lock().unwrap().clone();
                    if !raw.image.is_empty() {
                        (Cmd::BootRaw { image: raw.image, entry: raw.entry }, None, None, None)
                    } else {
                        let pkg = params.firmware.lock().unwrap().pkg.clone();
                        if pkg.is_empty() { continue; }
                        let sectors = params.flash.lock().unwrap().iter().map(|s| (s.at, s.data.to_vec())).collect();
                        (Cmd::Boot { pkg, sectors }, None, None, None)
                    }
                }
                other => (other, None, None, None),
            };"""),
("""                    active_pkg = m.as_ref().map(|_| pkg);
                    pot = u16::MAX;""",
"""                    active_pkg = m.as_ref().map(|_| pkg);
                    active_raw = None;
                    pot = u16::MAX;"""),
("""                    if let Some((firmware, reply)) = loaded {
                        *params.firmware.lock().unwrap() = firmware;
                        *params.flash.lock().unwrap() = project_sectors(&saved);
                        let _ = reply.send(Ok(()));
                    }
                    // (the frame count goes on: the host's stamps are against it)
                }
                Cmd::Init => unreachable!(),""",
"""                    if let Some((firmware, reply)) = loaded {
                        *params.firmware.lock().unwrap() = firmware;
                        *params.raw_xip.lock().unwrap() = crate::RawImage::default();
                        *params.flash.lock().unwrap() = project_sectors(&saved);
                        let _ = reply.send(Ok(()));
                    }
                    // (the frame count goes on: the host's stamps are against it)
                }
                Cmd::BootRaw { image, entry } => {
                    let runs = prepared.is_none() && active_raw.as_ref().is_some_and(|(a,e)| *e == entry && (Arc::ptr_eq(a, &image) || **a == *image));
                    if runs { continue; }
                    cancel_snapshots(&mut pending);
                    let booted = prepared.map_or_else(|| boot_raw(&image, entry, params.clock.value().mhz(), lcd_timed), Ok);
                    *params.halt.lock().unwrap() = booted.as_ref().err().map(|e| format!("The raw XIP image did not start: {e}"));
                    m = booted.ok();
                    active_pkg = None;
                    active_raw = m.as_ref().map(|_| (image, entry));
                    pot = u16::MAX;
                    let mut v = shared.view.lock().unwrap();
                    v.booted = m.is_some(); v.halted = false; v.speed = 0.0;
                    starved0 = v.starved;
                    speed_t = Instant::now(); speed_ms = 0; busy = Duration::ZERO;
                    v.board = Board::Fm1;
                    drop(v);
                    ctl.reset(&params);
                    saved.clear();
                    due.clear();
                    free = None;
                    if let Some((raw, reply)) = loaded_raw {
                        *params.raw_xip.lock().unwrap() = raw;
                        *params.firmware.lock().unwrap() = crate::Firmware::default();
                        params.flash.lock().unwrap().clear();
                        let _ = reply.send(Ok(()));
                    }
                }
                Cmd::Init => unreachable!(),"""),
("""                Cmd::Load { .. } => unreachable!(), // normalized above, after validation
""",
"""                Cmd::Load { .. } | Cmd::LoadRaw { .. } => unreachable!(), // normalized above, after validation
"""),
("""        if let (Some(mm), Some(pkg)) = (m.as_ref(), active_pkg.as_ref()) {
            if mm.soc.periph.hz != mhz * 1_000_000 && pending.is_empty() {
                let sectors = mm.changed_sectors();
                if let Ok(next) = boot(pkg, &sectors, mhz, lcd_timed) {
                    m = Some(next);
                    *params.halt.lock().unwrap() = None;
                    pot = u16::MAX;
                    due.clear();
                    free = None;
                    ctl.reset(&params);
                    let mut v = shared.view.lock().unwrap();
                    (v.halted, v.speed) = (false, 0.0);
                    starved0 = v.starved;
                    (speed_t, speed_ms, busy) = (Instant::now(), 0, Duration::ZERO);
                }
            }
        }
""",
"""        if let (Some(mm), Some(pkg)) = (m.as_ref(), active_pkg.as_ref()) {
            if mm.soc.periph.hz != mhz * 1_000_000 && pending.is_empty() {
                let sectors = mm.changed_sectors();
                if let Ok(next) = boot(pkg, &sectors, mhz, lcd_timed) {
                    m = Some(next);
                    *params.halt.lock().unwrap() = None;
                    pot = u16::MAX; due.clear(); free = None; ctl.reset(&params);
                    let mut v = shared.view.lock().unwrap();
                    (v.halted, v.speed) = (false, 0.0);
                    starved0 = v.starved;
                    (speed_t, speed_ms, busy) = (Instant::now(), 0, Duration::ZERO);
                }
            }
        } else if let (Some(mm), Some((image, entry))) = (m.as_ref(), active_raw.as_ref()) {
            if mm.soc.periph.hz != mhz * 1_000_000 {
                if let Ok(next) = boot_raw(image, *entry, mhz, lcd_timed) {
                    m = Some(next);
                    *params.halt.lock().unwrap() = None;
                    pot = u16::MAX; due.clear(); free = None; ctl.reset(&params);
                    let mut v = shared.view.lock().unwrap();
                    (v.halted, v.speed) = (false, 0.0);
                    starved0 = v.starved;
                    (speed_t, speed_ms, busy) = (Instant::now(), 0, Duration::ZERO);
                }
            }
        }
"""),
("""                    save_sectors(mm, &mut saved, &params);
""",
"""                    if active_pkg.is_some() { save_sectors(mm, &mut saved, &params); }
"""),
("""            save_sectors(mm, &mut saved, &params);
""",
"""            if active_pkg.is_some() { save_sectors(mm, &mut saved, &params); }
"""),
("""            let name = params.firmware.lock().unwrap().name.clone();
            match crate::wav::Wav::create(if name.is_empty() { "fm1" } else { &name }) {""",
"""            let raw = params.raw_xip.lock().unwrap().clone();
            let name = if raw.image.is_empty() { params.firmware.lock().unwrap().name.clone() } else { raw.name };
            match crate::wav::Wav::create(if name.is_empty() { "fm1" } else { &name }) {"""),
])

edit("crates/fm1-plugin/src/editor.rs", [
("""                let name = params.firmware.lock().unwrap().name.clone();
                let idle = ui.picking.is_none() && ui.job.is_none();""",
"""                let raw = params.raw_xip.lock().unwrap().clone();
                let package_name = params.firmware.lock().unwrap().name.clone();
                let name = if raw.image.is_empty() { package_name.clone() } else { raw.name.clone() };
                let idle = ui.picking.is_none() && ui.job.is_none();"""),
("""                if bar.add_enabled(idle, egui::Button::new("Load firmware / save…"))
                    .on_hover_text("Open a .fwsc firmware package or a shared .fm1save setup").clicked() {
                    ui.picking = Some((FileAction::Load, pick(FileAction::Load, &name)));
                }
                let has_firmware = !params.firmware.lock().unwrap().pkg.is_empty();""",
"""                if bar.add_enabled(idle, egui::Button::new("Load firmware / save…"))
                    .on_hover_text("Open a .fwsc firmware package or a shared .fm1save setup").clicked() {
                    ui.picking = Some((FileAction::Load, pick(FileAction::Load, &name)));
                }
                if bar.add_enabled(idle, egui::Button::new("Load raw XIP…"))
                    .on_hover_text("Development-only: boot a bare .xip.bin image; never creates or exports installable firmware").clicked() {
                    ui.picking = Some((FileAction::LoadRaw, pick(FileAction::LoadRaw, &name)));
                }
                let has_firmware = !params.firmware.lock().unwrap().pkg.is_empty() && raw.image.is_empty();"""),
("""                        ui.msg = if matches!(action, FileAction::Load) { "Loading save…" } else { "Exporting live flash…" }.into();""",
"""                        ui.msg = match action {
                            FileAction::Load => "Loading save…",
                            FileAction::LoadRaw => "Loading emulator-only raw XIP…",
                            FileAction::Export => "Exporting live flash…",
                        }.into();"""),
("""                    "Open a .fwsc firmware or shared .fm1save to start".into()""",
"""                    "Open a .fwsc/.fm1save or development-only raw XIP to start".into()"""),
("""enum FileAction { Load, Export }""",
"""enum FileAction { Load, LoadRaw, Export }"""),
("""            FileAction::Load => dialog
                .add_filter("FM-1 firmware or shared save", &["fwsc", "fm1save", "json"]).pick_file(),
            FileAction::Export =>""",
"""            FileAction::Load => dialog
                .add_filter("FM-1 firmware or shared save", &["fwsc", "fm1save", "json"]).pick_file(),
            FileAction::LoadRaw => dialog
                .add_filter("FM-1 raw XIP development image", &["bin", "xip"]).pick_file(),
            FileAction::Export =>"""),
("""                FileAction::Export => {
                    let firmware = params.firmware.lock().unwrap().clone();""",
"""                FileAction::LoadRaw => {
                    let meta = std::fs::metadata(&path).map_err(|e| e.to_string())?;
                    if meta.len() == 0 || meta.len() > (16 << 20) { return Err("raw XIP image is empty or too large".into()); }
                    let image = std::fs::read(&path).map_err(|e| e.to_string())?;
                    let name = path.file_name().map_or_else(String::new, |s| s.to_string_lossy().into_owned())
                        .trim_end_matches(".bin").trim_end_matches(".xip").to_owned();
                    let raw = crate::RawImage { name: name.clone(), image: Arc::new(image), entry: 0x0200_0120 };
                    let (tx, rx) = std::sync::mpsc::channel();
                    link.cmds.send(Cmd::LoadRaw { raw, reply: tx }).map_err(|_| "the machine stopped".to_owned())?;
                    rx.recv().map_err(|_| "the machine stopped while loading raw XIP".to_owned())??;
                    Ok(format!("Loaded raw XIP {} (emulator only)", name))
                }
                FileAction::Export => {
                    let firmware = params.firmware.lock().unwrap().clone();"""),
("""        let what = match action { FileAction::Load => "Load", FileAction::Export => "Export" };""",
"""        let what = match action { FileAction::Load => "Load", FileAction::LoadRaw => "Load raw XIP", FileAction::Export => "Export" };"""),
])

edit("web/worklet.js", [
("""    const pkg = copy(m.package);
    if (x.fm1_boot_fwsc(pkg, m.package.byteLength, 0, 0, m.mhz) !== 0) {
      throw new Error("not an FM-1 update package (or a DX7 bank it cannot use)");
    }
    if (m.sectors?.byteLength && x.fm1_flash_restore(copy(m.sectors), m.sectors.byteLength) !== 0) {""",
"""    const pkg = copy(m.package);
    if (m.raw) {
      const entry = m.entry ?? 0x02000120;
      x.fm1_boot(pkg, m.package.byteLength, entry, m.mhz);
    } else if (x.fm1_boot_fwsc(pkg, m.package.byteLength, 0, 0, m.mhz) !== 0) {
      throw new Error("not an FM-1 update package (or a DX7 bank it cannot use)");
    }
    if (!m.raw && m.sectors?.byteLength && x.fm1_flash_restore(copy(m.sectors), m.sectors.byteLength) !== 0) {"""),
])

print("raw-XIP patch applied")
