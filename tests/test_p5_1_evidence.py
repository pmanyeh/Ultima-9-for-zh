"""Asset-free tests of the strict native diagnostic evidence verifier."""
from copy import deepcopy
import unittest

from scripts.verify_p5_1_runtime import verify_rows


def fixture():
    events = []
    def event(kind, address, identity, generation, entry=1, related=0):
        e = dict(seq=len(events)+1, tick_ms=(len(events)+1)*100, kind=kind, address=address,
                 identity=identity, generation=generation, entry=entry, related=related)
        if kind == 5: e.update(raster_hash_fnv1a64=123, width=16, height=22, stride_pixels=16)
        events.append(e)
    event(1,100,1,1); event(1,200,2,2,2); event(2,300,1,3,related=100)
    event(4,400,1,10,related=300); event(5,400,1,10); event(6,500,1,11,related=400)
    event(3,100,1,1); event(3,200,2,2,2); event(3,300,1,3)
    event(7,500,1,11,related=400); event(8,400,1,10)
    event(1,100,3,4); event(3,100,3,4); event(9,0,0,0,0)
    stats = dict(id=1, wide=2, cache=2, copies=1, layout=1, bounds=1, unicode_draws=1,
                 width_overrides=2, composites=5, raster=1, queue=1, raster_retired=1, queue_retired=1)
    c = dict(event='runtime_hooks_restored', milliseconds=2000, frames=10, composite_frames=5,
             errors=0, first_error=0, lifecycle_dropped=0, glyph_cache_entries=4, cache_misses=4,
             cache_hits=10, unlock_failures=0, lock_failures=0, surface_generation=1, skipped_frames=0,
             live_buffers=0, live_rasters=0, live_queues=0, lifecycle=events,
             entries=[stats, dict(id=2, cache=1)])
    return [dict(event='launcher_validated', runtime_version=0x10100, bits=32, debugger=False, runtime_sha256='a'*64),
            dict(event='runtime_ready', hooks=14, debugger_attached=False), dict(event='handshake_ready'),
            dict(event='game_resumed'), c,
            dict(event='runtime_cleanup', hooks_restored=True, private_font_removed=True,
                 worker_handles_closed=True, active_calls=0), dict(event='game_exited', exit_code=0)]


class EvidenceTests(unittest.TestCase):
    def verify(self, rows, **kwargs):
        return verify_rows(rows, required=(1,), **kwargs)

    def test_complete_multilifetime_and_address_reuse(self):
        result = self.verify(fixture())
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['address_reuses']['buffer'], 1)
        self.assertEqual(result['live_domains'], dict(buffer=0,raster=0,queue=0))

    def test_old_identity_generation_and_missing_source_rejected(self):
        for index, field, bad in [(11,'identity',1), (11,'generation',1), (2,'related',999), (9,'generation',99)]:
            rows = fixture(); rows[4]['lifecycle'][index][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError): self.verify(rows)

    def test_missing_retirement_or_sequence_rejected(self):
        rows = fixture(); rows[4]['lifecycle'].pop(9)
        with self.assertRaises(ValueError): self.verify(rows)
        rows = fixture(); rows[4]['lifecycle'][0]['seq'] = 2
        with self.assertRaises(ValueError): self.verify(rows)

    def test_crash_hook_error_cache_growth_and_bad_cleanup_rejected(self):
        for key, value in [('errors',1), ('glyph_cache_entries',5), ('cache_misses',5), ('unlock_failures',1), ('lifecycle_dropped',1)]:
            rows = fixture(); rows[4][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify(rows)
        rows = fixture(); rows[-1]['exit_code'] = 0xC0000005
        with self.assertRaises(ValueError): self.verify(rows)
        rows = fixture(); rows[-2]['private_font_removed'] = False
        with self.assertRaises(ValueError): self.verify(rows)

    def test_live_evidence_is_provisional_and_cannot_replace_exit(self):
        rows = fixture()[:5]
        self.assertEqual(self.verify(rows,live=True)['status'], 'PROVISIONAL LIVE')
        with self.assertRaises(ValueError): self.verify(rows)

    def test_duration_and_real_composite_activity_required(self):
        with self.assertRaises(ValueError): self.verify(fixture(), minimum_seconds=3)
        with self.assertRaises(ValueError): self.verify(fixture(), minimum_active_span=1)
        rows = fixture(); earlier = deepcopy(rows[4]); earlier['event'] = 'runtime_counters'
        earlier.update(milliseconds=1000, frames=5, composite_frames=2, cache_hits=5, lifecycle=[])
        # Put lifetime events in the earlier snapshot, no duplicate batch.
        events = rows[4]['lifecycle']
        earlier['lifecycle'], rows[4]['lifecycle'] = events[:6], events[6:]
        rows.insert(4, earlier)
        self.assertEqual(self.verify(rows)['unicode_appearance_span_ms'], 0)
        rows[5]['milliseconds'] = 1000000
        rows[5]['composite_frames'] = 2  # Time passing without new custom frames is insufficient.
        with self.assertRaises(ValueError): self.verify(rows, minimum_active_span=900)

    def test_invented_counter_and_ready_order_rejected(self):
        rows = fixture(); rows[4]['entries'][0]['copies'] = 9
        with self.assertRaises(ValueError): self.verify(rows)
        rows = fixture(); rows[1], rows[3] = rows[3], rows[1]
        with self.assertRaises(ValueError): self.verify(rows)


if __name__ == '__main__': unittest.main()
