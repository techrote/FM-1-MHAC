/* Original host-only harness. Never accesses hardware. Supply extracted, pinned
 * upstream functions in fm1_record_core.inc (see extract.py). No upstream code
 * is bundled. This is cleanup-only, not complete loader or recovery qualification. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#define SECTOR 4096u
#define COUNT 256u
static uint8_t flash[COUNT * SECTOR];
static unsigned reads, erases, clears, checks, order_bad;
static int ram, fail_read, fail_erase, cut, partial;
static jmp_buf power;
static void ldr_record_clear(void) { ++clears; ram=0; if(cut==1) longjmp(power,1); }
static int ldr_fread(uint32_t off, void *p, uint32_t n) {
    if(ram || !clears) ++order_bad;
    ++reads;
    if(off>sizeof flash || n>sizeof flash-off) abort();
    if((int)(off/SECTOR)==fail_read) return -1;
    memcpy(p,flash+off,n); return 0;
}
static int ldr_erase(uint32_t off) {
    if(ram || !clears) ++order_bad;
    ++erases;
    if(off%SECTOR || off>=sizeof flash) abort();
    if(cut==2) longjmp(power,1);
    if((int)(off/SECTOR)==fail_erase) {
        if(partial) memset(flash+off,255,SECTOR/2);
        return -1;
    }
    memset(flash+off,255,SECTOR);
    if(cut==3) longjmp(power,1);
    return 0;
}
#include "fm1_record_core.inc"
static void check(int ok,const char *msg) { if(!ok){fprintf(stderr,"FAIL: %s\n",msg);exit(1);} ++checks; }
static void reset(void) { memset(flash,255,sizeof flash); reads=erases=clears=order_bad=0; ram=1; fail_read=fail_erase=-1;cut=partial=0; }
static uint8_t *record(unsigned s) { return flash+(s+1)*SECTOR-256; }
static void put(unsigned s) {
    uint8_t *r=record(s); memset(flash+s*SECTOR,0x37,SECTOR); memset(r,0,80);
    r[6]=0x41;r[7]=0x54; uint32_t c=ota_crc16(r+2,78,0);
    if(!c) abort();
    r[0]=(uint8_t)c;r[1]=(uint8_t)(c>>8);
}
static int erased(unsigned s) { for(unsigned i=0;i<SECTOR;i++) if(flash[s*SECTOR+i]!=255) return 0; return 1; }
static void interrupted(void) { if(setjmp(power)==0) ldr_records_drop(); }
int main(void) {
    check(LDR_REC_LO/SECTOR==147 && LDR_REC_HI/SECTOR==252,"pinned window");
    check(ota_crc16((const uint8_t*)"123456789",9,0)==0x31c3,"CRC known answer");
    for(unsigned s=0;s<COUNT;s++) {
        reset();put(s);ldr_records_drop();int inside=s>=147&&s<252;
        check(erased(s)==inside,"per-sector erase oracle");check(erases==(unsigned)inside,"per-sector count");
        check(reads==105&&clears==1&&!ram&&!order_bad,"scan and ordering");
        for(unsigned j=0;j<COUNT;j++) if(j!=s) check(erased(j),"untouched sector");
    }
    reset();put(224);record(224)[6]^=1;ldr_records_drop();check(!erases&&!erased(224),"bad magic");
    reset();put(224);record(224)[79]^=1;ldr_records_drop();check(!erases&&!erased(224),"bad CRC");
    reset();put(224);record(224)[0]=record(224)[1]=0;ldr_records_drop();check(!erases&&!erased(224),"zero CRC field");
    for(int s=147;s<252;s++) {
        reset();put(251);put(147);fail_read=s;ldr_records_drop();
        check(reads==(unsigned)(252-s),"read fault stops scan");check(!erased(147),"lower record survives read fault");
        check(erased(251)==(s!=251),"higher record outcome");check(!ram&&clears==1,"RAM already cleared on read failure");
    }
    for(int s=147;s<252;s++) {
        reset();put((unsigned)s);fail_erase=s;ldr_records_drop();
        check(erases==1&&reads==105&&!erased((unsigned)s),"erase failure ignored");check(!ram,"RAM cleared on erase failure");
    }
    reset();put(250);put(151);fail_erase=250;ldr_records_drop();
    check(!erased(250)&&erased(151)&&erases==2,"later record erased after failed erase");
    reset();put(151);fail_erase=151;partial=1;ldr_records_drop();
    check(!erased(151)&&flash[151*SECTOR]==255&&ota_rd16(record(151)+6)==0x5441,"partial erase damages data but retains record");
    for(int c=1;c<=3;c++) {
        reset();put(250);put(151);cut=c;interrupted();
        check(!ram&&!erased(151)&&erased(250)==(c==3),"interruption snapshot");
        cut=0;ldr_records_drop();check(erased(250)&&erased(151),"explicit cleanup retry converges");
    }
    printf("PASS %u assertions; 256 placement cases, 105 read faults, 105 erase faults, 3 interruption points\n",checks);
    puts("HOLD: no physical controller, boot selection, or installation authorization established");
    return 0;
}
