// FM1-003, 2026-11-27. Original offline write-footprint model; never opens hardware.
 // Usage: node fm1-003-write-footprint.mjs --selftest
 //        node fm1-003-write-footprint.mjs trace.json
 // Schema: {schema:1,board:"FM-1",upstream_pin:<pin>,jedec:"856014" or "B36014",
 // loader:"felucca-pinned",kind:"synthetic"|"modeled"|"observed",
 // events:[{phase:"stage"|"unstage"|"boot_cleanup"|"app"|"record_cleanup",
 // op:"erase"|"program",off:<integer byte offset>,len:<integer byte count>}]}
 // Model source: zvenson/dinghy at 92f17b28f2d05f2f78fd1b160b58475d518902c8.
 // ota.c (231-248, 283-421): staging, refusal cleanup, record commit, boot cleanup.
 // platform.c (161-175): staging guard; fm1_flash.h (150-184, 223-240): sector/page constraints.
 // loader.c (25-34, 83-99): loader range guard; ldr_core.c (31-44, 101-136, 143-185): record scan and app writes.
 // fm1_flash_map.h (FM-1 branch): main store and globals. No upstream source copied.
 // Record cleanup conditionally erases whole sectors across its scan, including potential user store.
 // Unknown-chip handling calls cleanup; it is not necessarily write-free.
 // Failed staging calls unstage even on initial validation errors; erase return codes ignored there.
 // Source window conformity is NOT proof of route identity, trace completeness or hardware safety.
 // No actual flash trace captured. Selftest receipt in JS runtime: {"checks":10786,"app_sectors":143,"record_scan_sectors":105,"stage_sectors":5,"record_scan_outside_stage":100,"record_scan_overlapping_main_store":73,"head_sectors":4}
