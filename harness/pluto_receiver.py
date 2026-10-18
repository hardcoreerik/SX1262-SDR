# SPDX-License-Identifier: GPL-3.0-only
"""Bounded RX capture using the master runner's existing Pluto IIO context."""
from __future__ import annotations

import math
import threading
import time

import numpy as np


def block_metrics(raw, bits=12, shift=0):
    """Per-component RMS dBFS; never a calibrated RF power measurement."""
    values = np.frombuffer(raw, dtype='<i2')
    if values.size == 0 or values.size % 2:
        raise ValueError('RX buffer must contain complete interleaved I/Q pairs')
    values = (values.astype(np.int32) >> shift).astype(np.float64)
    fullscale = 2 ** (bits - 1)
    power = float(np.mean(values ** 2)) / fullscale ** 2
    return {'rms_dbfs': 10 * math.log10(max(power, 1e-20)),
            'clipped_fraction': float(np.mean((values >= fullscale - 1) | (values <= -fullscale))),
            'samples': values.size // 2}


class PlutoReceiver:
    def __init__(self, source, frequency_hz=915000000, port='A_BALANCED', gain_db=-3,
                 bandwidth_hz=1000000, buffer_samples=8192):
        if source.backend == 'sim':
            raise ValueError('Use the runner simulator, not a hardware RX context')
        source.disable()
        self.ctx, self.phy = source._ctx, source._phy
        self.dev = self.ctx.find_device('cf-ad9361-lpc')
        if self.dev is None:
            raise RuntimeError('Pluto RX DMA device not found')
        self.buffer = None
        self.saved = []
        self.channels = [(ch, ch.enabled) for ch in self.dev.channels if ch.scan_element]
        self.config = {'frequency_hz': int(frequency_hz), 'port': port,
                       'sample_rate_hz': 2500000, 'bandwidth_hz': bandwidth_hz, 'gain_db': gain_db}
        try:
            self.ctx.set_timeout(2000)
            lo = self.phy.find_channel('altvoltage0', True)
            rx = self.phy.find_channel('voltage0', False)
            if port not in rx.attrs['rf_port_select_available'].value.split():
                raise ValueError('Unsupported RX input port: %s' % port)
            for ch, name, value in ((lo, 'powerdown', 0), (lo, 'frequency', int(frequency_hz)),
                                    (rx, 'gain_control_mode', 'manual'), (rx, 'hardwaregain', gain_db),
                                    (rx, 'sampling_frequency', 2500000), (rx, 'rf_bandwidth', bandwidth_hz),
                                    (rx, 'rf_port_select', port)):
                attr = ch.attrs[name]
                old = attr.value
                self.saved.append((attr, old.split()[0] if name == 'hardwaregain' else old))
                try:
                    attr.value = str(value)
                except Exception as exc:
                    raise RuntimeError('Cannot set Pluto RX %s=%s: %s' % (name, value, exc)) from exc
            for ch, _ in self.channels:
                ch.enabled = ch.id in ('voltage0', 'voltage1')
            fmt = self.dev.find_channel('voltage0', False).data_format
            if fmt.length != 16 or not fmt.is_signed or fmt.is_be:
                raise RuntimeError('Unsupported Pluto RX sample format')
            self.bits, self.shift = fmt.bits, fmt.shift
            for key, attr in (('sample_rate_hz', 'sampling_frequency'), ('bandwidth_hz', 'rf_bandwidth'),
                              ('gain_db', 'hardwaregain')):
                self.config[key] = float(rx.attrs[attr].value.split()[0])
            import iio
            self.buffer = iio.Buffer(self.dev, buffer_samples, False)
        except BaseException:
            self.close()
            raise

    def capture(self, trigger=None):
        """Read continuously before/during/after one trigger; cancel on every exit."""
        rows, errors = [], []
        stop, ready = threading.Event(), threading.Event()
        start = time.monotonic()

        def read():
            try:
                while not stop.is_set():
                    self.buffer.refill()
                    row = block_metrics(self.buffer.read(), self.bits, self.shift)
                    row['elapsed_s'] = time.monotonic() - start
                    rows.append(row)
                    ready.set()
            except Exception as exc:
                if not stop.is_set():
                    errors.append(exc)
                ready.set()

        worker = threading.Thread(target=read, daemon=True)
        worker.start()
        result = None
        trigger_start = trigger_end = None
        try:
            if not ready.wait(3) or errors:
                raise RuntimeError('Pluto RX stream did not start: %s' % errors)
            time.sleep(0.35)
            if errors or not worker.is_alive() or len(rows) < 3:
                raise RuntimeError('Pluto RX stream stopped before trigger: %s' % errors)
            trigger_start = time.monotonic() - start
            if trigger:
                result = trigger()
            trigger_end = time.monotonic() - start
            time.sleep(0.5)
        finally:
            stop.set()
            self.buffer.cancel()
            worker.join(3)
        if worker.is_alive():
            raise RuntimeError('Pluto RX worker did not stop')
        if errors:
            raise RuntimeError('Pluto RX stream failed: %s' % errors)
        if not rows:
            raise RuntimeError('Pluto RX stream returned no samples')
        for row in rows:
            t = row['elapsed_s']
            row['phase'] = ('baseline' if t < trigger_start else
                            'post' if t > trigger_end + 0.15 else 'trigger')
        return rows, result

    def close(self):
        if self.buffer is not None:
            self.buffer.cancel()
            self.buffer = None
        errors = []
        for ch, enabled in self.channels:
            try:
                ch.enabled = enabled
            except Exception as exc:
                errors.append(str(exc))
        for attr, value in reversed(self.saved):
            try:
                attr.value = value
            except Exception as exc:
                errors.append(str(exc))
        self.saved.clear()
        if errors:
            raise RuntimeError('Pluto RX state restoration failed: ' + '; '.join(errors))
