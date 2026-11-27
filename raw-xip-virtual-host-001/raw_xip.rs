use fm1_plugin::engine::{self, Cmd, Shared, View};
use fm1_plugin::{Fm1Params, RawImage};
use std::sync::{mpsc, Arc, Mutex};

fn take(audio: &mut rtrb::Consumer<[f32; 2]>, frames: usize) -> Vec<[f32;2]> {
    let mut out=Vec::with_capacity(frames);
    while out.len()<frames {
        match audio.pop() {
            Ok(f)=>out.push(f),
            Err(_)=>std::thread::sleep(std::time::Duration::from_millis(1)),
        }
    }
    out
}

#[test]
fn raw_xip_boots_and_plays_without_becoming_a_package_save() {
    let bytes = include_bytes!("fixtures/scope-weave.xip.bin").to_vec();
    let shared=Arc::new(Shared{view:Mutex::new(View{lcd:vec![0;240*240],leds:[0.0;41],pads:[0;16],board:fm1_soc::Board::Fm1,booted:false,halted:false,speed:0.0,starved:0,late:0}),quit:Default::default()});
    let params=Arc::new(Fm1Params::default());
    let (tx,rx)=mpsc::channel();
    let (_midi,midi_rx)=rtrb::RingBuffer::new(64);
    let (audio_tx,mut audio)=rtrb::RingBuffer::new(16384);
    let sh=shared.clone(); let p=params.clone();
    let t=std::thread::spawn(move||engine::run(sh,p,rx,midi_rx,audio_tx));
    tx.send(Cmd::Block(1024)).unwrap();
    let (ack,got)=mpsc::channel();
    tx.send(Cmd::LoadRaw{raw:RawImage{name:"Scope Weave".into(),image:Arc::new(bytes),entry:0x02000120},reply:ack}).unwrap();
    got.recv_timeout(std::time::Duration::from_secs(10)).unwrap().unwrap();
    let _=take(&mut audio,44_100);
    let n3=fm1_soc::periph::key_id("N3").unwrap();
    let play=fm1_soc::periph::key_id("PLAY").unwrap();
    for id in [n3,play] { tx.send(Cmd::Key{id,down:true}).unwrap(); tx.send(Cmd::Key{id,down:false}).unwrap(); let _=take(&mut audio,8_000); }
    let heard=take(&mut audio,3*44_100);
    assert!(heard.iter().any(|f|f[0].abs().max(f[1].abs())>0.0001),"raw XIP produced no audio");
    assert!(shared.view.lock().unwrap().booted);
    assert!(params.firmware.lock().unwrap().pkg.is_empty(),"raw image leaked into package state");
    assert!(!params.raw_xip.lock().unwrap().image.is_empty());
    shared.quit.store(true,std::sync::atomic::Ordering::Relaxed);
    t.join().unwrap();
}
