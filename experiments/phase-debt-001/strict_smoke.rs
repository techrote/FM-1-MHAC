// Original host-only FM1-001 diagnostic. No package, device I/O or stock boot fabrication.
use fm1_soc::{machine::{Machine, Options}, FlashPart, XIP_BASE};
use std::{fs, env};

const ENTRY: u32 = 0x02000120;
const END: u32 = ENTRY + 0x8dfbc;
type R<T> = Result<T, String>;
fn range(b: &[u8], o: usize, n: usize) -> R<&[u8]> {
    b.get(o..o.checked_add(n).ok_or("offset overflow")?).ok_or("truncated ELF".into())
}
fn u16at(b: &[u8], o: usize) -> R<u16> {
    Ok(u16::from_le_bytes(range(b,o,2)?.try_into().unwrap()))
}
fn u32at(b: &[u8], o: usize) -> R<u32> {
    Ok(u32::from_le_bytes(range(b,o,4)?.try_into().unwrap()))
}
fn need(c: bool, why: &str) -> R<()> {
    if c { Ok(()) } else { Err(why.into()) }
}
fn map_elf(b: &[u8]) -> R<Vec<u8>> {
    need(range(b,0,7)? == b"\x7fELF\x01\x01\x01", "ELF32 LE required")?;
    need(u16at(b,16)? == 2 && u16at(b,18)? == 241 && u32at(b,24)? == ENTRY,
         "wrong ELF type, machine or entry")?;
    let ph = u32at(b,28)? as usize;
    let count = u16at(b,44)? as usize;
    need(u16at(b,42)? == 32 && count > 0 && count <= 64, "invalid PH table")?;
    range(b,ph,32*count)?;
    let mut image = vec![0xff; (END-XIP_BASE) as usize];
    let mut extents = Vec::new();
    for i in 0..count {
        let h=range(b,ph+32*i,32)?;
        if u32at(h,0)? != 1 { continue }
        let off=u32at(h,4)? as usize;
        let pa=u32at(h,12)?;
        let fs=u32at(h,16)?;
        let ms=u32at(h,20)?;
        if fs == 0 { continue }
        let end=pa.checked_add(fs).ok_or("load overflow")?;
        need(fs<=ms && pa>=ENTRY && end<=END,"initialized load outside XIP")?;
        need(extents.iter().all(|&(a,z)| end<=a || z<=pa),"overlapping loads")?;
        image[(pa-XIP_BASE) as usize..(end-XIP_BASE) as usize]
            .copy_from_slice(range(b,off,fs as usize)?);
        extents.push((pa,end));
    }
    need(extents.iter().any(|&(a,z)| a==ENTRY && z>=ENTRY+4),"entry not mapped")?;
    need(&image[(ENTRY-XIP_BASE) as usize..(ENTRY-XIP_BASE+4) as usize] ==
         [0x04,0x81,0x80,0x00], "unexpected entry stub")?;
    Ok(image)
}
fn context(image: &[u8], pc:u32) {
    for a in (pc-8..=pc+8).step_by(2) {
        let off=(a-XIP_BASE) as usize;
        if let Some(bytes)=image.get(off..off+6) {
            let win=bytes.iter().enumerate().fold(0u64,|w,(i,b)|w|((*b as u64)<<(8*i)));
            println!("decode pc={a:#010x} bytes={bytes:02x?} info={:?} desc={:?}",
                fm1_core::decode_info(win,a),fm1_core::describe(win,a));
        }
    }
}
fn run(path: &str, part: FlashPart, budget: u32) -> R<()> {
    let image=map_elf(&fs::read(path).map_err(|e|e.to_string())?)?;
    println!("case={path} part={part:?} requested_cpu0_steps={budget}");
    if path.ends_with("baseline.elf") {
        // Decode windows at the historical anomaly and neighboring halfwords.
        // Static decode is not evidence of execution or instruction boundaries.
        context(&image,0x0200225a); context(&image,0x0200225e);
    }
    let o=Options {strict:true,lcd_timed:true,jit:false,skip_idle:false,
        flash_part:part,cpu1_survives:false,..Options::default()};
    let mut m=Machine::from_image(image,ENTRY,&o);
    need(m.soc.strict_align && m.soc.lcd_timed && !m.cpu.jit_on &&
         m.cpu.cost_model && m.soc.periph.cycle_ticks==8 &&
         !m.soc.periph.skip_idle && !m.soc.loop_skip.enabled &&
         m.soc.xip_cache.is_some(), "strict option ineffective")?;
    let mut result=Ok(());
    let mut requested=0u32;
    while requested<budget {
        let n=(budget-requested).min(100_000);
        requested+=n;
        if let Err(e)=m.run(n) {result=Err(e);break}
        if m.soc.emu_cause!=0 || m.soc.dbg_cause!=0 || m.soc.cpu1_fault.is_some() {
            result=Err("observed guard/alignment/core1 fault".into());break
        }
    }
    let a=&m.soc.periph.audio;
    let peak=a.iter().map(|&x|i32::from(x).abs()).max().unwrap_or(0);
    println!("requested_steps={requested} pc={:#010x} ticks={} ms={} audio_halves={} samples={} peak={} lcd_frames={} lcd_on={} unknown_mmio={} dbg_cause={:#x} emu_cause={:#x} core1_fault={:?} changed_flash_sectors={} result={result:?}",
        m.cpu.pc,m.soc.periph.cycles,m.soc.periph.ms(),m.soc.periph.audio_halves,a.len(),peak,
        m.soc.lcd.frames,m.soc.lcd.display_on,m.soc.unknown_accesses().len(),m.soc.dbg_cause,
        m.soc.emu_cause,m.soc.cpu1_fault,m.changed_sectors().len());
    for u in m.soc.unknown_accesses().iter().take(12) {println!("unknown_mmio {u:?}")}
    // Reaching the bounded horizon is only a smoke result, not proof of boot/audio.
    result
}
fn main() {
    let a:Vec<_>=env::args().collect();
    if a.len()!=4 {eprintln!("usage: strict_smoke ELF FLASH_PART STEP_BUDGET");std::process::exit(2)}
    let part=FlashPart::parse(&a[2]).expect("known flash part");
    let budget:u32=a[3].parse().expect("integer budget");
    assert!((1..=20_000_000).contains(&budget));
    if let Err(e)=run(&a[1],part,budget) {eprintln!("SMOKE HOLD: {e}");std::process::exit(1)}
    println!("BOUNDED SMOKE horizon returned without detected fault; not a boot or audition pass");
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture()->Vec<u8>{
        let mut b=vec![0u8;120];
        b[..7].copy_from_slice(b"\x7fELF\x01\x01\x01");
        b[16..18].copy_from_slice(&2u16.to_le_bytes());
        b[18..20].copy_from_slice(&241u16.to_le_bytes());
        b[24..28].copy_from_slice(&ENTRY.to_le_bytes());
        b[28..32].copy_from_slice(&52u32.to_le_bytes());
        b[42..44].copy_from_slice(&32u16.to_le_bytes());
        b[44..46].copy_from_slice(&2u16.to_le_bytes());
        for (h,off,pa) in [(52,116,ENTRY),(84,116,ENTRY+8)] {
            for (i,v) in [(0,1u32),(4,off),(12,pa),(16,4),(20,4)] {
                b[h+i..h+i+4].copy_from_slice(&v.to_le_bytes());
            }
        }
        b[116..120].copy_from_slice(&[4,129,128,0]);
        b
    }
    #[test] fn maps_lma_and_preserves_gap(){
        let b=fixture(); let x=map_elf(&b).unwrap(); let o=(ENTRY-XIP_BASE) as usize;
        assert_eq!(&x[o..o+12], &[4,129,128,0,255,255,255,255,4,129,128,0]);
    }
    #[test] fn rejects_malformed(){
        let b=fixture();
        for n in 0..b.len(){assert!(map_elf(&b[..n]).is_err());}
        for (offset,value) in [(64,ENTRY-1),(96,ENTRY),(100,5),(28,u32::MAX),(24,ENTRY+2)] {
            let mut x=b.clone(); x[offset..offset+4].copy_from_slice(&value.to_le_bytes());
            assert!(map_elf(&x).is_err(),"offset {offset}");
        }
    }
}
