// FM1-003 measurement apparatus. Disposable MIT-licensed emulator checkout only.
// joakimeriksson/fm1-emu @ 736aded65c8e2e9d652cf595fca248734483a877.
// Retain upstream LICENSE; do not publish a combined binary or flash a device.
import {readFileSync,writeFileSync} from "node:fs";
import {execFileSync} from "node:child_process";
import {join} from "node:path";
import {pathToFileURL} from "node:url";
const pin="736aded65c8e2e9d652cf595fca248734483a877";
const paths=["crates/fm1-core/src/lib.rs","crates/fm1-soc/src/lib.rs"];
const blobs=["698929b364356557969b87aea619bcbeceef1d52","2ab57f5d9832bed20441b5163acbe09d3a55fdb0"];
function need(ok,msg){if(!ok)throw Error(msg);}
function replace(s,from,to,n=1){
  need(s.split(from).length-1===n,"unexpected anchor count: "+from);
  return s.split(from).join(to);
}
const scope=(pc,call)=>"{ let _mhac = MhacInstructionScope::enter(self.core_id, "+pc+"); "+call+" }";
export function patch(core,soc){
  need(!core.includes("MhacInstructionScope")&&!soc.includes("mhac_origin"),"already instrumented");
  // Non-JIT interpreter only. The nested exec_fast in execute inherits its context.
  need(core.split("self.exec_fast(").length-1===8,"exec_fast count changed");
  need(core.split("self.execute(").length-1===1,"execute count changed");
  const op="self.exec_fast(bus, op.fast, next_pc)";
  core=replace(core,"pc = "+op+".unwrap_or(next_pc);","pc = "+scope("pc",op)+".unwrap_or(next_pc);",2);
  core=replace(core,"let mut pc = "+scope("pc",op),"let mut pc = "+scope("at",op));
  const tail="self.exec_fast(bus, tail, next_pc)",head="self.exec_fast(bus, head, head_next)";
  core=replace(core,tail,scope("head_next",tail));
  core=replace(core,head,scope("self.pc",head));
  const normal="self.exec_fast(bus, f, next_pc)";
  core=replace(core,"            "+normal+"\n","            "+scope("self.pc",normal)+"\n");
  core=replace(core,"let jumped = "+normal+";","let jumped = "+scope("self.pc",normal)+";",2);
  const slow="self.execute(bus, &insn, &x.pre, next_pc)";
  core=replace(core,slow,scope("insn.addr",slow));
  core+=[
    "",
    "thread_local! {",
    "    static MHAC_INSTRUCTION: std::cell::Cell<Option<(u32,u32)>> = const { std::cell::Cell::new(None) };",
    "}",
    "struct MhacInstructionScope(Option<(u32,u32)>);",
    "impl MhacInstructionScope {",
    "    fn enter(core:u32, pc:u32)->Self {",
    "        Self(MHAC_INSTRUCTION.with(|s|s.replace(Some((core,pc)))))",
    "    }",
    "}",
    "impl Drop for MhacInstructionScope {",
    "    fn drop(&mut self) { MHAC_INSTRUCTION.with(|s|s.set(self.0)); }",
    "}",
    "pub fn mhac_instruction_context()->Option<(u32,u32)> {",
    "    MHAC_INSTRUCTION.with(|s|s.get())",
    "}",
    ""
  ].join("\n");
  const anchor="        self.unknown_log.push(UnknownAccess {";
  const added=[
    "        // Active instruction context; synchronous bus effects may share it.",
    "        match fm1_core::mhac_instruction_context() {",
    '            Some((core,pc)) => eprintln!("mhac_origin core={} pc={:#010x} addr={} width={} write={} value={}",core,pc,addr,width,is_write,value),',
    '            None => eprintln!("mhac_origin core=none pc=none addr={} width={} write={} value={}",addr,width,is_write,value),',
    "        }",""
  ].join("\n");
  soc=replace(soc,anchor,added+anchor);
  return [core,soc];
}
function install(dir){
  const git=(...a)=>execFileSync("git",["-C",dir,...a],{encoding:"utf8"}).trim();
  need(git("rev-parse","HEAD")===pin,"wrong emulator pin");
  need(!git("status","--porcelain"),"dirty input checkout");
  paths.forEach((p,i)=>need(git("hash-object",p)===blobs[i],"wrong source blob "+p));
  const out=patch(...paths.map(p=>readFileSync(join(dir,p),"utf8")));
  paths.forEach((p,i)=>writeFileSync(join(dir,p),out[i]));
  need(git("diff","--name-only").split("\n").sort().join("\n")===paths.slice().sort().join("\n"),"unexpected patched paths");
  console.log("origin instrumentation installed in disposable checkout; no register behavior changed");
}
export function compare(control,observed){
  const lines=s=>s.trimEnd().split(/\r?\n/);
  const c=lines(control),o=lines(observed),origins=o.filter(l=>l.startsWith("mhac_origin "));
  need(c.join("\n")===o.filter(l=>!l.startsWith("mhac_origin ")).join("\n"),"instrumentation changed observable harness transcript");
  const summary=c.filter(l=>l.startsWith("requested_steps="));
  need(summary.length===1&&summary[0].endsWith("changed_flash_sectors=0 result=Ok(())"),"failed/nonunique boot summary");
  const count=Number(summary[0].match(/\bunknown_mmio=(\d+)\b/)?.[1]);
  const tuples=c.filter(l=>l.startsWith("unknown_mmio UnknownAccess "));
  need(count>0&&count<8192&&count===tuples.length&&count===origins.length,"incomplete origin census");
  return origins.map((l,i)=>{
    const m=l.match(/^mhac_origin core=(0|1) pc=(0x[0-9a-f]{8}) addr=(\d+) width=(\d+) write=(true|false) value=(\d+)$/);
    need(m,"missing/invalid CPU instruction context: "+l);
    const t=tuples[i].match(/^unknown_mmio UnknownAccess \{ addr: (\d+), width: (\d+), is_write: (true|false), value: (\d+) \}$/);
    need(t&&m.slice(3).join(",")===t.slice(1).join(","),"tuple mismatch at "+i);
    const pc=Number(m[2]);need(pc!==0&&pc%2===0,"invalid PC");
    return {core:Number(m[1]),pc,addr:Number(m[3]),width:Number(m[4]),write:m[5]==="true",value:Number(m[6])};
  });
}
function elfRows(elf,objdump,records){
  const b=readFileSync(elf);
  need(b.length>=52&&b.subarray(0,7).equals(Buffer.from([127,69,76,70,1,1,1]))&&b.readUInt16LE(18)===241,"not target ELF");
  const off=b.readUInt32LE(32),sz=b.readUInt16LE(46),n=b.readUInt16LE(48);
  need(sz===40&&n>0&&off+n*sz<=b.length,"invalid section table");
  const sections=Array.from({length:n},(_,i)=>{
    const s=off+i*sz;return {type:b.readUInt32LE(s+4),flags:b.readUInt32LE(s+8),addr:b.readUInt32LE(s+12),off:b.readUInt32LE(s+16),len:b.readUInt32LE(s+20)};
  });
  const dis=execFileSync(objdump,["-d",elf],{encoding:"utf8",maxBuffer:16*1024*1024});
  const map=new Map();let label="?";
  for(const line of dis.split("\n")){
    const sym=line.match(/^\s*[a-f0-9]+ <(.+)>:$/i);
    if(sym)label=sym[1];
    const row=line.match(/^\s*([a-f0-9]+):\s+((?:[a-f0-9]{2} )*[a-f0-9]{2})(?:[ \t]{2,}|\t)(.*)$/i);
    if(row)map.set(parseInt(row[1],16),{bytes:Buffer.from(row[2].replace(/ /g,""),"hex"),text:row[3],label});
  }
  return [...new Set(records.map(r=>r.pc))].map(pc=>{
    const row=map.get(pc);
    need(row&&row.bytes.length>0&&!/<unknown>/i.test(row.text),"missing instruction row at "+pc.toString(16));
    const s=sections.filter(s=>s.type!==8&&(s.flags&6)===6&&pc>=s.addr&&pc+row.bytes.length<=s.addr+s.len&&s.off+s.len<=b.length);
    need(s.length===1,"PC outside unique executable ELF section");
    const p=s[0].off+pc-s[0].addr;
    need(b.subarray(p,p+row.bytes.length).equals(row.bytes),"instruction bytes disagree with ELF");
    return {pc:"0x"+pc.toString(16),nearest_disassembly_label:row.label,bytes:row.bytes.toString("hex"),instruction:row.text,accesses:records.filter(r=>r.pc===pc).length};
  });
}
export function tests(){
  const t="unknown_mmio UnknownAccess { addr: 65728, width: 4, is_write: false, value: 0 }";
  const s="requested_steps=1 unknown_mmio=1 changed_flash_sectors=0 result=Ok(())\n"+t+"\n";
  const a="mhac_origin core=0 pc=0x02000120 addr=65728 width=4 write=false value=0\n";
  need(compare(s,a+s)[0].pc===0x02000120,"positive failed");
  const bad=[s,a+a+s,a.replace("core=0","core=none")+s,a.replace("addr=65728","addr=65729")+s,a.replace("pc=0x02000120","pc=0x02000121")+s,a+s.replace("requested_steps=1","requested_steps=2"),a+s.replace("changed_flash_sectors=0","changed_flash_sectors=1")];
  for(const [i,x] of bad.entries()){let refused=false;try{compare(s,x)}catch{refused=true;}need(refused,"negative accepted "+i);}
  return "8/8 transcript controls PASS";
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  const [mode,...args]=process.argv.slice(2);
  if(mode==="--selftest")console.log(tests());
  else if(mode==="--install"&&args.length===1)install(args[0]);
  else if(mode==="--compare"&&args.length===4){
    const [c,o,elf,objdump]=args;
    const records=compare(readFileSync(c,"utf8"),readFileSync(o,"utf8"));
    console.log(JSON.stringify({records,sites:elfRows(elf,objdump,records),disposition:"HOLD: active instruction context, not register behavior or whole-program safety"},null,2));
  }else throw Error("usage: --selftest | --install disposable-emulator | --compare control.log observed.log ELF llvm-objdump");
}
