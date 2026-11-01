"""Validate private native P5.1 JSONL evidence, including lifecycle generations.

This reads the runtime's own diagnostics, never game-process memory. Live output
is explicitly provisional; complete shutdown and duration gates require a closed
session. Event-driven gates impose no duration threshold. Historical duration
options remain available for analyzing the earlier batch. No copyrighted text
or pixel data is included in the summary.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = (4164, 4166, 4167, 4168, 4169)
FINAL_RUNTIME = '2e893bda781860455eacc33099ca0c9a334021d59c8880b728cabc4314e89b72'
TEST_RESOURCE = '138495860ff5804b19b9f413a2b6416fd5345e1adab7d8bd5dcb7f3353359842'


def verify_rows(rows, *, live=False, minimum_seconds=0, minimum_active_span=0, required=CORE):
    def need(value, message):
        if not value:
            raise ValueError(message)
    names = [r['event'] for r in rows]
    need(not live or 'game_exited' not in names, 'closed/interrupted session cannot be labelled live')
    need('runtime_ready' in names and 'game_resumed' in names, 'missing normal launch handshake')
    need(names.index('runtime_ready') < names.index('handshake_ready') < names.index('game_resumed'), 'READY order')
    need(not any(n in names for n in ('runtime_fail', 'launcher_fail', 'runtime_restore_failed')), 'failed session')
    header = next(r for r in rows if r['event'] == 'launcher_validated')
    need(header.get('runtime_version') == 0x10100 and header.get('bits') == 32 and header.get('debugger') is False,
         'unsupported runtime/debugger state')
    need(len(header.get('runtime_sha256', '')) == 64, 'missing runtime hash')
    ready = next(r for r in rows if r['event'] == 'runtime_ready')
    need(ready.get('hooks') == 14 and ready.get('debugger_attached') is False, 'hook/debugger readiness')
    counters = [r for r in rows if r['event'] in ('runtime_counters', 'runtime_hooks_restored')]
    need(bool(counters), 'missing counters')
    for c in counters:
        need(c['errors'] == 0 and c['first_error'] == 0 and c['lifecycle_dropped'] == 0, 'runtime/lifecycle fault')
        need(c['glyph_cache_entries'] == 4 and c['cache_misses'] == 4, 'glyph cache grew or missed after warm-up')
        need(c['unlock_failures'] == 0, 'failed Unlock')
        need(not any(e['kind'] == 9 for e in c['lifecycle']) or c['event'] == 'runtime_hooks_restored',
             'shutdown marker in a live counter batch')
    for a, b in zip(counters, counters[1:]):
        for key in ('milliseconds', 'frames', 'composite_frames', 'cache_hits'):
            need(b[key] >= a[key], 'non-monotonic counter: '+key)
    last = counters[-1]
    need(last['milliseconds'] >= minimum_seconds*1000, 'session duration below requested threshold')
    need(last['composite_frames'] > 0, 'no Unicode frames')
    entries = {r['id']: r for r in last['entries']}
    for entry in required:
        need(entry in entries, 'missing required entry')
        need(all(entries[entry].get(k, 0) > 0 for k in
                 ('wide', 'cache', 'copies', 'layout', 'bounds', 'unicode_draws', 'width_overrides', 'composites')),
             'incomplete entry route: '+str(entry))
    events = [event for row in counters for event in row['lifecycle']]
    domains = {'buffer': {}, 'raster': {}, 'queue': {}}
    seen_generations = defaultdict(set)
    seen_addresses = defaultdict(set)
    identities = set()
    reused = defaultdict(int)
    lifetimes = defaultdict(list)
    kind_counts = defaultdict(int)
    ready_ticks = []
    shutdown = False
    for sequence, event in enumerate(events, 1):
        need(event['seq'] == sequence, 'lifecycle sequence gap')
        kind, address = event['kind'], event['address']
        identity, generation, entry = event['identity'], event['generation'], event['entry']
        kind_counts[(entry, kind)] += 1
        if kind == 9:
            need(not shutdown, 'duplicate shutdown marker'); shutdown = True; continue
        need(identity > 0 and generation > 0 and address > 0, 'invalid lifecycle identity')
        if kind in (1, 2, 4, 6):
            need(not shutdown, 'new identity admitted during shutdown')
            domain = 'buffer' if kind in (1, 2) else 'raster' if kind == 4 else 'queue'
            need(address not in domains[domain], 'live address overwritten without retirement')
            need(generation not in seen_generations[domain], 'generation reused')
            if kind == 1:
                need(identity not in identities, 'constructor resurrected old identity')
                identities.add(identity)
            else:
                source_domain = 'buffer' if kind in (2, 4) else 'raster'
                source = domains[source_domain].get(event['related'])
                need(source is not None and (source['identity'], source['entry']) == (identity, entry),
                     'copy/raster/queue inheritance not proven')
            reused[domain] += address in seen_addresses[domain]
            seen_addresses[domain].add(address); seen_generations[domain].add(generation)
            domains[domain][address] = event
        elif kind == 5:
            source = domains['raster'].get(address)
            need(source is not None and (source['identity'], source['generation']) == (identity, generation),
                 'raster completion generation mismatch')
            need(event['raster_hash_fnv1a64'] > 0 and 0 < event['width'] <= event['stride_pixels'] <= 2048
                 and 0 < event['height'] <= 256, 'invalid completed raster identity')
            ready_ticks.append(event['tick_ms'])
        elif kind in (3, 7, 8):
            domain = {3: 'buffer', 7: 'queue', 8: 'raster'}[kind]
            previous = domains[domain].pop(address, None)
            need(previous is not None and (previous['identity'], previous['generation'], previous['entry']) ==
                 (identity, generation, entry), 'retirement generation mismatch')
            if domain == 'raster':
                need(not any(q['related'] == address for q in domains['queue'].values()), 'raster retired before queue')
            lifetime = event['tick_ms']-previous['tick_ms']
            need(lifetime >= 0, 'negative lifetime')
            lifetimes[(entry, domain)].append(lifetime)
        else:
            raise ValueError('unknown lifecycle event')
    for entry, stats in entries.items():
        for kind, field in ((1, 'cache'), (2, 'copies'), (5, 'raster'), (6, 'queue'),
                            (7, 'queue_retired'), (8, 'raster_retired')):
            need(kind_counts[(entry, kind)] == stats.get(field, 0), 'lifecycle/counter disagreement: '+field)
    # A positive sample delta proves composition happened inside that interval.
    # Use its lower boundary for the last interval and the upper boundary for
    # the first, giving a conservative bound independent of raster preparation.
    active_intervals = []
    previous_frames, previous_time = 0, 0
    for c in counters:
        if c['composite_frames'] > previous_frames:
            active_intervals.append((previous_time, c['milliseconds']))
        previous_frames, previous_time = c['composite_frames'], c['milliseconds']
    span = max(0, active_intervals[-1][0]-active_intervals[0][1]) if active_intervals else 0
    need(span >= minimum_active_span*1000, 'Unicode appearance span below requested threshold')
    if not live:
        need('runtime_hooks_restored' in names and 'runtime_cleanup' in names and 'game_exited' in names,
             'session not cleanly closed')
        cleanup = next(r for r in rows if r['event'] == 'runtime_cleanup')
        need(cleanup['hooks_restored'] and cleanup['private_font_removed'] and cleanup['worker_handles_closed']
             and cleanup['active_calls'] == 0, 'shutdown cleanup failed')
        need(rows[-1]['event'] == 'game_exited' and rows[-1]['exit_code'] == 0, 'abnormal process exit')
        need(shutdown and all(not d for d in domains.values()), 'unretired lifetime at exit')
        need(last['live_buffers'] == last['live_rasters'] == last['live_queues'] == 0, 'live bindings at exit')
    memory = [c['private_bytes'] for c in counters if c.get('milliseconds', 0) >= 120000 and c.get('private_bytes')]
    return {'status': 'PROVISIONAL LIVE' if live else 'PASS', 'runtime_sha256': header['runtime_sha256'],
            'duration_ms': last['milliseconds'], 'unicode_appearance_span_ms': span,
            'raster_creation_span_ms': max(ready_ticks)-min(ready_ticks) if ready_ticks else 0,
            'composite_frames': last['composite_frames'], 'glyph_cache_entries': last['glyph_cache_entries'],
            'cache_hits': last['cache_hits'], 'cache_misses': last['cache_misses'],
            'lifecycle_events': len(events), 'address_reuses': dict(reused),
            'live_domains': {k: len(v) for k, v in domains.items()},
            'surface_generation': last['surface_generation'], 'lock_failures': last['lock_failures'],
            'unlock_failures': last['unlock_failures'], 'skipped_frames': last['skipped_frames'],
            'private_bytes_after_2min_min_max': [min(memory), max(memory)] if memory else None,
            'entries': list(entries.values()),
            'lifetimes': [{'entry': entry, 'domain': domain, 'count': len(values),
                           'min_ms': min(values), 'max_ms': max(values)} for (entry, domain), values in lifetimes.items()]}


def verify_event_cycle(rows, receipt, *, repeated_entry=None, required=CORE):
    """Final-build normal exit and natural lifecycle events, without a clock gate."""
    def need(value, message):
        if not value: raise ValueError(message)
    result = verify_rows(rows, required=required)
    need(result['runtime_sha256'] == receipt['runtime_sha256'] == FINAL_RUNTIME, 'final runtime hash mismatch')
    need((receipt['width'], receipt['height']) in ((800,600),(1600,1200)), 'unsupported receipt resolution')
    need(receipt['presentation'] in ('windowed','fullscreen'), 'unsupported presentation')
    corpus = next((r for r in rows if r['event'] == 'runtime_corpus'), {})
    need(corpus.get('mode') == 'render' and corpus.get('resource_sha256') == receipt['resource_sha256'] == TEST_RESOURCE,
         'corpus hash/mode mismatch')
    counters = [r for r in rows if r['event'] in ('runtime_counters','runtime_hooks_restored')]
    need(counters[-1]['active_calls'] == 0, 'active hook during restoration')
    cleanup = next(r for r in rows if r['event'] == 'runtime_cleanup')
    need(cleanup.get('gateways_retained') is True, 'normal process-exit cleanup not established')
    events = [v for r in counters for v in r['lifecycle']]
    natural = []
    for e in events:
        if e['kind'] == 9: break
        natural.append(e)
    for entry in required:
        need(all(any(e['entry'] == entry and e['kind'] == kind for e in natural) for kind in (5,7,8)),
             'missing natural pre-shutdown raster/queue lifetime: '+str(entry))
    need(any(r['event'] == 'runtime_counters' and r['live_buffers'] == r['live_rasters'] == r['live_queues'] == 0
             and r['composite_frames'] > 0 for r in counters), 'missing post-render empty-binding event')
    warm = {(r['scalar'],r['em']):r for r in rows if r['event'] == 'glyph_cache_warm'}
    expected = {(20013,20):(9544,16,19,20),(20013,40):(9544,32,37,40),
                (25991,20):(20036,19,19,20),(25991,40):(20036,38,38,40)}
    need(set(warm) == set(expected), 'missing/extra physical glyph keys')
    for key, metrics in expected.items():
        need(tuple(warm[key][k] for k in ('index','width','height','advance')) == metrics
             and len(warm[key].get('coverage_sha256','')) == 64, 'unexpected direct glyph metrics')
    if repeated_entry is not None:
        for kind in (5,7,8):
            need(sum(e['kind'] == kind and e['entry'] == repeated_entry for e in natural) >= 2,
                 'repeat subtitle did not complete two natural lifetimes')
        epochs = set(); previous = 0
        for r in counters:
            stat = next((s for s in r['entries'] if s['id'] == repeated_entry), {})
            if stat.get('composites',0) > previous: epochs.add(stat.get('raster',0))
            previous = stat.get('composites',0)
        need(len(epochs) >= 2 and 0 not in epochs, 'repeat lifetimes lack compositor activity')
    result.update(gate='P5.1 event-driven v1',cycle=receipt['cycle'],width=receipt['width'],height=receipt['height'],
                  presentation=receipt['presentation'],normal_exit=True,natural_lifetimes_verified=True,
                  repeated_entry=repeated_entry,event_gate_pass=True)
    return result


def verify_event_matrix(cycles, observations, *, native_tests_passed, assets_restored):
    """Aggregate native log results plus separately recorded UI observations."""
    def need(value, message):
        if not value: raise ValueError(message)
    need(native_tests_passed and assets_restored, 'native regression/restoration incomplete')
    need(len(cycles) == 3 and len({c['cycle'] for c in cycles}) == 3, 'expected two short cycles and one fullscreen smoke')
    need(all(c.get('event_gate_pass') and c.get('normal_exit') and c.get('runtime_sha256') == FINAL_RUNTIME
             for c in cycles), 'unclean or mixed final builds')
    windowed = [c for c in cycles if c['presentation'] == 'windowed']
    need({(c['width'],c['height']) for c in windowed} == {(800,600),(1600,1200)} and len(windowed) == 2,
         'missing two windowed resolution cycles')
    full = [c for c in cycles if c['presentation'] == 'fullscreen']
    need(len(full) == 1 and (full[0]['width'],full[0]['height']) == (1600,1200), 'fullscreen smoke incomplete')
    need(any(c.get('repeated_entry') == 4170 for c in windowed), 'repeat lifecycle evidence missing')
    def observed(kind, cycle=None):
        return [o for o in observations if o['kind'] == kind and (cycle is None or o['cycle'] == cycle)]
    for c in cycles:
        need(observed('cjk_visible',c['cycle']), 'missing visual CJK observation')
    need(observed('native_ui_open') and observed('native_ui_cancel') and observed('interaction'), 'native UI/interaction smoke incomplete')
    for kind in ('fullscreen_visible','focus_loss','focus_restored','recovered_cjk'):
        need(observed(kind,full[0]['cycle']), 'fullscreen lifecycle observation missing: '+kind)
    losses = observed('focus_loss',full[0]['cycle'])
    need(any(o.get('anchor') and full[0]['composite_frames'] > o['anchor']['composite_frames'] for o in losses),
         'no new composition after fullscreen focus event')
    need(all(o.get('screenshot') and len(o.get('screenshot_sha256','')) == 64
             for o in observations if o['kind'] in ('cjk_visible','fullscreen_visible','recovered_cjk')),
         'missing visual artifact hashes')
    return {'status':'PASS','gate':'P5.1 event-driven v1','normal_cycles':2,'fullscreen_smokes':1,
            'runtime_sha256':FINAL_RUNTIME,'time_threshold_required':False,'actual_device_lost':'NOT OBSERVED',
            'scope':'selected subtitle corpus and pinned native/wrapper build; no P6 execution'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('log', type=Path)
    p.add_argument('--live', action='store_true')
    p.add_argument('--minimum-seconds', type=int, default=0)
    p.add_argument('--minimum-active-span', type=int, default=0)
    p.add_argument('--require-entry', type=int, action='append')
    p.add_argument('--output', type=Path)
    p.add_argument('--brief', action='store_true')
    p.add_argument('--event-config', type=Path, help='Use the event gate with this private launch receipt')
    p.add_argument('--repeat-entry', type=int, help='Require two natural display/retirement epochs for this entry')
    a = p.parse_args()
    data = a.log.read_bytes(); lines = data.splitlines()
    if a.live and data and not data.endswith(b'\n'): lines.pop()
    rows = [json.loads(line) for line in lines]
    if a.event_config:
        if a.live or a.minimum_seconds or a.minimum_active_span: p.error('event gate requires a closed session and no time threshold')
        result = verify_event_cycle(rows,json.loads(a.event_config.read_text()),
                                    repeated_entry=a.repeat_entry,required=a.require_entry or CORE)
    else:
        result = verify_rows(rows, live=a.live, minimum_seconds=a.minimum_seconds,
                             minimum_active_span=a.minimum_active_span, required=a.require_entry or CORE)
    result['evidence_sha256'] = hashlib.sha256(data).hexdigest()
    encoded = json.dumps(result, indent=2)+'\n'
    if a.output:
        if not a.output.resolve().is_relative_to((ROOT/'.local').resolve()): p.error('private .local output required')
        a.output.write_text(encoded, encoding='utf-8')
    if a.brief:
        print(result['status'], 'seconds='+str(round(result['duration_ms']/1000,3)),
              'custom_frames='+str(result['composite_frames']), 'reuses='+str(result['address_reuses']))
    else:
        print(encoded)


if __name__ == '__main__':
    main()
