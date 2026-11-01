"""Synthetic event-gate evidence only; no game/font files or duration waits."""
from copy import deepcopy
import unittest

from scripts.verify_p5_1_runtime import FINAL_RUNTIME, TEST_RESOURCE, verify_event_cycle, verify_event_matrix
from tests.test_p5_1_evidence import fixture


def event_fixture(repeat=False):
    rows = fixture(); rows[0]['runtime_sha256'] = FINAL_RUNTIME
    original = rows[4]; events = original['lifecycle']
    pre = deepcopy(original); pre.update(event='runtime_counters',milliseconds=0,active_calls=0)
    original.update(milliseconds=0,active_calls=0)
    rows[-2]['gateways_retained'] = True
    if repeat:
        events = events[:12]
        def add(kind,address,generation,related=0):
            e = dict(seq=0,tick_ms=(len(events)+1)*100,kind=kind,address=address,
                     identity=3,generation=generation,entry=1,related=related)
            if kind == 5: e.update(raster_hash_fnv1a64=321,width=16,height=22,stride_pixels=16)
            events.append(e)
        add(2,300,5,100);add(4,400,12,300);add(5,400,12);add(6,500,13,400)
        add(3,300,5);add(7,500,13,400);add(8,400,12);add(3,100,4)
        events.append(dict(seq=0,tick_ms=3000,kind=9,address=0,identity=0,generation=0,entry=0))
        for i,e in enumerate(events,1):e['seq']=i
        pre['lifecycle']=events[:11];original['lifecycle']=events[11:]
        pre['entries'][0].update(cache=1)
        original['entries'][0].update(copies=2,raster=2,queue=2,raster_retired=2,queue_retired=2,composites=10)
        original.update(composite_frames=10,frames=20,cache_hits=20)
    else:
        pre['lifecycle']=events[:-1];original['lifecycle']=events[-1:]
    rows.insert(4,pre)
    corpus=dict(event='runtime_corpus',mode='render',resource_sha256=TEST_RESOURCE)
    warm=[]
    for scalar,em,index,w,h in [(20013,20,9544,16,19),(20013,40,9544,32,37),
                                 (25991,20,20036,19,19),(25991,40,20036,38,38)]:
        warm.append(dict(event='glyph_cache_warm',scalar=scalar,em=em,index=index,width=w,height=h,
                         advance=em,coverage_sha256='a'*64))
    rows[1:1]=[corpus]+warm
    receipt=dict(cycle='synthetic',width=800,height=600,presentation='windowed',
                 runtime_sha256=FINAL_RUNTIME,resource_sha256=TEST_RESOURCE)
    return rows,receipt


def matrix_fixture():
    cycles=[];obs=[]
    for name,w,h,mode in [('a',800,600,'windowed'),('b',1600,1200,'windowed'),('f',1600,1200,'fullscreen')]:
        cycles.append(dict(cycle=name,width=w,height=h,presentation=mode,event_gate_pass=True,normal_exit=True,
                           runtime_sha256=FINAL_RUNTIME,repeated_entry=4170 if name=='b' else None,composite_frames=20))
        obs.append(dict(cycle=name,kind='cjk_visible',screenshot='.local/synthetic.png',screenshot_sha256='a'*64))
    for kind in ['fullscreen_visible','focus_loss','focus_restored','recovered_cjk','native_ui_open','native_ui_cancel','interaction']:
        obs.append(dict(cycle='f',kind=kind,anchor=dict(composite_frames=10),
                        screenshot='.local/synthetic.png',screenshot_sha256='a'*64))
    return cycles,obs


class EventGateTests(unittest.TestCase):
    def test_complete_events_pass_without_elapsed_time(self):
        rows,receipt=event_fixture()
        result=verify_event_cycle(rows,receipt,required=(1,))
        self.assertTrue(result['normal_exit']);self.assertEqual(result['duration_ms'],0)

    def test_two_display_epochs_required_for_replay(self):
        rows,receipt=event_fixture()
        with self.assertRaises(ValueError):verify_event_cycle(rows,receipt,repeated_entry=1,required=(1,))
        rows,receipt=event_fixture(repeat=True)
        self.assertTrue(verify_event_cycle(rows,receipt,repeated_entry=1,required=(1,))['event_gate_pass'])

    def test_wrong_build_font_active_call_and_corpus_rejected(self):
        for mutate in [lambda r,c:c.update(runtime_sha256='b'*64),
                       lambda r,c:next(x for x in r if x['event']=='glyph_cache_warm').update(width=99),
                       lambda r,c:next(x for x in r if x['event']=='runtime_hooks_restored').update(active_calls=1),
                       lambda r,c:c.update(resource_sha256='b'*64)]:
            rows,receipt=event_fixture();mutate(rows,receipt)
            with self.assertRaises(ValueError):verify_event_cycle(rows,receipt,required=(1,))

    def test_shutdown_only_retirement_cannot_substitute_for_natural_end(self):
        rows,receipt=event_fixture()
        packets=[r for r in rows if r['event'] in ('runtime_counters','runtime_hooks_restored')]
        events=packets[0]['lifecycle']+packets[1]['lifecycle']
        ends=[e for e in events if e['kind'] in (7,8)]
        events=[e for e in events if e['kind'] not in (7,8)]+ends
        for i,e in enumerate(events,1):e['seq']=i
        packets[0]['lifecycle']=[];packets[1]['lifecycle']=events
        with self.assertRaises(ValueError):verify_event_cycle(rows,receipt,required=(1,))

    def test_complete_matrix_and_missing_fullscreen_focus_rejected(self):
        cycles,obs=matrix_fixture()
        self.assertEqual(verify_event_matrix(cycles,obs,native_tests_passed=True,assets_restored=True)['status'],'PASS')
        for kind in ['fullscreen_visible','focus_loss','focus_restored','recovered_cjk']:
            reduced=[o for o in obs if o['kind']!=kind]
            with self.assertRaises(ValueError):verify_event_matrix(cycles,reduced,native_tests_passed=True,assets_restored=True)

    def test_unclean_cycle_or_no_recovery_composition_rejected(self):
        cycles,obs=matrix_fixture();cycles[0]['normal_exit']=False
        with self.assertRaises(ValueError):verify_event_matrix(cycles,obs,native_tests_passed=True,assets_restored=True)
        cycles,obs=matrix_fixture();cycles[2]['composite_frames']=10
        with self.assertRaises(ValueError):verify_event_matrix(cycles,obs,native_tests_passed=True,assets_restored=True)


if __name__=='__main__':unittest.main()
