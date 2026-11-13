#!/usr/bin/env python3
"""Check reusable teaching-event invariants without claiming semantic approval."""
import argparse
import json
from pathlib import Path


def check(data, rules):
    errors = []
    duration = data['duration']
    captions = {c['id']: c for c in data['captions']}
    rule_ids = {r['id'] for r in rules}
    seen = set()
    for event in data['events']:
        ident = event['id']
        if ident in seen:
            errors.append(f'{ident}: duplicate event')
        seen.add(ident)
        start, settled, end = (event[k] for k in ('start', 'settled', 'end'))
        if not 0 <= start <= settled < end <= duration:
            errors.append(f'{ident}: invalid event window')
        cap = captions.get(event['narration_id'])
        if not cap or not cap['start'] <= event['anchor_time'] < cap['end']:
            errors.append(f'{ident}: anchor outside linked narration')
        if abs(start - event['anchor_time']) > 0.25:
            errors.append(f'{ident}: event not aligned to anchor')
        if not event['rule_ids'] or set(event['rule_ids']) - rule_ids:
            errors.append(f'{ident}: missing or unknown source rules')
        # Short persistent labels are distinct from fast sequential subtitles.
        required = max(1.2, event.get('reading_chars', 0) * .15 + .5)
        if end - settled < required:
            errors.append(f'{ident}: readable hold {end-settled:.2f}s < {required:.2f}s')
    ordered = sorted(data['captions'], key=lambda c: c['start'])
    for i, cap in enumerate(ordered):
        if not 0 <= cap['start'] < cap['end'] <= duration:
            errors.append(f"{cap['id']}: invalid caption window")
        if i and cap['start'] < ordered[i-1]['end'] - .001:
            errors.append(f"{cap['id']}: overlapping caption")
    for event in data['events']:
        for other in data['events']:
            if event['id'] < other['id'] and max(event['start'], other['start']) < min(event['settled'], other['settled']):
                if event['focus'] != other['focus']:
                    errors.append(f"{event['id']}/{other['id']}: simultaneous competing main actions")
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('timeline', type=Path)
    parser.add_argument('--rules', type=Path, required=True)
    args = parser.parse_args()
    findings = check(json.loads(args.timeline.read_text()), json.loads(args.rules.read_text()))
    print(json.dumps({'ok': not findings, 'findings': findings, 'scope': 'structure and timing only'}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(findings))
