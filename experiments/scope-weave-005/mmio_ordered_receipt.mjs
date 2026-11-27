// Original read-only measurement apparatus for exact workflow run 45790802022/job 139809034148.
// No audit waiver. Not a generic log classifier; execution order is pinned.
import {readFileSync} from "node:fs";
function analyze(log) {
  const sessions=[]; let active;
  for(const line of log.split(/\r?\n/)){
    const s=line.match(/\brequested_steps=\d+.*\bunknown_mmio=(\d+)\b.*\bchanged_flash_sectors=(\d+)\b.*\bresult=(.*)$/);
    if(s){active={reported:Number(s[1]),flash:Number(s[2]),result:s[3].trim(),records:[]};sessions.push(active);continue;}
    if(!line.includes("unknown_mmio UnknownAccess"))continue;
    const m=line.match(/unknown_mmio UnknownAccess \{ addr: (\d+), width: (\d+), is_write: (true|false), value: (\d+) \}\s*$/);
    if(!active||!m)throw Error("malformed/orphan record");
    active.records.push([Number(m[1]),Number(m[2]),m[3]==="true",Number(m[4])]);
  }
  if(sessions.length!==26)throw Error("expected exactly 26 sessions in pinned workflow");
  const A=[65728,4,false,0], R=[262656,4,false,0], W=[262656,4,true,0];
  const pattern=n=>[A,...Array.from({length:n},()=>[R,R,W,R,W]).flat()];
  const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  // Exact execution order from the pinned workflow and its logged calls.
  const activeParts=["puya","puya","puya","puya","puya","puya","uc25hq80","uc25hq80","puya","puya","puya","puya","puya","uc25hq80","puya","puya","puya","puya"];
  const labels=activeParts.map((part,i)=>({part,variant:i<8?"scope":i<14?"context":"policy",phase:"active"}));
  for(const part of ["puya","uc25hq80"])for(const variant of ["baseline","scope","context","policy"])labels.push({part,variant,phase:"boot"});
  const rows=sessions.map((s,i)=>{
    const label=labels[i],groups=(label.part==="puya"?3:4)+(label.variant==="baseline"?2:0);
    if(s.reported!==s.records.length||s.flash!==0||s.result!=="Ok(())")throw Error(`incomplete or failed session ${i}`);
    if(!equal(s.records,pattern(groups)))throw Error(`unexpected tuple or ordering in session ${i}`);
    return {...label,groups,accesses:s.reported};
  });
  return {sessions:rows.length,accesses:rows.reduce((n,x)=>n+x.accesses,0),active:rows.slice(0,18),boot:rows.slice(18),disposition:"HOLD: source-consistent pattern only, not PC attribution or register safety"};
}
function tests(){
  const A="unknown_mmio UnknownAccess { addr: 65728, width: 4, is_write: false, value: 0 }\n";
  const R=A.replace("65728","262656"), W=R.replace("false","true");
  const sample=n=>`requested_steps=1 unknown_mmio=${1+5*n} changed_flash_sectors=0 result=Ok(())\n`+A+(R+R+W+R+W).repeat(n);
  const groups=[3,3,3,3,3,3,4,4,3,3,3,3,3,4,3,3,3,3,5,3,3,3,6,4,4,4];
  const log=groups.map(sample).join("");
  if(analyze(log).accesses!==471)throw Error("positive fixture failed");
  const controls=[log.replace(A,""),log.replace("65728","65729"),log.replace("width: 4","width: 2"),log.replace("value: 0","value: 1"),log.replace(R+R+W,W+R+R),log.replace("changed_flash_sectors=0","changed_flash_sectors=1"),log.replace("result=Ok(())","result=Err(test)"),log+sample(3)];
  for(const [i,bad] of controls.entries()){let rejected=false;try{analyze(bad)}catch{rejected=true}if(!rejected)throw Error(`negative ${i} accepted`);}
  return "9/9 synthetic controls PASS";
}
if(process.argv[2]==="--selftest")console.log(tests());
else {if(!process.argv[2])throw Error("usage: node mmio_ordered_receipt.mjs JOB.log | --selftest");console.log(JSON.stringify(analyze(readFileSync(process.argv[2],"utf8")),null,2));}
