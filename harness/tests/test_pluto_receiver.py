# SPDX-License-Identifier: GPL-3.0-only
"""RX scaling, no-TX-on-stream-failure, and reverse-run evidence boundaries."""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from pluto_receiver import PlutoReceiver, block_metrics
import run_sweep


def test_source_readback_preserves_dds_quantization_without_claiming_calibration():
    from pluto_source import PlutoSource
    from types import SimpleNamespace
    def channel(value):
        return SimpleNamespace(attrs={'frequency': SimpleNamespace(value=str(value))})
    source = object.__new__(PlutoSource)
    source.backend = 'iio'
    source._phy = SimpleNamespace(find_channel=lambda name, output: channel(199000998))
    source._dds = SimpleNamespace(find_channel=lambda name, output: channel(999859))
    result = source.frequency_readback()
    assert result['lo_plus_dds_i_hz'] == 200000857
    assert result['dds_i_hz'] == result['dds_q_hz'] == 999859
    assert 'unverified' in result['basis']
    source.backend = 'sim'
    assert source.frequency_readback() is None


def test_iq_uses_12bit_component_fullscale_and_reports_clipping():
    half = np.array([1024, -1024] * 8, dtype='<i2').tobytes()
    metrics = block_metrics(half)
    assert metrics['rms_dbfs'] == pytest.approx(-6.0206, abs=0.0001)
    assert metrics['samples'] == 8 and metrics['clipped_fraction'] == 0
    clipped = np.array([2047, -2048], dtype='<i2').tobytes()
    assert block_metrics(clipped)['clipped_fraction'] == 1
    with pytest.raises(ValueError):
        block_metrics(b'\x00\x00')


def test_stream_failure_never_calls_transmit():
    class BrokenBuffer:
        cancelled = False

        def refill(self):
            raise OSError('RX DMA failure')

        def cancel(self):
            self.cancelled = True

    rx = PlutoReceiver.__new__(PlutoReceiver)
    rx.buffer = BrokenBuffer()
    rx.bits, rx.shift = 12, 0
    transmitted = []
    with pytest.raises(RuntimeError, match='stream did not start'):
        rx.capture(lambda: transmitted.append(True))
    assert not transmitted and rx.buffer.cancelled


def test_reverse_simulation_stays_unverified_and_writes_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_sweep.main(['--sim', '--heltec-tx', '--profile', 'heltec_v4_3_sx1262',
                           '--out', str(tmp_path), '--no-plot']) == 0
    meta_path = next(tmp_path.glob('*/meta.json'))
    meta = json.loads(meta_path.read_text())
    assert meta['simulated'] is True and meta['evidence'] == 'SIMULATED'
    assert meta['direction'] == 'heltec-tx-pluto-rx'
    assert meta['dut']['tx']['ok'] is True
    summary = (meta_path.parent / 'summary.csv').read_text()
    assert 'UNVERIFIED' in summary and 'energy_only_packet_not_decoded' in summary
    assert (meta_path.parent / 'sha256.txt').is_file()
    assert (tmp_path / 'SX1262-SDR.log').is_file()


def test_reverse_hardware_requires_its_own_arm_flag(capsys):
    assert run_sweep.main(['--heltec-tx', '--no-plot']) == 2
    assert '--arm-heltec-tx' in capsys.readouterr().out