function createModel(){
  const pin="92f17b28f2d05f2f78fd1b160b58475d518902c8";
  const sector=4096, page=256, capacity=1048576;
  const ranges={stage:[0xe0000,0xe5000],app:[0x4000,0x93000],records:[0x93000,0xfc000],store:[0x97000,0xe0000]};
  const known=new Set(["856014","B36014"]);
  const phases=new Set(["stage","unstage","boot_cleanup","app","record_cleanup"]);
  const inside=(off,len,r)=>off>=r[0]&&off<=r[1]&&len<=r[1]-off;
  function inspect(trace){
    if(!trace||typeof trace!=="object"||trace.schema!==1||!Array.isArray(trace.events)||trace.events.length>100000) throw Error("invalid trace schema or size");
    const problems=[],outside=[],ambiguous=[],seen=new Set();
    const chip=typeof trace.jedec==="string"?trace.jedec.toUpperCase():"";
    if(trace.upstream_pin!==pin) problems.push("upstream pin not established");
    if(trace.board!=="FM-1") problems.push("board not established");
    if(!known.has(chip)) problems.push("flash part not established");
    if(trace.loader!=="felucca-pinned") problems.push("loader route not established as pinned Felucca");
    if(!["modeled","synthetic","observed"].includes(trace.kind)) problems.push("trace kind unknown");
    if(!trace.events.length) problems.push("empty trace");
    trace.events.forEach((e,i)=>{
      if(!e||typeof e!=="object"||!phases.has(e.phase)||!["erase","program"].includes(e.op)||!Number.isSafeInteger(e.off)||!Number.isSafeInteger(e.len)||e.off<0||e.len<=0||e.off>=capacity||e.len>capacity-e.off){outside.push({i,reason:"invalid event or range"});return;}
      const {phase,op,off,len}=e;
      if(op==="erase"&&(len!==sector||off%sector!==0)||op==="program"&&(len>page||off%page+len>page)){outside.push({i,reason:"not a physical sector erase or single-page program"});return;}
      const range=phase==="app"?ranges.app:phase==="record_cleanup"?ranges.records:ranges.stage;
      if(!inside(off,len,range)||(["unstage","boot_cleanup","record_cleanup"].includes(phase)&&op!=="erase")){outside.push({i,reason:"outside phase source window or operation"});return;}
      if(phase==="record_cleanup"&&!inside(off,len,ranges.stage)) ambiguous.push({i,reason:"record erase outside dedicated staging area; backup/ownership evidence required"});
      if(phase==="record_cleanup"&&!known.has(chip)) ambiguous.push({i,reason:"record erase on unknown flash part"});
      for(let s=Math.floor(off/sector);s<=Math.floor((off+len-1)/sector);s++)seen.add(s);
    });
    return {status:"HOLD",flash_authorized:false,source_window_conforms:outside.length===0&&trace.events.length>0,conservative_model_pass:problems.length===0&&outside.length===0&&ambiguous.length===0,problems,outside,ambiguous,distinct_sectors:seen.size,limitation:"Only supplied event geometry and declared labels checked. No completeness, binary identity, hardware behavior, data preservation, successful recovery or authorization established."};
  }
  function inventory(){
    const list=r=>Array.from({length:(r[1]-r[0])/sector},(_,i)=>r[0]+i*sector);
    const records=list(ranges.records),store=list(ranges.store),stage=list(ranges.stage);
    return {app_sectors:list(ranges.app).length,record_scan_sectors:records.length,stage_sectors:stage.length,record_scan_outside_stage:records.filter(x=>!stage.includes(x)).length,record_scan_overlapping_main_store:records.filter(x=>store.includes(x)).length,head_sectors:0x4000/sector};
  }
  function tests(){
    let checks=0;function check(x,msg){if(!x)throw Error(msg);checks++}
    const trace=events=>({schema:1,board:"FM-1",upstream_pin:pin,jedec:"856014",loader:"felucca-pinned",kind:"synthetic",events});
    for(const phase of phases)for(let s=0;s<256;s++){
      const x=inspect(trace([{phase,op:"erase",off:s*4096,len:4096}]));
      const legal=phase==="app"?s>=4&&s<147:phase==="record_cleanup"?s>=147&&s<252:s>=224&&s<229;
      check(x.source_window_conforms===legal,`erase oracle ${phase}/${s}`);
      const strict=legal&&(phase!=="record_cleanup"||s>=224&&s<229);
      check(x.conservative_model_pass===strict,`policy oracle ${phase}/${s}`);
    }
    for(let p=0;p<4096;p++)for(const phase of ["app","stage"]){
      const expected=phase==="app"?p>=64&&p<2352:p>=3584&&p<3664;
      check(inspect(trace([{phase,op:"program",off:p*256,len:256}])).source_window_conforms===expected,`page oracle ${phase}/${p}`);
    }
    const good={phase:"app",op:"program",off:0x4000,len:256};
    const reject=[{...good,off:0},{...good,off:0x3fff,len:2},{...good,off:0x92fff,len:2},{...good,off:0x4001},{...good,len:0},{...good,len:-1},{...good,len:257},{...good,off:0x100000},{...good,off:0xffffffff},{...good,off:16384.5},{...good,off:NaN},{...good,op:"chip_erase"},{...good,phase:"unknown"},{phase:"unstage",op:"program",off:0xe0000,len:1},{phase:"record_cleanup",op:"program",off:0x93000,len:1},{phase:"app",op:"erase",off:0x4001,len:4096},{phase:"stage",op:"erase",off:0xe0000,len:8192},null];
    for(const e of reject)check(!inspect(trace([e])).conservative_model_pass,"malformed event accepted");
    for(const patch of [{jedec:"EB6014"},{jedec:""},{loader:"official"},{loader:"unknown"},{board:"SMK-37"},{upstream_pin:"wrong"},{kind:"unknown"}])check(!inspect({...trace([good]),...patch}).conservative_model_pass,"bad route accepted");
    check(!inspect(trace([])).conservative_model_pass,"empty accepted");
    check(inspect({...trace([good]),jedec:"B36014"}).conservative_model_pass,"second modeled chip rejected");
    const unknown=inspect({...trace([{phase:"record_cleanup",op:"erase",off:0xe0000,len:4096}]),jedec:"unknown"});
    check(unknown.source_window_conforms&&!unknown.conservative_model_pass&&unknown.ambiguous.length===1,"unknown chip cleanup witness");
    const store=inspect(trace([{phase:"record_cleanup",op:"erase",off:0x97000,len:4096}]));
    check(store.source_window_conforms&&!store.conservative_model_pass,"main store witness");
    const result=inspect(trace([good]));
    check(result.conservative_model_pass&&!result.flash_authorized&&result.status==="HOLD","authorization invariant");
    const inv=inventory();
    check(inv.app_sectors===143&&inv.record_scan_sectors===105&&inv.stage_sectors===5&&inv.record_scan_outside_stage===100&&inv.record_scan_overlapping_main_store===73,"inventory");
    for(const bad of [null,{}, {schema:1,events:null}]){let refused=false;try{inspect(bad)}catch{refused=true}check(refused,"bad schema accepted")}
    return {checks,...inv};
  }
  return {inspect,inventory,tests};
}
const model=createModel();
try {
  if(process.argv.length!==3) throw Error("use --selftest or a JSON trace path");
  if(process.argv[2]==="--selftest") console.log(JSON.stringify(model.tests(),null,2));
  else {
    const fs=await import("node:fs");
    const name=process.argv[2];
    if(!fs.statSync(name).isFile()||fs.statSync(name).size>16000000)throw Error("not a bounded regular trace file");
    const result=model.inspect(JSON.parse(fs.readFileSync(name,"utf8")));
    console.log(JSON.stringify(result,null,2));
    if(!result.conservative_model_pass)process.exitCode=2;
  }
} catch(e){console.error("HOLD: "+e.message);process.exitCode=2;}
