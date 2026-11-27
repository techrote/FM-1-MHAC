// Offline experiment only. Run: node evidence/fm1-record-fault/monotone_finalization.mjs
function finalizationModel() {
  // Original offline model; no device I/O. Source authority:
  // zvenson/dinghy@92f17b28f2d05f2f78fd1b160b58475d518902c8
  // firmware/src/ota.c (FM-1 constants, stage, record, boot cleanup),
  // firmware/loader/ldr_core.c (cleanup screening predicate).
  // This predicate is NOT a verified implementation of SPL boot selection.
  const AREA = 0xe0000, SECTOR = 4096, SPAN = 5 * SECTOR, RECORD = SPAN - 256;
  let assertions = 0;
  function check(p, message) { if (!p) throw Error(message); assertions++; }
  const u16 = (a,o) => a[o] | (a[o+1]<<8);
  const w16 = (a,o,x) => {a[o]=x&255; a[o+1]=x>>>8;};
  const u32 = (a,o) => (a[o]+a[o+1]*256+a[o+2]*65536+a[o+3]*16777216)>>>0;
  function w32(a,o,x) { for(let i=0;i<4;i++) a[o+i]=(x>>>(8*i))&255; }
  function crc(a, start, n) {
    let c=0;
    for(let i=start;i<start+n;i++){
      c ^= a[i]<<8;
      for(let b=0;b<8;b++) c=((c<<1)^((c&0x8000)?0x1021:0))&65535;
    }
    return c;
  }
  function canonical() {
    const a=new Uint8Array(112);
    w16(a,2,0x5a0d);w16(a,4,0x5a01);w16(a,6,0x5441);
    for(const [i,ch] of [..."ota-FM-1_015"].entries()) a[8+i]=ch.charCodeAt(0);
    w32(a,72,AREA);w16(a,0,crc(a,2,78));return a;
  }
  const original=canonical(), originalCRC=u16(original,0);
  const screen=a=>u16(a,6)===0x5441 && u16(a,0)!==0 && u16(a,0)===crc(a,2,78);
  const same=(a,b)=>a.length===b.length&&a.every((x,i)=>x===b[i]);
  const canProgram=(a,b)=>a.every((x,i)=>(x&b[i])===b[i]);
  const canPartialErase=(a,b)=>a.every((x,i)=>(x|b[i])===b[i]);
  check(crc(new Uint8Array([49,50,51,52,53,54,55,56,57]),0,9)===0x31c3,"CRC known vector");
  check(screen(original)&&originalCRC!==0,"canonical record");
  // Proposed logical tombstone: clear only the stored CRC. Under a strictly
  // local monotone 1->0 program, any subset of changed CRC bits is considered.
  const tombstone=original.slice();w16(tombstone,0,0);
  let programStates=0, validProgramStates=0;
  for(let v=0;v<65536;v++){
    if((v&originalCRC)!==v)continue;
    const x=original.slice();w16(x,0,v);
    check(canProgram(original,x),"program direction");
    check(screen(x)===(v===originalCRC),"only unchanged CRC screens valid");
    check(same(x.subarray(2),original.subarray(2)),"record payload unchanged");
    programStates++;validProgramStates+=Number(screen(x));
  }
  check(!screen(tombstone),"full tombstone invalid");
  // Re-erasure is NOT the reverse of a safe transactional commit. A torn
  // erase can restore the exact CRC (or a different CRC-valid payload).
  let eraseCRCStates=0, validEraseCRCStates=0;
  for(let v=0;v<65536;v++){
    const x=tombstone.slice();w16(x,0,v);
    check(canPartialErase(tombstone,x),"erase direction");
    check(screen(x)===(v===originalCRC),"unchanged payload CRC screening");
    eraseCRCStates++;validEraseCRCStates+=Number(screen(x));
  }
  check(canPartialErase(tombstone,original)&&screen(original),"record resurrection witness");
  // Enumerate one-bit changes in covered payload, leaving magic unchanged.
  // From a zero CRC, any recomputed CRC can be reached by 0->1 transitions.
  let alteredPayloads=0, alteredPointerWitness=null;
  for(let offset=2;offset<80;offset++){
    for(let bit=0;bit<8;bit++){
      if((tombstone[offset]&(1<<bit))!==0)continue;
      const x=tombstone.slice();x[offset]|=1<<bit;w16(x,0,crc(x,2,78));
      check(canPartialErase(tombstone,x),"altered record monotone erase");
      if(!screen(x))continue;
      check(!same(x,original),"noncanonical CRC-valid record");
      alteredPayloads++;
      if(!alteredPointerWitness&&u32(x,72)!==AREA)
        alteredPointerWitness={offset,bit,originalAddress:AREA,mutatedAddress:u32(x,72),crc:u16(x,0)};
    }
  }
  check(alteredPointerWitness!==null,"changed pointer proxy witness");
  // Candidate ordering: marker sector first, then body sectors, with full
  // readback between phases. This helps only under stronger erase/boot
  // assumptions. A synthetic occupied fifth sector shares erase granularity
  // with the marker; the source's maximum staged body allows this.
  const maxBody=SPAN-512, header=32;
  const fitsSeparateMarkerSector=len=>Number.isInteger(len)&&len>0&&len+header<=4*SECTOR;
  check(fitsSeparateMarkerSector(4*SECTOR-header),"exact disjoint boundary");
  check(!fitsSeparateMarkerSector(4*SECTOR-header+1),"one-byte overlap");
  check(!fitsSeparateMarkerSector(maxBody),"pinned max allows overlap");
  check(maxBody+header<RECORD,"record page not overwritten by staging at maximum");
  function fixture(bodyLength){
    const bytes=new Uint8Array(SPAN);bytes.fill(255);
    for(let i=0;i<header+bodyLength;i++)bytes[i]=(i*73+19)&127;
    bytes.set(tombstone,RECORD);return bytes;
  }
  const bodyLengths=[1,4*SECTOR-header,4*SECTOR-header+1,maxBody];
  const cases=[];
  for(const len of bodyLengths){
    const start=fixture(len), bodyEnd=header+len;
    const valid=x=>screen(x.subarray(RECORD,RECORD+112));
    const bodyIntact=x=>same(x.subarray(0,bodyEnd),start.subarray(0,bodyEnd));
    const oldOrder=start.slice();oldOrder.fill(255,0,SECTOR);oldOrder.set(original,RECORD);
    check(valid(oldOrder)&&!bodyIntact(oldOrder)&&canPartialErase(start,oldOrder),"body-first torn erase witness");
    const markerFirst=start.slice();markerFirst.set(original,RECORD);
    // If the body occupies any byte in sector five, torn erasure can change
    // that byte while resurrecting the record.
    if(bodyEnd>4*SECTOR)markerFirst[4*SECTOR]=255;
    check(valid(markerFirst)&&canPartialErase(start,markerFirst),"marker-first torn erase witness");
    check(bodyIntact(markerFirst)===fitsSeparateMarkerSector(len),"body separation condition");
    const fullyErased=start.slice();fullyErased.fill(255,4*SECTOR);
    check(!valid(fullyErased),"fully erased marker does not screen valid");
    fullyErased.fill(255,0,4*SECTOR);
    check(!valid(fullyErased),"later body erasure cannot restore erased record in this model");
    cases.push({bodyLength:len,bodyFirstResurrectedWithDamage:true,markerFirstResurrectedWithDamage:!bodyIntact(markerFirst)});
  }
  // Negative control: the model has no authority to approve an installation.
  // Even a disjoint marker sector leaves altered CRC-valid records possible
  // during partial erase; actual SPL and NOR failure behavior are unverified.
  return {classification:"offline conditional counterexample; installation HOLD",
    canonicalCRC:"0x"+originalCRC.toString(16),programStates,validProgramStates,
    eraseCRCStates,validEraseCRCStates,alteredPayloads,alteredPointerWitness,
    sourceMaximumBody:maxBody,maxBodyWithDisjointMarkerSector:4*SECTOR-header,cases,assertions,
    limitations:["local monotone program model, arbitrary monotone partial erase model",
      "screening predicate is not actual SPL selection",
      "no target, physical flash, bootloader or application execution",
      "no flash commands or hardware adapter; no installation authorization"]};
}
console.log(JSON.stringify(finalizationModel(), null, 2));
