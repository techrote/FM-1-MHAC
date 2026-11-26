#!/usr/bin/env node
// FM1-003 direct-object provenance diagnostic. No audit waiver or packaging.
// Relink map must reproduce the pinned linked ELF byte-for-byte.
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
function need(ok,msg){if(!ok)throw Error(msg)}

function elf(blob){
  const v=new DataView(blob.buffer,blob.byteOffset,blob.byteLength);
  const u16=p=>v.getUint16(p,true),u32=p=>v.getUint32(p,true);
  need(blob.length>=52&&[127,69,76,70,1,1,1].every((x,i)=>blob[i]===x),"ELF32 LE required");
  const off=u32(32),n=u16(48),idx=u16(50);
  need(u16(46)===40&&n>0&&idx>0&&idx<n&&off+n*40<=blob.length,"section table bounds");
  const sections=Array.from({length:n},(_,i)=>{let p=off+i*40;return {i,nameOff:u32(p),type:u32(p+4),flags:u32(p+8),addr:u32(p+12),off:u32(p+16),size:u32(p+20),link:u32(p+24),info:u32(p+28),entsize:u32(p+36)}});
  const bytes=s=>{need(s.type!==8&&s.off+s.size<=blob.length,"file section bounds");return blob.slice(s.off,s.off+s.size)};
  const strings=bytes(sections[idx]);
  for(const s of sections){need(s.nameOff<strings.length,"section name bounds");let e=s.nameOff;while(e<strings.length&&strings[e])e++;need(e<strings.length,"unterminated name");s.name=String.fromCharCode(...strings.slice(s.nameOff,e));if(s.type!==8)bytes(s)}
  function str(s,o){const b=bytes(s);need(o<b.length,"symbol name bounds");let e=o;while(e<b.length&&b[e])e++;need(e<b.length,"unterminated symbol");return String.fromCharCode(...b.slice(o,e))}
  function sym(tab,i){need(tab&&tab.type===2&&tab.entsize===16&&i*16+16<=tab.size&&sections[tab.link]?.type===3,"symbol table bounds");const p=tab.off+i*16;return {name:str(sections[tab.link],u32(p)),value:u32(p+4),section:u16(p+14),type:blob[p+12]&15}}
  function relocs(s){const out=[];for(const r of sections.filter(x=>(x.type===9||x.type===4)&&x.info===s.i)){const len=r.type===4?12:8;need(r.entsize===len&&r.size%len===0,"relocation format");for(let o=0;o<r.size;o+=len){const p=r.off+o,info=u32(p+4),at=u32(p);need(at<s.size,"relocation outside input section");out.push({at,type:info&255,symbol:sym(sections[r.link],info>>>8),addend:r.type===4?v.getInt32(p+8,true):null})}}return out}
  return {type:u16(16),machine:u16(18),sections,bytes,relocs};
}

function mapRows(text,objname){
  const rows=[];
  for(const l of text.split(/\r?\n/)){
    const m=l.match(/^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+(.+):\(([^()]+)\)\s*$/i);
    if(!m)continue;
    const name=m[4].split(/[\\/]/).pop();
    if(name!==objname)continue;
    rows.push({addr:parseInt(m[1],16),size:parseInt(m[3],16),section:m[5]});
  }
  return rows;
}

function contribution(rows,sections,at,size){
  const matches=rows.filter(x=>x.size>0&&x.addr<=at&&at+size<=x.addr+x.size);
  need(matches.length===1,"ambiguous or missing input contribution");
  const m=matches[0],ss=sections.filter(x=>x.name===m.section);
  need(ss.length===1&&ss[0].size===m.size,"input/output size or section mismatch (possible relaxation/merge)");
  return {row:m,section:ss[0],offset:at-m.addr};
}

function equal(a,b){return a.length===b.length&&a.every((x,i)=>x===b[i])}

function occurrences(hay,needle){const out=[];for(let i=0;i+needle.length<=hay.length;i++){if(needle.every((x,j)=>hay[i+j]===x))out.push(i)}return out}

