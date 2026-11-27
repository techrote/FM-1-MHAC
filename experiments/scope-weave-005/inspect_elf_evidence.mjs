#!/usr/bin/env node
// Pinned local ELF evidence only. No output binary, no audit waiver.
// Reproduces table destinations from actual ELF .text, not log-derived bytes.
// Model and source pins: see inspect_audit_log.mjs. No upstream code copied.
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {execFileSync} from "node:child_process";
function inspectText(blob, dis, kind) {
  const need=(x,m)=>{if(!x)throw Error(m)};
  const view=new DataView(blob.buffer,blob.byteOffset,blob.byteLength);
  const u16=p=>view.getUint16(p,true),u32=p=>view.getUint32(p,true);
  const eq=(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i]);
  const ascii=a=>String.fromCharCode(...a);
  need(blob.length>=52&&eq([...blob.slice(0,7)],[127,69,76,70,1,1,1]),"not ELF32 LE");
  need(u16(16)===2&&u16(18)===241&&u32(24)===0x2000120,"unexpected ELF identity fields");
  const sh=u32(32), sz=u16(46), n=u16(48), si=u16(50);
  need(sz===40&&si>0&&si<n&&sh+n*sz<=blob.length,"section table bounds");
  const s=i=>Array.from({length:10},(_,j)=>u32(sh+i*sz+j*4));
  const names=s(si);need(names[1]===3&&names[4]+names[5]<=blob.length,"string table bounds");
  const name=off=>{need(off<names[5],"invalid section name");let p=names[4]+off,e=p;while(e<names[4]+names[5]&&blob[e])e++;need(e<names[4]+names[5],"unterminated section name");return ascii(blob.slice(p,e))};
  const sections=Array.from({length:n},(_,i)=>s(i)).filter(x=>name(x[0])===".text");
  need(sections.length===1,"missing or ambiguous .text");
  const t=sections[0];need(t[1]===1&&(t[2]&6)===6&&t[3]===0x2000120&&t[4]+t[5]<=blob.length,"unexpected .text layout");
  const take=(a,n)=>{need(a>=t[3]&&a+n<=t[3]+t[5],"outside .text");return [...blob.slice(t[4]+a-t[3],t[4]+a-t[3]+n)]};
  const rows=new Map(), labels=new Map();
  for(const line of dis.split(/\r?\n/)){
    const lab=line.match(/^\s*([0-9a-f]+)\s+<([^>]+)>:$/i);if(lab){labels.set(parseInt(lab[1],16),lab[2]);continue;}
    const m=line.match(/^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )*[0-9a-f]{2})(?:[ \t]{2,}|\t)(.*)$/i);
    if(!m)continue;
    const a=parseInt(m[1],16); if(a<t[3]||a>=t[3]+t[5])continue;
    need(!rows.has(a),"duplicate disassembly address");
    rows.set(a,{bytes:m[2].split(" ").map(x=>parseInt(x,16)),payload:m[3].trim()});
  }
  const checkRow=a=>{const x=rows.get(a);need(x&&eq(x.bytes,take(a,x.bytes.length)),"absent or mismatched row at "+a.toString(16));return x};
  const range=(a,n)=>{let p=a;while(p<a+n){const x=checkRow(p);p+=x.bytes.length;}need(p===a+n,"range crosses row boundary")};
  const hex=a=>"0x"+a.toString(16);
  let base,size,targets,hits,literal=null;
  if(kind==="baseline"){
    base=0x200225a;size=6;
    need(checkRow(base-2).payload==="tbb [r0]"&&checkRow(base-6).payload.startsWith("if (r0 > 4)"),"missing bounded byte dispatch");
    const b=take(base,size);need(eq(b,[3,157,50,70,45,0]),"byte table differs from pinned observation");
    targets=b.slice(0,5).map(x=>base+2*x);hits=[base,base+4];
  }else{
    need(kind==="scope","unknown variant");base=0x20014b4;size=20;
    need(labels.get(base)===".Ljta0"&&labels.get(base+size)===".LBB12_21","missing table labels");
    need(checkRow(base-14).payload==="r4 = "+base&&checkRow(base-8).payload==="r2 = [r4+r2<<2]"&&checkRow(base-4).payload==="goto r2","missing indirect dispatch");
    targets=Array.from({length:5},(_,i)=>take(base+4*i,4).reduce((a,v,j)=>a+v*256**j,0));
    need(eq(targets,[0x2001394,0x20014c8,0x20013c8,0x20014cc,0x20014d0]),"absolute table differs from pinned observation");
    hits=[base+4,base+12,base+16];
    const a=0x200c9d8;need(ascii(take(a,14))==="UNKNOWN FLASH\0","literal bytes differ");
    need(checkRow(a).payload==="UNKNOWN"&&checkRow(a+8).bytes.length>=6,"literal disassembly missing");
    literal={address:hex(a),length:14,elf_and_rows_match:true};
  }
  range(base,size);
  need(hits.every(a=>checkRow(a).payload==="<unknown>"),"decoder marker missing");
  const observed=[...rows].filter(([a,x])=>/<unknown>|\bunknown\b/i.test(x.payload)).map(([a])=>a).sort((a,b)=>a-b);
  need(eq(observed,[...hits,...(literal?[0x200c9d8]:[])].sort((a,b)=>a-b)),"unaccounted screening hit");
  const targetRows=targets.map(a=>{
    need(a%2===0&&(a<base||a>=base+size),"target enters candidate data");
    const x=checkRow(a);
    need(x.payload&&!/<unknown>|\bunknown\b/i.test(x.payload),"target not decoded");
    return {address:hex(a),row_bytes:x.bytes.length,elf_match:true,unknown_marker:false,label:labels.has(a)};
  });
  return {kind,table:hex(base),size,targets:targetRows,hits:hits.map(hex),literal,disposition:"HOLD: matching ELF bytes and destination rows are local evidence, not proof of reachability, complete instruction coverage, or hardware safety"};
}
function selftest(){
  let tests=0;
  for(const kind of ["baseline","scope"]){
    const b=new Uint8Array(0xd000+512),v=new DataView(b.buffer),w16=(p,x)=>v.setUint16(p,x,true),w32=(p,x)=>v.setUint32(p,x,true);
    b.set([127,69,76,70,1,1,1]);w16(16,2);w16(18,241);w32(24,0x2000120);w32(32,52);w16(46,40);w16(48,3);w16(50,2);
    const names=[0,46,116,101,120,116,0,46,115,104,115,116,114,116,97,98,0];b.set(names,180);
    [1,1,6,0x2000120,512,0xd000].forEach((x,i)=>w32(92+i*4,x));[7,3,0,0,180,names.length].forEach((x,i)=>w32(132+i*4,x));
    const rows=new Map(),labs=[];
    const row=(a,bytes,payload)=>{b.set(bytes,512+a-0x2000120);rows.set(a,a.toString(16)+": "+bytes.map(x=>x.toString(16).padStart(2,"0")).join(" ")+"\t"+payload)};
    if(kind==="baseline"){
      row(0x2002254,[0,0,0,0],"if (r0 > 4) goto x");row(0x2002258,[0,1],"tbb [r0]");
      row(0x200225a,[3,157],"<unknown>");row(0x200225c,[50,70],"data");row(0x200225e,[45,0],"<unknown>");
      [0x2002260,0x2002394,0x20022be,0x20022e6,0x20022b4].forEach(a=>row(a,[0,0],"nop"));
    }else{
      row(0x20014a6,[0,0],"r4 = "+0x20014b4);row(0x20014ac,[0,0],"r2 = [r4+r2<<2]");row(0x20014b0,[0,0],"goto r2");
      labs.push("020014b4 <.Ljta0>:","020014c8 <.LBB12_21>:");
      [0x2001394,0x20014c8,0x20013c8,0x20014cc,0x20014d0].forEach((a,i)=>{row(0x20014b4+i*4,[a&255,(a>>8)&255],[1,3,4].includes(i)?"<unknown>":"data");row(0x20014b6+i*4,[0,2],"data");row(a,[0,0],"nop")});
      row(0x200c9d8,[85,78,75,78,79,87,78,32],"UNKNOWN");row(0x200c9e0,[70,76,65,83,72,0,0,0],"FLASH.");
    }
    const dis=[...labs,...rows.values()].join("\n");const result=inspectText(b,dis,kind);
    if(result.targets.length!==5)throw Error("wrong fixture result");tests++;
    const bad=b.slice();bad[512+(kind==="baseline"?0x200225a:0x20014b4)-0x2000120]^=1;
    const target=result.targets[0].address.slice(2);
    const controls=[[bad,dis],[b,dis.split("\n").filter(x=>!x.startsWith(target+":")).join("\n")],[b,dis.replace(target+": 00 00",target+": ff 00")],[b,dis.replace(target+": 00 00\tnop",target+": 00 00\t<unknown>")],[b.slice(0,80),dis]];
    for(const [x,y] of controls){let rejected=false;try{inspectText(x,y,kind)}catch{rejected=true}if(!rejected)throw Error("negative control escaped");tests++;}
  }
  return tests;
}
console.log("elf_evidence_selftest="+selftest()+"/12 PASS (synthetic)");
if(process.argv[2]!=="--selftest"){
 const [kind,path,objdump]=process.argv.slice(2);
 const pins={baseline:"22d4f466f4571b5f619d960a12b2a33732c8ad2ee8873f23d18669f39ce74a9e",scope:"4a5bd10a5bd5cb93e9bbe73db83051738b9f9b01b9961d05c70f43a889c25fac"};
 const blob=readFileSync(path);
 const sha=createHash("sha256").update(blob).digest("hex");
 if(sha!==pins[kind])throw Error("HOLD: unexpected ELF digest");
 const dis=execFileSync(objdump,["-d",path],{encoding:"utf8",maxBuffer:16*1024*1024});
 console.log(JSON.stringify({sha,...inspectText(blob,dis,kind)}));
}
