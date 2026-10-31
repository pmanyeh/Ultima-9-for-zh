"""Validate private native P5.1 JSONL evidence, including lifecycle generations.

This reads the runtime's own diagnostics, never game-process memory. Live output
is explicitly provisional; complete shutdown and duration gates require a closed
session. No copyrighted text or pixel data is included in the summary.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = (4164, 4166, 4167, 4168, 4169)


def verify_rows(rows, *, live=False, minimum_seconds=0, minimum_active_span=0, required=CORE):
    def need(value, message):
        if not value:
            raise ValueError(message)
    names = [r['event'] for r in rows]
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('log', type=Path)
    p.add_argument('--live', action='store_true')
    p.add_argument('--minimum-seconds', type=int, default=0)
    p.add_argument('--minimum-active-span', type=int, default=0)
    p.add_argument('--require-entry', type=int, action='append')
    p.add_argument('--output', type=Path)
    p.add_argument('--brief', action='store_true')
    a = p.parse_args()
    data = a.log.read_bytes(); lines = data.splitlines()
    if a.live and data and not data.endswith(b'\n'): lines.pop()
    rows = [json.loads(line) for line in lines]
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
