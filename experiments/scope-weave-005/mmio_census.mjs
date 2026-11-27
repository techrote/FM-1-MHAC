// Original FM1-003 measurement apparatus. No MMIO allowlist or audit waiver.
import {readFileSync} from "node:fs";
import {join} from "node:path";
function census(log){
 const rows=[];let active=null;
 for(const line of log.split(/\r?\n/)){
  const s=line.match(/\brequested_steps=\d+.*\bunknown_mmio=(\d+)\b/);
  if(s){active={reported:Number(s[1]),records:[]};rows.push(active);continue}
  if(!line.includes("unknown_mmio UnknownAccess"))continue;
  const m=line.match(/unknown_mmio UnknownAccess \{ addr: (\d+), width: (\d+), is_write: (true|false), value: (\d+) \}\s*$/);
  if(!active||!m)throw Error("orphan or malformed access");
  const a=Number(m[1]),w=Number(m[2]),v=Number(m[4]);
  if(a>0xffffffff||v>0xffffffff||![1,2,4].includes(w))throw Error("invalid access");
  active.records.push([a,w,m[3]==="true",v]);
 }
 if(!rows.length)throw Error("no session summaries");
 return rows.map(({reported,records})=>{
  if(!Number.isSafeInteger(reported)||records.length>reported)throw Error("invalid count");
  const counts={};for(const [a,w,b,v] of records){const k=`0x${a.toString(16).padStart(8,"0")}/${w}/${b?"write":"read"}/0x${v.toString(16)}`;counts[k]=(counts[k]||0)+1}
  return {reported,observed:records.length,complete:reported===records.length,counts,records};
 });
}
function compareBoot(logs){
 const keys=["baseline","scope","context","policy"],results={};
 for(const part of ["puya","uc25hq80"]){
  const all=keys.map(k=>{const r=census(logs[`${part}-${k}`]);if(r.length!==1||!r[0].complete)throw Error("incomplete or multiple boot sessions");return r[0]});
  results[part]=Object.fromEntries(keys.map((k,i)=>[k,{reported:all[i].reported,counts:all[i].counts,exact_order_equal_to_baseline:JSON.stringify(all[0].records)===JSON.stringify(all[i].records)}]));
 }
 return {results,disposition:"HOLD: matched readiness endpoint only; no register semantics, instruction attribution or physical safety established"};
}
function selftest(){
 const s=n=>`requested_steps=100 unknown_mmio=${n} result=Ok(())\n`;
 const r=(a=65728,w=4,v=0)=>`unknown_mmio UnknownAccess { addr: ${a}, width: ${w}, is_write: false, value: ${v} }\n`;
 const check=b=>{if(!b)throw Error("selftest failed")};
 const bad=f=>{let reject=false;try{f()}catch{reject=true}check(reject)};
 check(census(s(2)+r()+r())[0].counts["0x000100c0/4/read/0x0"]===2);
 check(!census(s(2)+r())[0].complete);check(census(s(0))[0].complete);check(census(s(1)+r()+s(0)).length===2);
 bad(()=>census(r()));bad(()=>census(s(0)+r()));bad(()=>census(s(1)+r(1,3)));bad(()=>census(s(1)+"unknown_mmio UnknownAccess bad"));
 let logs={};for(const p of ["puya","uc25hq80"])for(const k of ["baseline","scope","context","policy"])logs[`${p}-${k}`]=s(2)+r()+r(262656);
 check(compareBoot(logs).results.puya.scope.exact_order_equal_to_baseline);logs["puya-scope"]=s(2)+r(262656)+r();check(!compareBoot(logs).results.puya.scope.exact_order_equal_to_baseline);
 logs["puya-scope"]=s(2)+r();bad(()=>compareBoot(logs));
 return "11/11 census and matched-boot synthetic controls PASS";
}
if(process.argv[2]==="--selftest") console.log(selftest());
else {const dir=process.argv[2]; if(!dir)throw Error("usage: mmio_census.mjs DIRECTORY | --selftest");const logs={};for(const p of ["puya","uc25hq80"])for(const k of ["baseline","scope","context","policy"])logs[`${p}-${k}`]=readFileSync(join(dir,`${p}-${k}.log`),"utf8");console.log(JSON.stringify(compareBoot(logs)));}
