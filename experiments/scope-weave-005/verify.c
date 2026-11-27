#include "scope_weave.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
enum { FRAMES=6*4800, BLOCK=257 };
static int32_t corpus[SW_PRESETS][2*FRAMES];
static int32_t a[2*BLOCK],b[2*BLOCK];
static uint32_t rng=0x31415926u;
static unsigned rand32(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void le(FILE *f,uint32_t x,unsigned n){for(unsigned i=0;i<n;i++){assert(fputc((int)(x&255u),f)!=EOF);x>>=8;}}
static void riff(FILE *f,unsigned frames){
    assert(fwrite("RIFF",1,4,f)==4);le(f,36u+4u*frames,4);
    assert(fwrite("WAVEfmt ",1,8,f)==8);le(f,16,4);le(f,1,2);le(f,2,2);
    le(f,SW_FS,4);le(f,SW_FS*4u,4);le(f,4,2);le(f,16,2);
    assert(fwrite("data",1,4,f)==4);le(f,4u*frames,4);
}
int main(int argc,char **argv){
    assert(argc==2);
    unsigned legal=0;
    for(unsigned i=0;i<59049u;i++){
        unsigned v=i;uint8_t t[5];
        for(unsigned j=0;j<5;j++){t[j]=(uint8_t)(v%9u);v/=9u;}
        int p=sw_parse(t);
        if(p>=0){legal++;for(unsigned j=0;j<5;j++)assert(t[j]==sw_token((unsigned)p,0,j));}
    }
    assert(legal==27u);
    printf("grammar accepted=%u rejected=%u\n",legal,59049u-legal);
    for(unsigned m=0;m<SW_MODES;m++){
        unsigned aliases=0,unique=0;
        for(unsigned p=0;p<SW_PRESETS;p++){
            sw_state s={0};memset(corpus[p],0,sizeof corpus[p]);sw_render(&s,corpus[p],FRAMES,p,m,26,1);
            unsigned matches=0;
            for(unsigned q=0;q<p;q++)if(!memcmp(corpus[p],corpus[q],sizeof corpus[p]))matches++;
            aliases+=matches;unique+=!matches;
        }
        assert(unique==(m==0?27u:m==1?18u:3u));
        assert(aliases==(m==0?0u:m==1?9u:108u));
        printf("mode=%u distinct_pcm=%u identical_pairs=%u\n",m,unique,aliases);
    }
    sw_state x={0},y={0};unsigned peak=0,mutes=0;uint64_t frames=0,partitions=0;
    for(unsigned i=0;i<20000u;i++){
        unsigned p=rand32()%27u,m=rand32()%3u,r=rand32()%27u,run=rand32()%5u!=0u;
        unsigned n=1u+rand32()%BLOCK;
        memset(a,0,sizeof a);memset(b,0,sizeof b);
        sw_render(&x,a,n,p,m,r,run);
        for(unsigned pos=0;pos<n;){unsigned k=1u+rand32()%31u;if(k>n-pos)k=n-pos;sw_render(&y,b+2u*pos,k,p,m,r,run);pos+=k;partitions++;}
        assert(!memcmp(a,b,2u*n*sizeof a[0]));
        assert(x.phase[0]==y.phase[0]&&x.phase[1]==y.phase[1]&&x.inc[0]==y.inc[0]&&x.inc[1]==y.inc[1]&&x.until==y.until&&x.env==y.env&&x.preset==y.preset&&x.mode==y.mode&&x.running==y.running&&x.slot==y.slot&&x.token==y.token);
        for(unsigned j=0;j<2u*n;j++){unsigned z=(unsigned)abs(a[j]);assert(z<=2048u);if(z>peak)peak=z;}
        frames+=n;
        if(i%97u==0){
            for(unsigned k=0;k<10u;k++){memset(a,0,sizeof a);memset(b,0,sizeof b);sw_render(&x,a,BLOCK,p,m,r,0);sw_render(&y,b,BLOCK,p,m,r,0);assert(!memcmp(a,b,sizeof a));}
            for(unsigned j=0;j<2u*BLOCK;j++)assert(a[j]==0);
            assert(x.env==0&&y.env==0);mutes++;
        }
    }
    printf("stress commands=20000 frames=%llu partitions=%llu mute_checks=%u peak=%u state_bytes=%zu\n",(unsigned long long)frames,(unsigned long long)partitions,mutes,peak,sizeof(sw_state));
    FILE *f=fopen(argv[1],"wb");assert(f);riff(f,6u*3u*FRAMES);
    /* Q(N(beacon)) vs N(Q(beacon)), ordered/sorted/leaf. Three phrases per section. */
    for(unsigned m=0;m<3u;m++)for(unsigned p=0;p<2u;p++){
        sw_state s={0};
        for(unsigned z=0;z<3u;z++){
            memset(corpus[0],0,sizeof corpus[0]);sw_render(&s,corpus[0],FRAMES,p?9u:3u,m,26,1);
            for(unsigned j=0;j<2u*FRAMES;j++)le(f,(uint16_t)corpus[0][j],2);
        }
    }
    assert(!fclose(f));puts("PASS");return 0;
}
