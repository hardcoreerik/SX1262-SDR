# SPDX-License-Identifier: GPL-3.0-only
"""Fixed 99.1 MHz RX1 -> 250 MHz TX1 experiment, invoked by run_sweep only.

Host-buffered forwarding has no hardware continuity guarantee. The decoded
audio is from Pluto RX; it is never evidence of Heltec audio recovery.
"""
import hashlib
import json
import time
import traceback
import threading
import wave
from pathlib import Path
import numpy as np
from scipy import signal
from pluto_receiver import PlutoReceiver, block_metrics
from dut_serial import heltec_identity_matches


def iq_to_tx(z, scale):
    if not np.isfinite(scale) or scale<=0:raise ValueError('Invalid fixed scale')
    v=np.column_stack((z.real,z.imag))*scale
    clipped=float(np.mean(np.any(abs(v)>12000,axis=1)))
    return bytearray(np.clip(np.rint(v),-12000,12000).astype('<i2').tobytes()),clipped


def fm_audio(z, fs):
    narrow=signal.resample_poly(z,1,10)
    phase=np.angle(narrow[1:]*np.conj(narrow[:-1]))
    audio=signal.resample_poly(phase,24,125) # 250 kHz -> 48 kHz
    audio=signal.sosfilt(signal.butter(5,15000,fs=48000,output='sos'),audio)
    # North American broadcast-FM 75 us de-emphasis; mono only.
    alpha=np.exp(-1/(48000*75e-6))
    audio=signal.lfilter([1-alpha],[1,-alpha],audio)
    audio-=np.mean(audio)
    peak=max(float(np.max(abs(audio))),1e-9)
    return (audio/peak*.8*32767).astype('<i2')


def forward_blocks(rx,tx,seconds,convert,disable,observe):
    if not 0<seconds<=10:raise ValueError('Relay duration must be <=10 seconds')
    start=time.monotonic();n=0
    try:
        while time.monotonic()-start<seconds:
            t=time.monotonic()
            try:rx.refill();raw=rx.read()
            except Exception as exc:raise RuntimeError('Relay RX refill failed: %s' % exc) from exc
            payload=convert(raw)
            if tx.write(payload)!=len(payload):raise RuntimeError('Incomplete TX buffer write')
            try:tx.push()
            except Exception as exc:raise RuntimeError('Relay TX push failed: %s' % exc) from exc
            n+=len(raw)//4
            observe({'elapsed_s':time.monotonic()-start,'block_wall_s':time.monotonic()-t,
                     'rx_bytes':len(raw),'tx_bytes':len(payload),'samples_total':n})
    finally: disable()
    return n


