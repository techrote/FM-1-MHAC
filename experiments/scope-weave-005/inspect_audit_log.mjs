#!/usr/bin/env node
// Diagnostic only. Does not alter audit_elf.py or issue a PASS.
// Usage: node inspect_audit_log.mjs downloaded-github-job.log
// Input: exact workflow job log 139729951983, from run 45766929896.
// Pin: FM-1-MHAC 9ce76fb33a7c661fa09f86d88658b9f60a2f7471.
// Model formula provenance: joakimeriksson/fm1-emu at
// 736aded65c8e2e9d652cf595fca248734483a877, crates/fm1-core/src/lib.rs
// lines 2616-2623, docs/isa-notes.md lines 267-269.
// Source correlation: zvenson/dinghy at 92f17b28f2d05f2f78fd1b160b58475d518902c8,
// firmware/src/kit_backup.h lines 96-144, recovery.c lines 64-66.
// Table padding is inferred, not independently proven. No redistribution of upstream code.
// Exact ELF hashes pin this diagnostic; do not generalize to future builds.
import {readFileSync} from "node:fs";
function inspect(log) {
  const baseline="22d4f466f4571b5f619d960a12b2a33732c8ad2ee8873f23d18669f39ce74a9e";
  const scope="4a5bd10a5bd5cb93e9bbe73db83051738b9f9b01b9961d05c70f43a889c25fac";
  const groups=new Map(); let pending=[];
  for(const line of log.split(/\r?\n/)){
    let i=line.indexOf("audit_triage {");
    if(i>=0){pending.push(JSON.parse(line.slice(i+13)));continue;}
    i=line.indexOf('{"elf":');
    if(i<0)continue;
    const e=JSON.parse(line.slice(i));
    if(e.unknown_lines!==pending.length)throw Error("incomplete diagnostic group");
    const value={e,records:pending};pending=[];
    if(groups.has(e.sha256)&&JSON.stringify(groups.get(e.sha256))!==JSON.stringify(value))throw Error("inconsistent repeated ELF report");
    groups.set(e.sha256,value);
  }
  if(pending.length)throw Error("orphan diagnostic rows");
  function evidence(sha,expected) {
    const g=groups.get(sha); if(!g||g.records.length!==expected)throw Error("missing pinned ELF report");
    const bytes=new Map(), rows=new Map(), labels=new Map();
    for(const r of g.records)for(const line of r.neighborhood){
      const lab=line.match(/^\s*([0-9a-f]+)\s+<([^>]+)>:$/i);
      if(lab){labels.set(parseInt(lab[1],16),lab[2]);continue;}
      const m=line.match(/^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )*[0-9a-f]{2})(?:[ \t]{2,}|\t)(.*)$/i);
      if(!m)continue;
      let a=parseInt(m[1],16);const b=m[2].split(" ").map(x=>parseInt(x,16));
      for(let j=0;j<b.length;j++){if(bytes.has(a+j)&&bytes.get(a+j)!==b[j])throw Error("conflicting bytes");bytes.set(a+j,b[j]);}
      if(rows.has(a)&&rows.get(a)!==m[3].trim())throw Error("conflicting rows");
      rows.set(a,m[3].trim());
    }
    return {g,bytes,rows,labels};
  }
  function need(condition,message){if(!condition)throw Error(message);}
  function take(d,a,n){return Array.from({length:n},(_,i)=>{need(d.bytes.has(a+i),"missing byte at "+(a+i).toString(16));return d.bytes.get(a+i);});}
  function hex(a){return "0x"+a.toString(16);}
  const b=evidence(baseline,2), c=evidence(scope,4);
  const start=0x200225a;
  need(b.rows.get(start-2)==="tbb [r0]"&&b.rows.get(start-6).startsWith("if (r0 > 4)"),"baseline guard/dispatch absent");
  const entries=take(b,start,5), padding=take(b,start+5,1);
  need(padding[0]===0,"unexpected table-adjacent byte");
  const bt=entries.map(v=>start+2*v);
  need(bt.every(v=>v>=start+6&&(v&1)===0),"table target overlaps candidate data");
  const base=0x20014b4, end=base+20;
  need(c.labels.get(base)===".Ljta0"&&c.labels.get(end)===".LBB12_21","candidate table labels absent");
  need(c.rows.get(base-14)==="r4 = "+base&&c.rows.get(base-8)==="r2 = [r4+r2<<2]"&&c.rows.get(base-4)==="goto r2","candidate indirect dispatch absent");
  const at=Array.from({length:5},(_,i)=>take(c,base+4*i,4).reduce((a,v,j)=>a+v*256**j,0));
  need(at.every(v=>v>=0x2000120&&(v&1)===0&&(v<base||v>=end)&&v<0x2000120+c.g.e.section_sizes[".text"]),"candidate table target outside expected bounds");
  const str=take(c,0x200c9d8,14);
  need(String.fromCharCode(...str)==="UNKNOWN FLASH\0","recovery literal mismatch");
  const hits=(d,lo,hi)=>d.g.records.filter(r=>Number(r.address)>=lo&&Number(r.address)+r.raw_hex.length/2<=hi).map(r=>r.address);
  const bh=hits(b,start,start+6), ch=hits(c,base,end);
  need(bh.length===2&&ch.length===3&&c.g.records.some(r=>r.address==="0x200c9d8"&&r.kind==="literal-printable-byte-rendering"),"unaccounted original hit");
  return {disposition:"HOLD; local evidence only, no whole-program reachability proof",baseline:{sha:baseline,table:hex(start),entries,padding,targets:bt.map(hex),hits:bh,target_rows_visible:bt.map(v=>b.rows.has(v)),source_hypothesis:"kit_backup.h bk_handle five-case dispatch"},scope:{sha:scope,table:hex(base),targets:at.map(hex),hits:ch,target_rows_visible:at.map(v=>c.rows.has(v)),literal:"UNKNOWN FLASH",literal_address:"0x200c9d8"},other_elfs:[...groups.values()].filter(g=>![baseline,scope].includes(g.e.sha256)).map(g=>({sha:g.e.sha256,unknown:g.e.unknown_lines}))};
}
const log=readFileSync(process.argv[2],"utf8");
const report=inspect(log);
const mutations=[
 log.replaceAll("tbb [r0]","nop"),
 log.replaceAll("r2 = [r4+r2<<2]","r2 = 0"),
 log.replaceAll("55 4e 4b 4e 4f 57 4e 20","55 4e 4b 4e 4f 57 4e 21"),
 log.replaceAll("03 9d","00 9d"),
 log.replaceAll("audit_triage {","lost {")
];
let rejected=0;
for(const mutant of mutations){try{inspect(mutant)}catch{rejected++;}}
if(rejected!==mutations.length)throw Error("negative control escaped");
console.log(JSON.stringify({report,negative_controls_rejected:rejected},null,2));
