/* Optional Scope Context audio policy. Include after cp_audio/cp_render.
 * Bits 0..15: original command; bit 16: equivalence mode;
 * bits 17..31: explicit retrigger epoch (modulo 32768).
 * One snapshot per callback; multiple edits between snapshots coalesce. */
#ifndef CONTEXT_POLICY_H
#define CONTEXT_POLICY_H
#define CP_EQ_BIT (UINT32_C(1)<<16)
#define CP_EPOCH_MASK UINT32_C(32767)
typedef struct { cp_audio core; uint16_t epoch; uint8_t seen; } cp_policy_audio;
static uint32_t cp_policy_pack(uint32_t cmd,unsigned equivalent,unsigned epoch){
    return (cmd&UINT32_C(65535))|(equivalent?CP_EQ_BIT:0)|((epoch&CP_EPOCH_MASK)<<17);
}
static uint32_t cp_policy_key(uint32_t snapshot){
    uint32_t cmd=snapshot&UINT32_C(65535);
    /* No witness means context does not affect any rendered token. */
    if((snapshot&CP_EQ_BIT)&&!(cmd&(1u<<14)))cmd&=~(UINT32_C(3)<<12);
    return cmd;
}
static void cp_policy_render(cp_policy_audio *a,int32_t *out,uint32_t n,uint32_t snapshot){
    uint16_t epoch=(uint16_t)(snapshot>>17);
    if(a->seen&&a->epoch!=epoch)a->core.valid=0;
    a->seen=1;a->epoch=epoch;
    cp_render(&a->core,out,n,cp_policy_key(snapshot));
}
#endif