def run_relay(runner):
    import iio
    if runner.sim:raise ValueError('FM relay is hardware-only; no simulated broadcast evidence')
    src=runner.src;src.disable()
    if src.backend!='iio':raise ValueError('FM relay requires verified native IIO backend')
    src._check_safety(-60)
    info=runner.dut.info()
    if not heltec_identity_matches(runner.dut.p,info):raise RuntimeError('Heltec identity mismatch')
    out=Path(runner.out);saved=[];channels=[];rx=None;tx=None;monitor=None
    monitor_stop=threading.Event();monitor_errors=[]
    meta={'simulated':False,'mode':'bounded-fm-relay','status':'started','dut_info':info,
          'rx_frequency_hz':99100000,'tx_frequency_hz':250000000,'sample_rate_hz':2500000,
          'tx_gain_db':-60,'rx_gain_db':40,'max_duration_s':10,
          'limitations':'Host-buffered live forwarding; continuity unverified. Audio is Pluto RX only. Source purity, RF power and Heltec demodulation unverified.'}
    def log(s):runner.log(s)
    def set_attr(ch,key,value):
        attr=ch.attrs[key];old=attr.value
        saved.append((attr,old.split()[0] if key=='hardwaregain' else old));attr.value=str(value)
    def probe():
        v=runner.dut.run('probe',freq_hz=250000000,dwell_ms=20)
        if not v.get('_done') or not v.get('ok') or v.get('errors'):raise RuntimeError('Invalid Heltec RX probe')
        return v
    try:
        meta['heltec_before']=probe()
        # Larger buffers reduce network overhead. RX gain remains fixed.
        rx=PlutoReceiver(src,99100000,gain_db=40,bandwidth_hz=300000,buffer_samples=65536)
        meta['rx_config']=rx.config
        meta['rx_format']={'bits':rx.bits,'shift':rx.shift}
        blocks=[]
        for _ in range(80):
            rx.buffer.refill();blocks.append(bytes(rx.buffer.read()))
        raw=b''.join(blocks);(out/'rx1-99p1mhz.iq').write_bytes(raw)
        meta['rx_metrics']=block_metrics(raw,rx.bits,rx.shift)
        values=(np.frombuffer(raw,dtype='<i2').astype(np.int32)>>rx.shift).reshape(-1,2)
        z=values[:,0]+1j*values[:,1]
        audio=fm_audio(z,2500000)
        with wave.open(str(out/'pluto-rx1-99p1-mono.wav'),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(audio.tobytes())
        if meta['rx_metrics']['clipped_fraction']>.001:raise RuntimeError('RX clipped; no TX enabled')
        sos=signal.butter(6,110000,fs=2500000,output='sos')
        initial=signal.sosfilt(sos,z[:65536]);scale=10000/max(float(np.max(abs(initial))),1)
        state=np.zeros((len(sos),2),dtype=complex);clip=[]
        def convert(raw_block):
            nonlocal state
            v=(np.frombuffer(raw_block,dtype='<i2').astype(np.int32)>>rx.shift).reshape(-1,2)
            filtered,state=signal.sosfilt(sos,v[:,0]+1j*v[:,1],zi=state)
            payload,c=iq_to_tx(filtered,scale);clip.append(c);return payload
        phy=src._phy;dev=src._dds
        for ch in dev.channels:
            if ch.scan_element:
                channels.append((ch,ch.enabled));ch.enabled=ch.id in ('voltage0','voltage1')
        txch=phy.find_channel('voltage0',True);lo=phy.find_channel('altvoltage1',True)
        set_attr(txch,'sampling_frequency',2500000)
        set_attr(txch,'rf_bandwidth',300000)
        set_attr(txch,'rf_port_select','A')
        lo.attrs['frequency'].value='250000000'
        fmt=dev.find_channel('voltage0',True).data_format
        meta['tx_format']={'bits':fmt.bits,'length':fmt.length,'shift':fmt.shift}
        if fmt.length!=16 or not fmt.is_signed or fmt.is_be:raise RuntimeError('Unsupported TX sample format')
        # AD936x TX accepts 12-bit samples MSB-aligned in 16-bit DMA words.
        # Limit component values to 12000, below the +/-32768 DMA full scale.
        tx=iio.Buffer(dev,65536,False)
        # Hardware-buffer selection may change DDS source mux; DDS scales stay zero.
        tx.write(bytearray(65536*4));tx.push()
        meta['source_before_tx']=src.frequency_readback()
        meta['source_before_tx']['dds_active']=False
        meta['source_before_tx']['basis']='DDS disabled; DMA baseband playback at TX LO, not LO-plus-DDS tone'
        log('FM relay: RX1 99.1 MHz -> TX1 250 MHz, gain -60 dB, bounded 10 seconds')
        lo.attrs['powerdown'].value='0';txch.attrs['hardwaregain'].value='-60'
        times=[]
        meta['heltec_during']=[]
        def monitor_dut():
            try:
                while not monitor_stop.wait(2):meta['heltec_during'].append(probe())
            except Exception as exc:
                monitor_errors.append(str(exc));src.disable()
        # Serial exchanges take hundreds of milliseconds. Keeping them off the
        # DMA loop prevents starving TX; they do not share IIO stream buffers.
        monitor=threading.Thread(target=monitor_dut,daemon=True);monitor.start()
        def observe(row):
            times.append(row)
            if monitor_errors:raise RuntimeError('Heltec monitor failed: '+str(monitor_errors))
        meta['forwarded_samples']=forward_blocks(rx.buffer,tx,10,convert,src.disable,observe)
        monitor_stop.set();monitor.join(3)
        if monitor.is_alive() or monitor_errors:raise RuntimeError('Heltec monitor did not finish cleanly')
        meta['timing']=times;meta['tx_component_clip_fraction_max']=max(clip,default=0)
        meta['sample_duration_s']=meta['forwarded_samples']/2500000
        meta['wall_duration_s']=times[-1]['elapsed_s']
        meta['heltec_after']=probe();meta['status']='completed'
    except BaseException as exc:
        meta['status']='aborted';meta['error']=str(exc)
        meta['traceback']=traceback.format_exc()
        if 'times' in locals():meta['partial_timing']=times
        raise
    finally:
        src.disable()
        monitor_stop.set()
        if monitor is not None:monitor.join(3)
        if tx is not None:tx.cancel();tx=None
        if rx is not None:rx.close()
        for ch,enabled in channels:ch.enabled=enabled
        for attr,old in reversed(saved):attr.value=old
        src.disable()
        meta['final_powerdown']=src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value
        meta['final_gain']=src._phy.find_channel('voltage0',True).attrs['hardwaregain'].value
        meta['final_dds_scales']=[src._dds.find_channel('altvoltage'+str(k),True).attrs['scale'].value for k in range(4)]
        meta['dut_stop']=runner.dut.run('stop')
        (out/'relay.json').write_text(json.dumps(meta,indent=2,default=str))
        log('FM relay shutdown: powerdown=%s gain=%s' % (meta['final_powerdown'],meta['final_gain']))
    if meta['final_powerdown']!='1' or any(float(v)!=0 for v in meta['final_dds_scales']):raise RuntimeError('Independently confirm TX OFF')
    log('Relay forwarded %.3f sample-seconds during %.3f wall-seconds; continuity UNVERIFIED' % (meta['sample_duration_s'],meta['wall_duration_s']))
    with (out/'sha256-relay.txt').open('w') as f:
        for p in sorted(out.iterdir()):
            if p.is_file() and p.name!='sha256-relay.txt':f.write(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')
    return str(out),[]
