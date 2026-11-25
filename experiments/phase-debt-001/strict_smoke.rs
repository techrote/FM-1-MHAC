// Original host-only FM1-001 diagnostic. No package, device I/O or stock boot fabrication.
use fm1_soc::{machine::{Machine, Options}, Action, FlashPart, XIP_BASE};
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
// Narrow classifier for the exact reproduced baseline, not a global unknown-opcode waiver.
fn table_evidence(image: &[u8]) -> R<()> {
    let off=(0x02002254-XIP_BASE) as usize;
    need(range(image,off,12)? == [0,0xfc,0xea,8,0,1,3,0x9d,0x32,0x46,0x2d,0],
        "baseline table signature changed")?;
    // The pinned emulator implements tbb as byte[next_pc + index], target=next_pc+2*byte.
    // The preceding LLVM disassembly bounds r0 to 0..4.
    let base=0x0200225a;
    for (i,&v) in range(image,off+6,5)?.iter().enumerate() {
        let target=base+2*u32::from(v);
        let t=(target-XIP_BASE) as usize;
        let bytes=range(image,t,6)?;
        let win=bytes.iter().enumerate().fold(0u64,|w,(j,b)|w|((*b as u64)<<(8*j)));
        let decoded=fm1_core::decode_info(win,target);
        println!("table index={i} byte={v:#04x} target={target:#010x} decode={decoded:?}");
        need(target>=0x02002260 && decoded.is_some(),"table target fails decode screen")?;
    }
    println!("TABLE EVIDENCE: guard + tbb + five entries + alignment byte; not a whole-program reachability proof");
    Ok(())
}
fn peak(samples:&[i16])->i32 {
    samples.iter().map(|&x|i32::from(x).abs()).max().unwrap_or(0)
}
fn schedule_key(m:&mut Machine, name:&str, now:u64)->R<()> {
    let id=fm1_soc::periph::key_id(name).ok_or("unknown FM1 panel key")?;
    let p=&mut m.soc.periph;
    let down=p.cycle_of_ms(now+5);
    let up=p.cycle_of_ms(now+105);
    p.script.push_back((down,Action::Key{id,down:true}));
    p.script.push_back((up,Action::Key{id,down:false}));
    println!("scheduled key={name} id={id} down_ms={} up_ms={}",now+5,now+105);
    Ok(())
}
fn run(path: &str, part: FlashPart, budget: u32) -> R<()> {
    let image=map_elf(&fs::read(path).map_err(|e|e.to_string())?)?;
    println!("case={path} part={part:?} requested_cpu0_steps={budget}");
    if path.ends_with("baseline.elf") {
        // Decode windows at the historical anomaly and neighboring halfwords.
        // Static decode is not evidence of execution or instruction boundaries.
        context(&image,0x0200225a); context(&image,0x0200225e);
        table_evidence(&image)?;
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
    let candidate=path.ends_with("candidate.elf");
    let mut phase=0u8;
    let mut since=0u64;
    let mut audio_index=0usize;
    let mut next_log=50u64;
    while requested<budget {
        let n=(budget-requested).min(100_000);
        requested+=n;
        if let Err(e)=m.run(n) {result=Err(e);break}
        if m.soc.resets!=0 || m.soc.emu_cause!=0 || m.soc.dbg_cause!=0 || m.soc.cpu1_fault.is_some() {
            result=Err("observed reset/guard/alignment/core1 fault".into());break
        }
        let now=m.soc.periph.ms();
        let len=m.soc.periph.audio.len();
        if now>=next_log {
            println!("progress ms={now} phase={phase} retired={} resets={} pc={:#010x} audio_halves={} samples={len} lcd_frames={} lcd_on={}",
                m.cpu.insn_count,m.soc.resets,m.cpu.pc,m.soc.periph.audio_halves,m.soc.lcd.frames,m.soc.lcd.display_on);
            next_log=now+50;
        }
        if phase==0 && m.soc.periph.audio_halves>0 && len>0 && m.soc.lcd.frames>0 && m.soc.lcd.display_on {
            println!("peripherals active ms={now}");
            phase=1; since=now; audio_index=len;
        }
        if phase==1 && now-since>=100 {
            need(len>audio_index,"DMA did not advance after peripheral readiness")?;
            if !candidate {phase=5;break}
            need(peak(&m.soc.periph.audio)==0,"candidate boot PCM was not silent")?;
            schedule_key(&mut m,"PLAY",now)?;
            phase=2; since=now; audio_index=len;
        } else if phase==2 && now-since>=300 {
            need(len>audio_index,"DMA did not advance during PLAY")?;
            let pk=peak(&m.soc.periph.audio[audio_index..]);
            println!("play window samples={} peak={pk}",len-audio_index);
            need(pk>0,"PLAY produced no PCM activity")?;
            need(pk<=6400,"candidate PCM exceeds core bound")?;
            schedule_key(&mut m,"HOME",now)?;
            phase=3; since=now;
        } else if phase==3 && now-since>=180 {
            // Allow modeled scanning, release and audio DMA latency; measure a separate tail.
            phase=4; since=now; audio_index=len;
        } else if phase==4 && now-since>=150 {
            need(len>audio_index,"DMA did not advance after HOME")?;
            let pk=peak(&m.soc.periph.audio[audio_index..]);
            println!("mute tail samples={} peak={pk}",len-audio_index);
            need(pk==0,"HOME tail was not silent")?;
            phase=5;break
        }
        if now>=1800 {break}
    }
    if result.is_ok() && phase!=5 {result=Err(format!("progress horizon exhausted phase={phase}"));}
    println!("phase={phase} cpu0_retired_since_reset={} resets={} core1_retired={:?}",
        m.cpu.insn_count,m.soc.resets,m.cpu1.as_ref().map(|c|c.insn_count));
    let a=&m.soc.periph.audio;
    let peak=peak(a);
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
    assert!((1..=250_000_000).contains(&budget));
    if let Err(e)=run(&a[1],part,budget) {eprintln!("SMOKE HOLD: {e}");std::process::exit(1)}
    println!("PERIPHERAL PROGRESS diagnostic passed; bare-image model only, not package boot or physical audition");
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