def test_nominal_exception_is_fixed_frequency_and_full_sweep_still_requires_filter(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert run_sweep.main(['--sim', '--nominal-check', '--freqs', '37,2450,3494',
                           '--out', str(tmp_path), '--no-plot']) == 0
    meta = json.loads(next(tmp_path.glob('*/meta.json')).read_text())
    assert meta['mode'] == 'nominal-915-only'
    assert {p['on']['frequency_hz'] for p in meta['probes']} == {915000000}
    assert [p['gain_db'] for p in meta['probes']] == [-80, -70, -60]
    assert run_sweep.main(['--arm-rf', '--no-plot']) == 2
    assert 'actual source output filter' in capsys.readouterr().out


def test_pll_only_never_enables_source_or_claims_receive_proof(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('RX-only survey attempted to enable Pluto TX')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_sweep.PlutoSource, 'set_tone', forbidden)
    assert run_sweep.main(['--sim', '--pll-only', '--freqs', '37,915,2450,2700,3494',
                           '--out', str(tmp_path), '--no-plot']) == 0
    meta = json.loads(next(tmp_path.glob('*/meta.json')).read_text())
    assert meta['mode'] == 'pll-only' and meta['simulated']
    assert len(meta['probes']) == 5
    assert any(p['errors'] & 0x40 for p in meta['probes'])
    assert {p['frequency_hz'] for p in meta['probes']} == {37000000,915000000,2450000000,2700000000,3494000000}


def test_receive_check_skips_pll_error_and_never_exceeds_attenuator_rating(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    original = run_sweep.PlutoSource.set_tone
    def record(source, hz, gain, *args, **kwargs):
        calls.append((hz, gain))
        return original(source, hz, gain, *args, **kwargs)
    monkeypatch.setattr(run_sweep.PlutoSource, 'set_tone', record)
    assert run_sweep.main(['--sim', '--receive-check', '--freqs', '915,2450,3000',
                           '--out', str(tmp_path), '--no-plot']) == 0
    assert len(calls) == 6
    assert {hz for hz, _ in calls} == {915020000, 3000000000}
    assert all(gain <= -60 for _, gain in calls)
    calls.clear()
    assert run_sweep.main(['--sim', '--receive-check', '--freqs', '3100',
                           '--out', str(tmp_path), '--no-plot']) == 1
    assert not calls


def test_gfsk_probe_uses_narrow_filter_and_validates_firmware_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_sweep.main(['--sim', '--nominal-check', '--gfsk-probe',
                           '--out', str(tmp_path), '--no-plot']) == 0
    meta = json.loads(next(tmp_path.glob('*/meta.json')).read_text())
    probe = meta['probes'][0]['on']
    assert probe['mode'] == 'gfsk' and probe['bandwidth_hz'] == 4800 and probe['reads'] == 8
    import dut_serial
    profile = dut_serial.load_profiles()['heltec_v4_3_sx1262']
    old = dut_serial.parse_heltec_info('SX1262-SDR fw=1.0 board=HTIT-WB32LAF-V4.3 fem=KCT8103L')
    assert not dut_serial.heltec_identity_matches(profile, old)


def test_receive_abort_preserves_partial_data_and_disables_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = run_sweep.Runner(run_sweep.load_config(), sim=True, out_root=str(tmp_path))
    original = runner.dut.run
    def fail(cmd, **kwargs):
        value = original(cmd, **kwargs)
        if cmd == 'probe' and runner.src.enabled:
            value['errors'] = 0x40
        return value
    monkeypatch.setattr(runner.dut, 'run', fail)
    try:
        with pytest.raises(RuntimeError, match='Invalid RX/status'):
            runner.run_nominal()
        assert not runner.src.enabled
        partial = json.loads((tmp_path / runner.run_id / 'partial.json').read_text())
        assert partial['status'] == 'aborted' and len(partial['probes']) == 1
        assert partial['probes'][0]['on']['errors'] == 0x40
    finally:
        runner.close()


def test_lower_offset_scan_moves_receiver_while_source_stays_fixed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    original = run_sweep.PlutoSource.set_tone
    def record(source, hz, gain, *args, **kwargs):
        calls.append((hz, gain))
        return original(source, hz, gain, *args, **kwargs)
    monkeypatch.setattr(run_sweep.PlutoSource, 'set_tone', record)
    assert run_sweep.main(['--sim', '--receive-check', '--gfsk-probe', '--freqs', '100',
                           '--sim-pluto-range', '46875001:6000000000', '--rx-offsets-khz=-5,0,135,225',
                           '--out', str(tmp_path), '--no-plot']) == 0
    meta = json.loads(next(tmp_path.glob('*/meta.json')).read_text())
    assert meta['rx_offsets_hz'] == [-5000, 0, 135000, 225000]
    assert {p['tune_hz'] for p in meta['probes']} == {99995000,100000000,100135000,100225000}
    assert {p['gain_db'] for p in meta['probes']} == {-60}
    assert calls == [(100001000, -60)] * 4
    assert run_sweep.main(['--sim', '--receive-check', '--gfsk-probe', '--freqs', '433.92',
                           '--rx-offsets-khz', '0,135', '--out', str(tmp_path), '--no-plot']) == 1
    assert run_sweep.main(['--sim', '--rx-offsets-khz', '135']) == 2


def test_below_published_boundary_is_rx_only_and_old_firmware_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('Source enabled during below-boundary survey')
    monkeypatch.setattr(run_sweep.PlutoSource, 'set_tone', forbidden)
    assert run_sweep.main(['--sim', '--pll-only', '--gfsk-probe', '--freqs', '25,36,37,45',
                           '--out', str(tmp_path), '--no-plot']) == 0
    import dut_serial
    profile = dut_serial.load_profiles()['heltec_v4_3_sx1262']
    assert profile['freq_min_hz'] == 1000000
    old = dut_serial.parse_heltec_info('SX1262-SDR fw=1.1 board=HTIT-WB32LAF-V4.3 fem=KCT8103L')
    assert not dut_serial.heltec_identity_matches(profile, old)


def test_fixed_receiver_moves_source_only_and_preserves_interlocks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_sweep.main(['--sim', '--receive-check', '--gfsk-probe',
                           '--freqs', '249.99975,250,250.00025', '--fixed-rx-mhz', '250.001',
                           '--sim-pluto-range', '46875001:6000000000',
                           '--out', str(tmp_path), '--no-plot']) == 0
    meta = json.loads(next(tmp_path.glob('*/meta.json')).read_text())
    assert meta['fixed_rx_hz'] == 250001000 and meta['scan_axis'] == 'source-frequency'
    assert {p['tune_hz'] for p in meta['probes']} == {250001000}
    assert {p['gain_db'] for p in meta['probes']} == {-60}
    assert {p['on']['_cmd'] for p in meta['probes']} == {'probe 250001000 20 gfsk'}
    for p in meta['probes']:
        assert p['source_state']['lo'] + 1000000 == p['frequency_hz'] + 1000
    assert run_sweep.main(['--sim', '--fixed-rx-mhz', '250.001']) == 2
    assert run_sweep.main(['--sim', '--receive-check', '--gfsk-probe',
                           '--fixed-rx-mhz', '250.001', '--rx-offsets-khz=0,1']) == 2
    assert run_sweep.main(['--sim', '--receive-check', '--gfsk-probe', '--freqs', '250',
                           '--sim-pluto-range', '46875001:6000000000',
                           '--fixed-rx-mhz', '251', '--out', str(tmp_path), '--no-plot']) == 1


def test_bounded_wide_gfsk_probe_reports_actual_bandwidth(tmp_path, monkeypatch):
    import dut_serial
    monkeypatch.chdir(tmp_path)
    for mode,bw in [('gfsk58',58600),('gfsk467',467000)]:
        d=dut_serial.Dut('heltec_v4_3_sx1262',sim_bench=__import__('sim').SimBench(),overrides={'probe_mode':mode})
        row=d.run('probe',freq_hz=99100000,dwell_ms=20)
        assert row['mode']=='gfsk' and row['bandwidth_hz']==bw
        assert row['reads']==8
        d.close()
    profile=dut_serial.load_profiles()['heltec_v4_3_sx1262']
    assert profile['required_firmware_identity']['firmware']=='1.8'
