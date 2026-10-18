"""Rapid capture framing, integrity and timing eligibility."""
import sys,zlib
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dut_serial import parse_heltec_audio
from heltec_audio import timing_metrics


def fixture():
    # Device records: timestamp_us uint32, raw RSSI byte, PCM int16.
    import struct
    b=b''.join(struct.pack('<IBh',i*125,240+i,-100+i) for i in range(4))
    text=('SXCAP1 ok=1 f_hz=99100000 bw_hz=58600 rate_hz=8000 n=4 status=0x52 errors=0x0000 code=ESP_OK\n'
          +'SXDATA1 offset=0 hex='+b.hex()+'\n'
          +'SXCAPEND1 bytes=28 crc32=%08X stop=1\n'%(zlib.crc32(b)&0xffffffff))
    return b,text


def test_audio_integrity_offsets_and_complete_record_count():
    b,text=fixture();r=parse_heltec_audio(text)
    assert r['ok'] and r['data']==b and r['n']==4
    for bad in [text.replace('offset=0','offset=7'),text.replace('bytes=28','bytes=21'),
                text.replace('crc32=','crc32=0'),text.replace('stop=1','stop=0'),
                text.replace('n=4','n=5'),text.replace('errors=0x0000','errors=0x0040'),
                text.replace('status=0x52','status=0x3A'),text.replace('ok=1','ok=0')]:
        assert not parse_heltec_audio(bad)['ok']


def test_timing_gate_distinguishes_requested_from_achieved_rate():
    m=timing_metrics(np.arange(8000,dtype=np.uint32)*125,8000)
    assert m['achieved_rate_hz']==8000 and m['voice_timing_gate']
    m=timing_metrics(np.arange(8000,dtype=np.uint32)*250,8000)
    assert m['achieved_rate_hz']==4000 and not m['voice_timing_gate']
    with pytest.raises(ValueError):timing_metrics(np.array([0,125,125]),8000)


def test_receive_only_runner_preserves_raw_and_stops_on_bad_capture(tmp_path):
    from types import SimpleNamespace
    from dut_serial import load_profiles
    from heltec_audio import run_capture
    calls=[]
    attr=SimpleNamespace(value='1')
    class Source:
        backend='iio'
        _phy=SimpleNamespace(find_channel=lambda *_:SimpleNamespace(attrs={'powerdown':attr}))
        def disable(self):calls.append('off')
        def describe(self):return {'tx':'OFF'}
        def set_tone(self,*a,**kw):raise AssertionError('RX-only test attempted TX')
    class Device:
        p=load_profiles()['heltec_v4_3_sx1262']
        last_raw=''
        def info(self):return {'ok':True,**self.p['required_firmware_identity']}
        def run(self,cmd,**kw):
            calls.append(cmd)
            if cmd=='stop':return {'ok':'1','_done':True}
            assert cmd=='capture'
            _,self.last_raw=fixture()
            return {'ok':False,'_done':True}
    runner=SimpleNamespace(sim=False,out=str(tmp_path),src=Source(),dut=Device(),cfg={})
    with pytest.raises(RuntimeError,match='Invalid rapid capture'):run_capture(runner)
    assert calls==['off','capture','stop','off']
    assert (tmp_path/'58600Hz-1000sps.serial.txt').is_file()
    import json
    assert json.loads((tmp_path/'meta.json').read_text())['status']=='aborted'


def test_parser_rejects_duplicate_chunks_and_calibration_error():
    _,s=fixture()
    chunk=s.splitlines()[1]+'\n'
    assert not parse_heltec_audio(s.replace(chunk,chunk+chunk))['ok']
    assert not parse_heltec_audio(s.replace('code=ESP_OK','cal_errors=0x40 code=ESP_OK'))['ok']


def test_bounded_am_waveform_has_requested_envelope_without_clipping():
    from pluto_source import am_iq
    for f in (0,300,1000,2500):
        v=np.frombuffer(am_iq(f),dtype='<i2').reshape(-1,2)
        assert len(v)==25000 and abs(v.astype(int)).max()<=12000
        envelope=np.hypot(v[:,0].astype(float),v[:,1].astype(float))
        if f:
            spectrum=abs(np.fft.rfft(envelope-envelope.mean()))
            bins=np.fft.rfftfreq(len(v),1/2500000)
            assert bins[np.argmax(spectrum)]==f
            assert 1332<envelope.min()<1335
        else:assert envelope.max()-envelope.min()<2
    with pytest.raises(ValueError):am_iq(5000)


def test_tone_fit_uses_real_timestamps_and_rejects_unrelated_noise():
    from heltec_audio import tone_metrics
    t=np.arange(8000,dtype=np.uint32)*125
    rng=np.random.default_rng(43)
    for f in (300,1000,2500):
        y=200+16*np.sin(2*np.pi*f*t/1e6)+rng.normal(0,1,len(t))
        m=tone_metrics(t,y,f)
        assert 7.8<m['fit_amplitude_db']<8.2
        assert m['peak_over_local_floor_db']>30
        noise=tone_metrics(t,200+rng.normal(0,1,len(t)),f)
        assert noise['fit_amplitude_db']<.1


def test_modulation_cli_requires_pad_arm_and_typed_confirmation(monkeypatch):
    import run_sweep
    def forbidden(*a,**kw):raise AssertionError('Hardware opened before RF interlocks')
    monkeypatch.setattr(run_sweep,'Runner',forbidden)
    assert run_sweep.main(['--heltec-modulation'])==2
    assert run_sweep.main(['--heltec-modulation','--arm-rf','--fixed-atten-db','0'])==2
    monkeypatch.setattr('builtins.input',lambda _: 'wrong')
    assert run_sweep.main(['--heltec-modulation','--arm-rf'])==2


