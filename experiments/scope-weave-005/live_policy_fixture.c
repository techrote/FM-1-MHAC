/* Native counterpart to the physical-key experiment, no platform or flash. */
#define CP_TEST
#define main prior_main
#include "context_panel.c"
#undef main
#include "context_policy.h"
static int32_t buf[2*257];
static void emit(cp_policy_audio *s,uint32_t cmd,unsigned n){
    while(n){unsigned k=n<257?n:257;memset(buf,0,sizeof buf);cp_policy_render(s,buf,k,cmd);
        for(unsigned j=0;j<2*k;j++){assert(buf[j]>=-2048&&buf[j]<=2048);unsigned q=(uint16_t)buf[j];assert(putchar(q&255)!=EOF&&putchar(q>>8)!=EOF);}n-=k;}
}
int main(int argc,char **argv){
    assert(argc==2);unsigned mode=(unsigned)atoi(argv[1]);assert(mode<4);
    cp_edit e={0,0,0,3,0,0};cp_key(&e,0);cp_key(&e,1);cp_key(&e,6);cp_key(&e,8);e.run=1;
    cp_policy_audio s={0};unsigned eq=mode!=3,epoch=0;
    emit(&s,cp_policy_pack(cp_pack(&e),eq,epoch),18522);
    if(mode==1||mode==3)cp_key(&e,9);else if(mode==0)cp_key(&e,8);else epoch++;
    emit(&s,cp_policy_pack(cp_pack(&e),eq,epoch),110250-18522);
    return 0;
}
