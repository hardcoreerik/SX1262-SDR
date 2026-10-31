# SPDX-License-Identifier: GPL-3.0-only
"""Receive-only RSSI timing experiment, invoked by the single run_sweep runner."""
import hashlib
import json
import datetime as dt
import wave
from pathlib import Path
import numpy as np
from dut_serial import heltec_identity_matches
from contextlib import nullcontext


def timing_metrics(timestamps, requested_rate):
    t = np.asarray(timestamps, dtype=np.int64)
    if t.ndim != 1 or len(t) < 2 or np.any(np.diff(t) <= 0):
        raise ValueError('Capture timestamps must strictly increase')
    intervals = np.diff(t)
    rate = float((len(t)-1)*1e6/(t[-1]-t[0]))
    period = 1e6/requested_rate
    in_band = float(np.mean(abs(intervals-period) <= period*.1))
    return {'achieved_rate_hz': rate, 'requested_rate_hz': requested_rate,
            'n': len(t), 'interval_min_us': int(intervals.min()),
            'interval_median_us': float(np.median(intervals)),
            'interval_max_us': int(intervals.max()), 'intervals_within_10pct': in_band,
            'voice_timing_gate': bool(rate >= 8000 and in_band >= .99 and len(t) == requested_rate)}


def capture_record(dut, out, stem, frequency_hz, bw, rate, fem_mode='auto'):
    r = dut.run('capture', capture_hz=frequency_hz, capture_bw=bw, capture_rate=rate, capture_fem=fem_mode)
    (out/(stem+'.serial.txt')).write_text(dut.last_raw, encoding='utf-8')
    if not r.get('_done') or not r.get('ok') or r.get('rate_hz') != rate or r.get('bandwidth_hz') != bw or r.get('frequency_hz') != frequency_hz or r.get('fem_mode') != fem_mode:
        raise RuntimeError('Invalid rapid capture; stopped at '+stem)
    data = r['data']
    (out/(stem+'.bin')).write_bytes(data)
    v = np.frombuffer(data, dtype=np.dtype([('us','<u4'),('rssi','u1'),('pcm','<i2')]))
    metrics = timing_metrics(v['us'], rate)
    metrics.update(bandwidth_hz=bw, median_rssi_dbm=float(np.median(-v['rssi'].astype(float)/2)),
                   identical_adjacent_rssi_fraction=float(np.mean(v['rssi'][1:]==v['rssi'][:-1])),
                   evidence='RSSI_OBSERVED', stem=stem, fem_mode=fem_mode)
    np.savetxt(out/(stem+'.csv'), np.column_stack((v['us'], v['rssi'], v['pcm'])),
               delimiter=',', header='completion_us,rssi_raw,device_pcm', comments='', fmt='%d')
    # Requested playback clock is explicitly separate from measured timing.
    with wave.open(str(out/(stem+'-envelope-requested-clock.wav')), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(v['pcm'].astype('<i2').tobytes())
    return metrics


def run_capture(runner):
    if runner.sim:
        raise ValueError('Rapid RSSI capture is hardware-only; no simulated RF evidence')
    out = Path(runner.out)
    src, dut = runner.src, runner.dut
    meta = {'simulated': False, 'mode': 'heltec-rapid-rssi', 'frequency_hz': 99100000,
            'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'config': runner.cfg, 'captures': [], 'status': 'started',
            'limitations': 'RSSI envelope PCM, not decoded FM or I/Q. Load baseline; no source-correlated reception or calibrated power. SPI read cadence does not establish internal RSSI update bandwidth.'}
    try:
        src.disable()
        if src.backend != 'iio' or src._phy.find_channel('altvoltage1', True).attrs['powerdown'].value != '1':
            raise RuntimeError('Pluto TX OFF readback failed')
        info = dut.info()
        meta['dut_info'] = info
        meta['pluto'] = src.describe()
        if not heltec_identity_matches(dut.p, info):
            raise RuntimeError('Heltec firmware identity mismatch')
        for bw in (58600, 467000):
            for rate in (1000, 2000, 4000, 8000):
                stem = '%dHz-%dsps' % (bw, rate)
                metrics = capture_record(dut, out, stem, 99100000, bw, rate)
                meta['captures'].append(metrics)
                runner.log('%s: achieved %.1f reads/s, timing gate=%s' %
                           (stem, metrics['achieved_rate_hz'], metrics['voice_timing_gate']))
        meta['status'] = 'completed'
    except BaseException as exc:
        meta['error'] = str(exc)
        meta['status'] = 'aborted'
        raise
    finally:
        try:
            stopped = dut.run('stop')
            meta['stop'] = stopped
            if not stopped.get('_done') or stopped.get('ok') != '1':
                raise RuntimeError('Heltec standby not confirmed')
        finally:
            src.disable()
            meta['pluto_tx_powerdown'] = src._phy.find_channel('altvoltage1', True).attrs['powerdown'].value
            meta['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
            (out/'meta.json').write_text(json.dumps(meta, indent=2, default=str))
            manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()
                        if p.is_file() and p.name not in ('sha256.json', 'run.log')}
            (out/'sha256.json').write_text(json.dumps(manifest, indent=2))
    return runner.out, []


def run_offair(runner):
    """Receive-only candidate captures; never label envelope noise as decoded FM."""
    if runner.sim: raise ValueError('Off-air capture is hardware-only')
    src,dut,out=runner.src,runner.dut,Path(runner.out)
    freqs=[int(round(float(f)*1e6)) for f in runner.cfg['sweep']['frequencies_mhz']]
    settings=runner.cfg.get('offair_fm',{})
    reps=settings.get('reps',1);bands=settings.get('bandwidths_hz',[58600,467000])
    modes=settings.get('fem_modes',['auto'])
    if not 1<=len(freqs)<=30 or any(not 88000000<=f<=108000000 for f in freqs):
        raise ValueError('Off-air captures require <=30 frequencies in88–108MHz')
    if not isinstance(reps,int) or not 1<=reps<=5 or not bands or any(b not in (58600,467000) for b in bands):
        raise ValueError('Invalid bounded off-air capture settings')
    if not modes or len(modes)>2 or len(set(modes))!=len(modes) or any(m not in ('auto','lna') for m in modes):
        raise ValueError('Invalid RX FEM comparison modes')
    meta={'simulated':False,'mode':'heltec-offair-fm-candidates','status':'started',
          'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'config':runner.cfg,'captures':[],
          'limitations':'Receive-only RSSI envelope PCM. Candidate energy/audio statistics are not station identification or broadcast FM decoding. No raw IQ. Antenna/path/power and tuning accuracy uncalibrated.'}
    try:
        src.disable()
        if src.backend!='iio' or src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value!='1':
            raise RuntimeError('Pluto TX OFF not confirmed')
        meta['dut_info']=dut.info();meta['pluto']=src.describe()
        if not heltec_identity_matches(dut.p,meta['dut_info']):raise RuntimeError('Heltec firmware identity mismatch')
        for hz in freqs:
            for bw in bands:
                for rep in range(1,reps+1):
                    for mode in modes:
                        stem='%dHz-%dBW-rep%d-%s'%(hz,bw,rep,mode)
                        c=capture_record(dut,out,stem,hz,bw,8000,fem_mode=mode)
                        c.update(frequency_hz=hz,rep=rep)
                        meta['captures'].append(c)
                        if c['n']!=8000 or c['intervals_within_10pct']<.99:
                            raise RuntimeError('Off-air capture cadence failed')
                        runner.log('%.5fMHz BW%d %s: RSSI %.1fdBm; captured device envelope, station unverified'%(hz/1e6,bw,mode,c['median_rssi_dbm']))
        meta['status']='completed'
    except BaseException as exc:
        meta.update(status='aborted',error=str(exc));raise
    finally:
        src.disable()
        try:
            meta['stop']=dut.run('stop')
            if not meta['stop'].get('_done') or meta['stop'].get('ok')!='1':raise RuntimeError('Heltec standby not confirmed')
        finally:
            src.disable()
            meta['final_powerdown']=src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value
            meta['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
            (out/'offair.json').write_text(json.dumps(meta,indent=2,default=str))
            manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name not in ('sha256.json','run.log')}
            (out/'sha256.json').write_text(json.dumps(manifest,indent=2))
    return runner.out,[]


def tone_metrics(timestamps, rssi_raw, frequency):
    """Fit the expected tone on real timestamps; compare against nearby spectrum."""
    t = np.asarray(timestamps, dtype=float)/1e6
    y = -np.asarray(rssi_raw, dtype=float)/2
    keep = t >= t[0]+.05
    t, y = t[keep], y[keep]
    if len(t) < 100: raise ValueError('Insufficient tone samples')
    phase = 2*np.pi*frequency*t
    a = np.column_stack((np.ones(len(t)), np.sin(phase), np.cos(phase)))
    coeff = np.linalg.lstsq(a, y, rcond=None)[0]
    amplitude = float(np.hypot(coeff[1], coeff[2]))
    fs = (len(t)-1)/(t[-1]-t[0])
    # FFT peak test is eligible only when the timestamp cadence is also valid.
    power = abs(np.fft.rfft((y-y.mean())*np.hanning(len(y))))**2
    f = np.fft.rfftfreq(len(y), 1/fs)
    target = abs(f-frequency) <= 3
    nearby = (abs(f-frequency) >= 20) & (abs(f-frequency) <= 150)
    snr = float(10*np.log10(max(float(power[target].max()),1e-20)/max(float(np.median(power[nearby])),1e-20)))
    return {'tone_hz': frequency, 'fit_amplitude_db': amplitude, 'peak_over_local_floor_db': snr,
            'median_rssi_dbm': float(np.median(y)), 'uncalibrated': True}


def run_modulation(runner):
    """Five conducted AM response repetitions; fixed settings, no FM claim."""
    if runner.sim: raise ValueError('Modulation capture is hardware-only')
    src, dut, out = runner.src, runner.dut, Path(runner.out)
    meta = {'simulated': False, 'mode': 'conducted-am-rssi-response', 'status': 'started',
            'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'config': runner.cfg,
            'captures': [], 'frequency_hz': 250001000, 'repetitions': 5,
            'thresholds': {'carrier_delta_db': 6, 'tone_fit_db': 1, 'tone_over_off_ratio': 3,
                           'peak_over_local_floor_db': 10, 'intervals_within_10pct': .99},
            'limitations': 'AM envelope response only. Absolute RF power, spectral purity, physical LO and internal RSSI update bandwidth not independently calibrated. No FM discriminator or raw IQ.'}
    try:
        src.disable()
        if src.backend != 'iio' or src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value != '1':
            raise RuntimeError('Pluto TX OFF not confirmed')
        meta['dut_info'] = dut.info()
        meta['pluto'] = src.describe()
        if not heltec_identity_matches(dut.p, meta['dut_info']):
            raise RuntimeError('Heltec firmware identity mismatch')
        for rep in range(5):
            off = None
            carrier = None
            for modulation in (None, 0, 300, 1000, 2500, None):
                phase = 'off-before' if modulation is None and off is None else 'off-after' if modulation is None else 'carrier' if modulation == 0 else 'am%d' % modulation
                stem = 'rep%d-%s' % (rep+1, phase)
                src.disable()
                context = nullcontext({'tx': 'OFF'}) if modulation is None else src.am_burst(modulation)
                with context as source:
                    metrics = capture_record(dut,out,stem,250001000,58600,8000)
                if src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value != '1':
                    raise RuntimeError('Pluto shutdown readback failed')
                metrics.update(rep=rep+1,phase=phase,source=source)
                v = np.frombuffer((out/(stem+'.bin')).read_bytes(),dtype=np.dtype([('us','<u4'),('rssi','u1'),('pcm','<i2')]))
                metrics['tones'] = {str(f): tone_metrics(v['us'],v['rssi'],f) for f in (300,1000,2500)}
                meta['captures'].append(metrics)
                if metrics['n'] != 8000 or metrics['intervals_within_10pct'] < .99:
                    raise RuntimeError('Capture cadence failed; stage stopped')
                if phase == 'off-before': off = metrics
                elif phase == 'carrier':
                    carrier = metrics
                    delta = carrier['median_rssi_dbm']-off['median_rssi_dbm']
                    metrics['source_delta_db'] = delta
                    if delta < 6: raise RuntimeError('Carrier uncorrelated; stage stopped')
                elif modulation:
                    tone = metrics['tones'][str(modulation)]
                    baseline = off['tones'][str(modulation)]['fit_amplitude_db']
                    metrics['tone_over_off_ratio'] = tone['fit_amplitude_db']/max(baseline,1e-9)
                    if tone['fit_amplitude_db'] < 1 or tone['peak_over_local_floor_db'] < 10 or metrics['tone_over_off_ratio'] < 3:
                        raise RuntimeError('AM tone uncorrelated; stage stopped')
                elif phase == 'off-after' and metrics['median_rssi_dbm'] > off['median_rssi_dbm']+3:
                    raise RuntimeError('Source OFF baseline did not recover')
                runner.log('%s: RSSI %.1f dBm; %.1f reads/s' % (stem,metrics['median_rssi_dbm'],metrics['achieved_rate_hz']))
        meta['status'] = 'completed'
    except BaseException as exc:
        meta['status'] = 'aborted'
        meta['error'] = str(exc)
        raise
    finally:
        src.disable()
        try:
            meta['stop'] = dut.run('stop')
            if not meta['stop'].get('_done') or meta['stop'].get('ok') != '1':
                raise RuntimeError('Heltec standby not confirmed')
        finally:
            src.disable()
            meta['final_powerdown'] = src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value
            meta['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
            (out/'modulation.json').write_text(json.dumps(meta,indent=2,default=str))
            manifest = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name not in ('sha256.json','run.log')}
            (out/'sha256.json').write_text(json.dumps(manifest,indent=2))
    return runner.out, []


def run_fm_slope(runner):
    """Exploratory source offset screen, then five confirmations at best slope."""
    if runner.sim: raise ValueError('FM slope capture is hardware-only')
    src, dut, out = runner.src, runner.dut, Path(runner.out)
    meta = {'simulated':False, 'mode':'conducted-fm-slope', 'status':'started',
            'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'config':runner.cfg,
            'receiver_hz':250001000, 'bandwidth_hz':58600, 'deviation_hz':5000,
            'captures':[], 'screen':[], 'confirmations':[],
            'thresholds':{'source_delta_db':6, 'fit_amplitude_db':1,
                          'peak_over_local_floor_db':10, 'tone_over_off_and_cw_ratio':3},
            'limitations':'Exploratory offset selection followed by repeats. Digital constant envelope does not certify physical RF purity. No independent source AM measurement or synchronized slope-phase inversion proof. Not broadcast FM or direct99.1MHz reception.'}
    def capture(stem, offset=None, tone=0):
        src.disable()
        context = nullcontext({'tx':'OFF'}) if offset is None else src.fm_burst(tone,offset)
        with context as state:
            c = capture_record(dut,out,stem,250001000,58600,8000)
        if src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value != '1':
            raise RuntimeError('FM source shutdown not confirmed')
        v = np.frombuffer((out/(stem+'.bin')).read_bytes(),dtype=np.dtype([('us','<u4'),('rssi','u1'),('pcm','<i2')]))
        c['tones'] = {str(f):tone_metrics(v['us'],v['rssi'],f) for f in (1000,2500)}
        c.update(source=state,phase=stem)
        meta['captures'].append(c)
        if c['n'] != 8000 or c['intervals_within_10pct'] < .99:
            raise RuntimeError('FM capture cadence failed')
        runner.log('%s: RSSI %.1f dBm, 1kHz fit %.2f dB' %
                   (stem,c['median_rssi_dbm'],c['tones']['1000']['fit_amplitude_db']))
        return c
    def compare(fm,cw,off,tone):
        a=fm['tones'][str(tone)]; base=max(cw['tones'][str(tone)]['fit_amplitude_db'],off['tones'][str(tone)]['fit_amplitude_db'],1e-9)
        ratio=a['fit_amplitude_db']/base
        return {'fit_amplitude_db':a['fit_amplitude_db'], 'tone_over_controls_ratio':ratio,
                'peak_over_local_floor_db':a['peak_over_local_floor_db'],
                'pass':bool(a['fit_amplitude_db']>=1 and ratio>=3 and a['peak_over_local_floor_db']>=10)}
    try:
        src.disable()
        if src.backend != 'iio' or src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value != '1':
            raise RuntimeError('Pluto TX OFF not confirmed')
        meta['dut_info']=dut.info();meta['pluto']=src.describe()
        if not heltec_identity_matches(dut.p,meta['dut_info']):raise RuntimeError('Heltec firmware identity mismatch')
        off=capture('screen-off-before')
        anchor=capture('screen-center-carrier',0)
        if anchor['median_rssi_dbm']-off['median_rssi_dbm']<6:
            raise RuntimeError('Anchor source uncorrelated; FM stage stopped')
        for offset in (0,-10000,10000,-20000,20000,-30000,30000,-40000,40000):
            cw=anchor if offset==0 else capture('screen-%+d-carrier'%offset,offset)
            delta=cw['median_rssi_dbm']-off['median_rssi_dbm']
            row={'offset_hz':offset,'carrier_delta_db':delta,'carrier_median_rssi_dbm':cw['median_rssi_dbm']}
            meta['screen'].append(row)
            if delta<6:
                row.update(eligible=False,reason='outside_source_correlated_response');continue
            fm=capture('screen-%+d-fm1000'%offset,offset,1000)
            row.update(eligible=True,**compare(fm,cw,off,1000))
        after=capture('screen-off-after')
        if abs(after['median_rssi_dbm']-off['median_rssi_dbm'])>3:
            raise RuntimeError('Screen source-OFF baseline did not recover')
        candidates=[r for r in meta['screen'] if r.get('pass')]
        if candidates:
            best=max(candidates,key=lambda r:r['fit_amplitude_db'])
            offset=best['offset_hz'];meta['selected_offset_hz']=offset
            for rep in range(1,6):
                off=capture('confirm%d-off-before'%rep)
                cw=capture('confirm%d-carrier'%rep,offset)
                if cw['median_rssi_dbm']-off['median_rssi_dbm']<6:
                    raise RuntimeError('Confirmation carrier uncorrelated')
                for tone in (1000,2500):
                    fm=capture('confirm%d-fm%d'%(rep,tone),offset,tone)
                    check=compare(fm,cw,off,tone)
                    meta['confirmations'].append({'rep':rep,'tone_hz':tone,**check})
                    if not check['pass']:raise RuntimeError('FM confirmation tone uncorrelated; stage stopped')
                after=capture('confirm%d-off-after'%rep)
                if abs(after['median_rssi_dbm']-off['median_rssi_dbm'])>3:
                    raise RuntimeError('Confirmation source-OFF baseline did not recover')
        meta['result']='FM_TONE_CORRELATED_IN_CONDUCTED_SETUP' if candidates else 'NO_OFFSET_MET_SCREEN_THRESHOLDS'
        meta['status']='completed'
    except BaseException as exc:
        meta.update(status='aborted',error=str(exc));raise
    finally:
        src.disable()
        try:
            meta['stop']=dut.run('stop')
            if not meta['stop'].get('_done') or meta['stop'].get('ok')!='1':raise RuntimeError('Heltec standby not confirmed')
        finally:
            src.disable()
            meta['final_powerdown']=src._phy.find_channel('altvoltage1',True).attrs['powerdown'].value
            meta['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
            (out/'fm-slope.json').write_text(json.dumps(meta,indent=2,default=str))
            manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name not in ('sha256.json','run.log')}
            (out/'sha256.json').write_text(json.dumps(manifest,indent=2))
    return runner.out,[]