@pytest.mark.parametrize('kind', ('am','fm'))
def test_am_burst_failure_disables_tx_and_cancels_dma(monkeypatch,kind):
    from types import SimpleNamespace
    from pluto_source import PlutoSource
    def ch(name,scan=False,**attrs):
        return SimpleNamespace(id=name,scan_element=scan,enabled=False,
            attrs={k:SimpleNamespace(value=str(v)) for k,v in attrs.items()},
            data_format=SimpleNamespace(length=16,is_signed=True,is_be=False))
    tx=ch('voltage0',hardwaregain=-89.75,sampling_frequency=2500000,rf_bandwidth=300000,rf_port_select='A')
    lo=ch('altvoltage1',frequency=250000000,powerdown=1)
    dds=[ch('voltage0',True),ch('voltage1',True)]+[ch('altvoltage'+str(i),scale=0) for i in range(4)]
    src=PlutoSource.__new__(PlutoSource)
    src.backend='iio';src.fixed_atten_db=30;src.min_fixed_atten_db=30;src.max_gain_db=-20
    src._phy=SimpleNamespace(find_channel=lambda name,_:tx if name=='voltage0' else lo)
    src._dds=SimpleNamespace(channels=dds,find_channel=lambda name,_:next(c for c in dds if c.id==name))
    calls=[]
    class Buffer:
        def __init__(self,*args):pass
        def write(self,payload):return len(payload)
        def push(self):calls.append('push')
        def cancel(self):calls.append('cancel')
    monkeypatch.setitem(sys.modules,'iio',SimpleNamespace(Buffer=Buffer))
    with pytest.raises(RuntimeError,match='serial failed'):
        with (src.am_burst(1000) if kind=='am' else src.fm_burst(1000,20000)) as state:
            assert lo.attrs['powerdown'].value=='0'
            assert state['tx_off_timer_s']==2
            raise RuntimeError('serial failed')
    assert lo.attrs['powerdown'].value=='1'
    assert float(tx.attrs['hardwaregain'].value)==-89.75
    assert calls==['push','cancel']
    assert lo.attrs['frequency'].value=='250000000'
    assert not any(c.enabled for c in dds)


def test_fm_waveform_is_constant_envelope_with_five_khz_deviation():
    from pluto_source import fm_iq
    for f in (300,1000,2500):
        v=np.frombuffer(fm_iq(f),dtype='<i2').reshape(-1,2).astype(float)
        z=v[:,0]+1j*v[:,1]
        assert np.ptp(abs(z))<1.5 and abs(v).max()<=12000
        inst=np.angle(z[1:]*z[:-1].conj())*2500000/(2*np.pi)
        expected=100000+5000*np.cos(2*np.pi*f*(np.arange(len(inst))+.5)/2500000)
        assert np.sqrt(np.mean((inst-expected)**2))<20
        assert inst.max()-100000<5050 and inst.max()-100000>4950
    with pytest.raises(ValueError):fm_iq(5000)


def test_fm_cli_keeps_arming_and_cannot_run_as_receive_only(monkeypatch):
    import run_sweep
    def forbidden(*a,**kw):raise AssertionError('Hardware opened without interlock')
    monkeypatch.setattr(run_sweep,'Runner',forbidden)
    assert run_sweep.main(['--fm-slope'])==2
    assert run_sweep.main(['--heltec-modulation','--fm-slope'])==2
    assert run_sweep.main(['--heltec-modulation','--fm-slope','--arm-rf','--fixed-atten-db','0'])==2
    monkeypatch.setattr('builtins.input',lambda _: 'wrong')
    assert run_sweep.main(['--heltec-modulation','--fm-slope','--arm-rf'])==2


def test_offair_capture_parser_bounds():
    _,s=fixture()
    for hz in (88000000,91900000,108000000,250001000):
        assert parse_heltec_audio(s.replace('f_hz=99100000','f_hz=%d'%hz))['ok']
    for hz in (87999999,108000001,249000000):
        assert not parse_heltec_audio(s.replace('f_hz=99100000','f_hz=%d'%hz))['ok']


def test_offair_mode_only_uses_source_off_and_receive_capture(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import heltec_audio
    from dut_serial import load_profiles
    calls=[]
    profile=load_profiles()['heltec_v4_3_sx1262']
    class Source:
        backend='iio'
        _phy=SimpleNamespace(find_channel=lambda *_:SimpleNamespace(attrs={'powerdown':SimpleNamespace(value='1')}))
        def disable(self):calls.append('off')
        def describe(self):return {'tx':'OFF'}
        def set_tone(self,*a,**kw):raise AssertionError('Off-air TX attempted')
        def fm_burst(self,*a,**kw):raise AssertionError('Off-air FM TX attempted')
    class Device:
        p=profile
        def info(self):return {'ok':True,**profile['required_firmware_identity']}
        def run(self,cmd):assert cmd=='stop';return {'ok':'1','_done':True}
    def receive(dut,out,stem,hz,bw,rate):
        calls.append(('capture',hz,bw,rate))
        return {'n':8000,'intervals_within_10pct':1,'median_rssi_dbm':-110}
    monkeypatch.setattr(heltec_audio,'capture_record',receive)
    runner=SimpleNamespace(sim=False,out=str(tmp_path),src=Source(),dut=Device(),log=lambda _:None,
            cfg={'sweep':{'frequencies_mhz':[91.9]},'offair_fm':{'bandwidths_hz':[58600]}})
    heltec_audio.run_offair(runner)
    assert calls==['off',('capture',91900000,58600,8000),'off','off']


def test_offair_cli_requires_receive_only_mode():
    import run_sweep
    assert run_sweep.main(['--offair-fm'])==2