function inspect(kind,obj,linked,rows){
  need(obj.type===1&&linked.type===2&&obj.machine===241&&linked.machine===241,"target identity");
  const text=linked.sections.filter(s=>s.name===".text");need(text.length===1&&(text[0].flags&6)===6,"linked text");
  const take=(addr,n)=>{let s=text[0],o=addr-s.addr;need(o>=0&&o+n<=s.size,"linked address range");return linked.bytes(s).slice(o,o+n)};
  const base=kind==="baseline"?0x200225a:0x20014b4, size=kind==="baseline"?6:20;
  const t=contribution(rows,obj.sections,base,size);
  need((t.section.flags&6)===6,"table is not in executable input section");
  const raw=obj.bytes(t.section).slice(t.offset,t.offset+size), final=take(base,size);
  const rel=obj.relocs(t.section).filter(r=>r.at>=t.offset&&r.at<t.offset+size);
  const report={kind,table_address:base,input_section:t.section.name,input_offset:t.offset,input_size:t.section.size,relocations:rel.map(r=>({offset:r.at-t.offset,type:r.type,symbol:r.symbol.name,symbol_section:r.symbol.section,symbol_value:r.symbol.value,explicit_addend:r.addend})),direct_bytes_equal:equal(raw,final)};
  if(kind==="baseline"){
    need(equal(final,[3,157,50,70,45,0])&&equal(raw,final)&&rel.length===0,"byte table direct object evidence mismatch");
    report.disposition="byte table preserved directly; control flow HOLD";
  }else{
    need(kind==="scope","unknown variant");
    const targets=[0x2001394,0x20014c8,0x20013c8,0x20014cc,0x20014d0];
    const dv=new DataView(final.buffer,final.byteOffset,final.byteLength);
    need(targets.every((x,i)=>dv.getUint32(i*4,true)===x),"linked table target mismatch");
    need(rel.length===5&&[0,4,8,12,16].every(o=>rel.filter(r=>r.at-t.offset===o).length===1),"missing or ambiguous per-word relocation");
    // This establishes placement of relocation sites; no pi32 relocation type semantics assumed.
    report.disposition="five direct-object relocation sites correspond to linked table words; control flow HOLD";
    const literal=take(0x200c9d8,14);
    need(equal(literal,[85,78,75,78,79,87,78,32,70,76,65,83,72,0]),"linked literal mismatch");
    report.literal_nonexec_input_matches=obj.sections.filter(s=>s.type===1&&(s.flags&2)&&!(s.flags&4)).flatMap(s=>occurrences(obj.bytes(s),literal).map(offset=>({section:s.name,offset,flags:s.flags})));
    need(report.literal_nonexec_input_matches.length>0,"no matching allocated non-executable input string");
    report.literal_limit="Matching source bytes only; merged-string placement may require separate proof.";
  }
  return report;
}

