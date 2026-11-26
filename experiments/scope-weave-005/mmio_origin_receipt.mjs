// FM1-003 historical instruction-origin receipt verifier. Original analysis only.
// Pinned CI job 139870776313, run 45808752635, HEAD d70936e7f9b7e9b64f74bc716cc61faa1cd75f9d.
// Input: downloaded plain-text job log; this does not replace ELF or static audit.
import {readFileSync} from "node:fs";
function extract(log) {
  const lines=log.split(/\r?\n/).map(l=>l.replace(/^\S+Z /,""));
  const reports=[];
  for(let i=0;i<lines.length;i++) {
    if(lines[i]!=="{"||!lines[i+1]?.includes('"records"'))continue;
    let j=i+1;while(j<lines.length&&lines[j]!=="}")j++;
    if(j===lines.length)throw Error("truncated report");
    reports.push(JSON.parse(lines.slice(i,j+1).join("\n")));i=j;
  }
  return reports;
}
function analyze(reports) {
  const need=(ok,msg)=>{if(!ok)throw Error(msg)};
  const specs=[
    ["puya","baseline",1,4,"d0ecc00b","r0 = [r12+176]"],
    ["puya","policy",1,2,"d0ec500b","r0 = [r5+176]"],
    ["uc25hq80","baseline",2,4,"d0ecc00b","r0 = [r12+176]"],
    ["uc25hq80","policy",2,2,"d0ec500b","r0 = [r5+176]"]
  ];
  const jedec=[[0x1c00018,"1260","r2 = [r1+0]",false],[0x1c0002e,"1060","r0 = [r1+0]",false],[0x1c00036,"9560","[r1+0] = r5",true],[0x1c00132,"1060","r0 = [r1+0]",false],[0x1c00138,"9260","[r1+0] = r2",true]];
  const read=[[0x1c009f2,"d0ec4090","r9 = [r4+0]",false],[0x1c00a0a,"4360","r3 = [r4+0]",false],[0x1c00a12,"c560","[r4+0] = r5",true],[0x1c00b6e,"4060","r0 = [r4+0]",false],[0x1c00b74,"d0ec4190","[r4+0] = r9",true]];
  need(reports.length===4,"expected exactly four ordered reports");
  return specs.map(([flash,variant,j,r,resetBytes,resetInsn],i)=>{
    const p=reports[i], reset=[0x200192e,resetBytes,resetInsn,false], expected=[reset,...Array.from({length:j},()=>jedec).flat(),...Array.from({length:r},()=>read).flat()];
    need(Array.isArray(p.records)&&p.records.length===expected.length,`wrong count ${flash}/${variant}`);
    need(Array.isArray(p.sites)&&p.sites.length===11,"wrong site count");
    const sites=new Map(p.sites.map(s=>[s.pc,s]));
    need(sites.size===11,"duplicate site");
    const counts=new Map();
    for(let k=0;k<expected.length;k++){
      const [pc,bytes,instruction,write]=expected[k], a=p.records[k], hex="0x"+pc.toString(16), label=k===0?"fm1_cstart":k<=j*5?"fl_jedec_ram":"fl_read_ram";
      need(a.core===0&&a.pc===pc&&a.addr===(k===0?0x100c0:0x40200)&&a.width===4&&a.write===write&&a.value===0,`record mismatch ${flash}/${variant}/${k}`);
      const site=sites.get(hex);
      need(site&&site.bytes===bytes&&site.instruction===instruction&&site.nearest_disassembly_label===label,`site mismatch ${hex}`);
      counts.set(hex,(counts.get(hex)||0)+1);
    }
    for(const [pc,count] of counts)need(sites.get(pc).accesses===count,"site count mismatch "+pc);
    return {flash,variant,reset_reads:1,jedec_cycles:j,read_cycles:r,records:expected.length,unique_sites:11};
  });
}
if(process.argv.length!==3)throw Error("usage: node mmio_origin_receipt.mjs job.log");
const reports=extract(readFileSync(process.argv[2],"utf8"));
const results=analyze(reports);
console.log(JSON.stringify({results,total_records:results.reduce((a,b)=>a+b.records,0),disposition:"HOLD: fixed historical receipt only; not a model of physical registers"},null,2));
