"""Pre-send isolation and capability checks. A probe is never a course review."""
import copy
import re

class ReviewPreflightError(ValueError):
    pass

def learner_payload(packet):
    value = copy.deepcopy(packet)
    value['allowed_artifacts'] = [{k:v for k,v in a.items() if k != 'path'} for a in value.get('allowed_artifacts', [])]
    for a in [*value.get('evidence', {}).get('media', []), *value.get('evidence', {}).get('frames', [])]:
        a.pop('path', None)
    return value

def inspect_payload(packet):
    """Scan the entire outbound whitelist after host-only capabilities are removed."""
    value = learner_payload(packet)
    errors = []
    markers = re.compile(r'\b(?:UV\d{2,}(?:-F\d+)?|(?:PILOT|FINAL|STORYBOARD|SCRIPT)-F\d+|history:F\d+)\b|\bUSER-FOLLOWUP-[A-Za-z0-9]+|/Users/[^\s"\']+|file://|(?:^|\s)(?:project|qa|source|work)/[^\s]+\.(?:json|md|pdf|wav|mp4)\b', re.I)
    forbidden = {'producer_history', 'prior_reviews', 'repair_history', 'source_document', 'expected_answer', 'teaching_objectives', 'original_material'}
    def walk(item, locator='$'):
        if isinstance(item, dict):
            for key, child in item.items():
                if key in forbidden:
                    errors.append(dict(code='REVIEW_INPUT_CONTAMINATED', locator=locator+'.'+key, reason='producer context key'))
                walk(child, locator+'.'+key)
        elif isinstance(item, list):
            for index, child in enumerate(item): walk(child, locator+f'[{index}]')
        elif isinstance(item, str) and markers.search(item):
            errors.append(dict(code='REVIEW_INPUT_CONTAMINATED', locator=locator, reason='production lineage or private path'))
    walk(value)
    return dict(ready=not errors, errors=errors)

def require_clean(packet):
    result=inspect_payload(packet)
    if not result['ready']:
        raise ReviewPreflightError('REVIEW_INPUT_CONTAMINATED: '+', '.join(e['locator'] for e in result['errors']))
    return result

def capability_matrix(checklist, capabilities):
    """Only actual runner capabilities count. No model-name inference or fallback."""
    needs={'script_read':{'text'}, 'storyboard_read':{'text'}, 'frames':{'images'},
           'frame_sequence':{'images'}, 'full_av':{'continuous_video','audio_listening'},
           'user_listening':{'user_listening'}, 'media_probe':{'media_probe'},
           'automatic_audio_technical':{'automatic_audio_technical'}}
    rows=[]
    for item in checklist:
        missing=sorted(needs.get(item.get('required_method'), {'unknown_method'})-set(capabilities))
        rows.append(dict(id=item['id'], method=item.get('required_method'), missing=missing,
                         critical=bool(item.get('critical')), available=not missing))
    return dict(schema='review-capability-matrix/1', checks=rows, capabilities=sorted(capabilities),
                ready=not any(r['critical'] and r['missing'] for r in rows),
                course_blind_review=False, inference_performed=False,
                limits='Text, images, ASR and signal checks do not establish continuous viewing or listening.')
