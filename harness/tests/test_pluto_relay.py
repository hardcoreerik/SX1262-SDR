"""Bounded FM relay conversions and failure cleanup."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pluto_relay import iq_to_tx, fm_audio, forward_blocks


def test_tx_scaling_is_fixed_and_clips_without_wrapping():
    z=np.array([100+200j,40000-40000j])
    raw, clipped=iq_to_tx(z, 1)
    assert np.frombuffer(raw,dtype='<i2').tolist()==[100,200,12000,-12000]
    assert clipped==.5
    with pytest.raises(ValueError):iq_to_tx(z, float('nan'))


def test_fm_decoder_recovers_one_khz_from_synthetic_fm():
    fs=2500000;t=np.arange(fs//4)/fs
    z=np.exp(1j*2*np.pi*10000*np.cumsum(np.sin(2*np.pi*1000*t))/fs)
    a=fm_audio(z,fs)
    f=np.fft.rfftfreq(len(a),1/48000)
    assert abs(f[np.argmax(abs(np.fft.rfft(a))) ]-1000)<10


def test_stream_failure_always_shuts_down():
    class Rx:
        def refill(self):raise OSError('RX failed')
    class Tx:
        def push(self):raise AssertionError('TX pushed without RX')
    calls=[]
    with pytest.raises(RuntimeError,match='RX refill failed'):
        forward_blocks(Rx(),Tx(),1,lambda raw:raw,lambda:calls.append('off'),lambda row:None)
    assert calls==['off']


def test_relay_cli_retains_arming_pad_and_typed_interlock(tmp_path, monkeypatch):
    import run_sweep
    monkeypatch.chdir(tmp_path)
    def forbidden(*args,**kwargs):raise AssertionError('Hardware opened without interlocks')
    monkeypatch.setattr(run_sweep,'Runner',forbidden)
    assert run_sweep.main(['--pluto-relay','--no-plot'])==2
    assert run_sweep.main(['--pluto-relay','--arm-rf','--fixed-atten-db','0'])==2
    monkeypatch.setattr('builtins.input',lambda _: 'wrong')
    assert run_sweep.main(['--pluto-relay','--arm-rf'])==2


def test_tx_timeout_and_short_write_both_disable_output():
    class Rx:
        def refill(self):pass
        def read(self):return bytearray(16)
    class Tx:
        def write(self,data):return len(data)
        def push(self):raise OSError('TX timed out')
    calls=[]
    with pytest.raises(RuntimeError,match='TX push failed'):
        forward_blocks(Rx(),Tx(),1,lambda x:x,lambda:calls.append('off'),lambda _:None)
    assert calls==['off']
    tx=Tx();tx.write=lambda _:0;calls.clear()
    with pytest.raises(RuntimeError,match='Incomplete TX buffer'):
        forward_blocks(Rx(),tx,1,lambda x:x,lambda:calls.append('off'),lambda _:None)
    assert calls==['off']