function selftest(){
  let n=0;
  const rows=mapRows("     VMA      LMA     Size Align Out     In      Symbol\n  401130   401130       19    16         /tmp/a.o:(.text.f)\n  401150   401150        1    16         /tmp/b.o:(.text.g)\n  4000d4   4000d4        e     1         <internal>:(.rodata)", "a.o");
  need(rows.length===1&&rows[0].size===25&&rows[0].addr===0x401130,"map parsing");n++;
  const sec=[{name:".text.f",size:25}];
  need(contribution(rows,sec,0x401138,6).offset===8,"map offset");n++;
  function reject(f){let rejected=false;try{f()}catch{rejected=true}need(rejected,"negative escaped");n++}
  reject(()=>contribution(rows,sec,0x401148,2));
  reject(()=>contribution([...rows,...rows],sec,0x401138,6));
  reject(()=>contribution(rows,[{name:".text.f",size:24}],0x401138,6));
  reject(()=>contribution(rows,[...sec,...sec],0x401138,6));
  need(equal(occurrences([1,1,1],[1,1]),[0,1]),"overlap occurrence");n++;
  // Synthetic minimal ELF32 object, one PROGBITS section and section names.
  const b=new Uint8Array(256),v=new DataView(b.buffer),w16=(p,x)=>v.setUint16(p,x,true),w32=(p,x)=>v.setUint32(p,x,true);
  b.set([127,69,76,70,1,1,1]);w16(16,1);w16(18,241);w32(32,52);w16(46,40);w16(48,3);w16(50,2);
  [1,1,6,0,220,6,0,0,2,0].forEach((x,i)=>w32(92+4*i,x));
  const names=[0,46,116,101,120,116,0,46,115,104,115,116,114,116,97,98,0];b.set(names,180);
  [7,3,0,0,180,names.length,0,0,1,0].forEach((x,i)=>w32(132+4*i,x));
  b.set([3,157,50,70,45,0],220);
  const e=elf(b);need(e.type===1&&e.machine===241&&e.sections[1].name===".text"&&equal(e.bytes(e.sections[1]),[3,157,50,70,45,0]),"ELF parse");n++;
  reject(()=>elf(b.slice(0,100)));
  const broken=b.slice();new DataView(broken.buffer).setUint32(92+16,255,true);reject(()=>elf(broken));
  const base=0x200225a, s={name:".text",size:6,flags:6,addr:base,i:1,type:1};
  const bytes=Uint8Array.from([3,157,50,70,45,0]),o={type:1,machine:241,sections:[s],bytes:()=>bytes,relocs:()=>[]},l={type:2,machine:241,sections:[s],bytes:()=>bytes};
  const m=[{addr:base,size:6,section:".text"}];
  need(inspect("baseline",o,l,m).direct_bytes_equal,"baseline contract");n++;
  reject(()=>inspect("baseline",{...o,bytes:()=>Uint8Array.from([4,157,50,70,45,0])},l,m));
  reject(()=>inspect("baseline",{...o,relocs:()=>[{at:0,type:1,symbol:{}}]},l,m));
  // Candidate five independent relocation sites and non-executable string.
  const a=0x2001394,arr=new Uint8Array(0xc9d8-0x1394+16),dv=new DataView(arr.buffer),t=0x20014b4-a;
  [0x2001394,0x20014c8,0x20013c8,0x20014cc,0x20014d0].forEach((x,i)=>dv.setUint32(t+4*i,x,true));
  const lit=Uint8Array.from([85,78,75,78,79,87,78,32,70,76,65,83,72,0]);arr.set(lit,0x200c9d8-a);
  const os={name:".text.f",size:20,flags:6,i:1,type:1},rs={name:".rodata.str",size:14,flags:2,i:2,type:1},ls={name:".text",addr:a,size:arr.length,flags:6};
  const rel=Array.from({length:5},(_,i)=>({at:i*4,type:1,symbol:{name:"s",section:1,value:i*2},addend:0}));
  const co={type:1,machine:241,sections:[os,rs],bytes:s=>s===os?new Uint8Array(20):lit,relocs:()=>rel},cl={type:2,machine:241,sections:[ls],bytes:()=>arr},cm=[{addr:0x20014b4,size:20,section:os.name}];
  need(inspect("scope",co,cl,cm).literal_nonexec_input_matches.length===1,"candidate contract");n++;
  reject(()=>inspect("scope",{...co,relocs:()=>rel.slice(1)},cl,cm));
  reject(()=>inspect("scope",{...co,sections:[os,{...rs,flags:6}]},cl,cm));
  return n;
}
console.log("direct_object_selftest="+selftest()+" PASS (synthetic)");
if(process.argv[2]!=="--selftest"){
  const [kind,objectPath,referencePath,relinkedPath,mapPath]=process.argv.slice(2);
  need(["baseline","scope"].includes(kind)&&mapPath,"usage: direct_object.mjs KIND OBJECT REFERENCE_ELF RELINKED_ELF MAP");
  const pins={baseline:"22d4f466f4571b5f619d960a12b2a33732c8ad2ee8873f23d18669f39ce74a9e",scope:"4a5bd10a5bd5cb93e9bbe73db83051738b9f9b01b9961d05c70f43a889c25fac"};
  const o=readFileSync(objectPath),r=readFileSync(referencePath),l=readFileSync(relinkedPath),m=readFileSync(mapPath);
  const sha=b=>createHash("sha256").update(b).digest("hex");
  need(sha(r)===pins[kind]&&equal(r,l),"HOLD: reference or map-enabled relink identity mismatch");
  console.log(JSON.stringify({reference_sha256:sha(r),object_sha256:sha(o),map_sha256:sha(m),...inspect(kind,elf(o),elf(l),mapRows(m.toString("utf8"),objectPath.split(/[\\/]/).pop()))}));
}
