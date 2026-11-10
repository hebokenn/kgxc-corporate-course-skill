"""Author-side input completeness, not an extra model review or a human click."""
import re
from production_validation import Check, load, graph, visible, first_readable, current_review, ENCODED


def inspect(project, doc, video, purpose, contract):
    c=Check('author_input')
    direction=contract.get('requirements',{}).get('direction',{})
    data=load(project,direction.get('author_input'))
    text=data.get('script_text','')
    if not data or not text:
        c.error('AUTHOR_INPUT_MISSING','Current author input self-check and spoken text are required')
        return c.result()
    terms=data.get('terms',[])
    required=set(re.findall(r'(?<![A-Za-z0-9])[A-Z][A-Z0-9]{1,}(?![A-Za-z0-9])',text)) | set(data.get('specialist_terms',[]))
    for term in required:
        row=next((r for r in terms if r.get('term')==term),{})
        if (row.get('first_raw_start')!=text.find(term) or not row.get('explanation') or not row.get('source_ref') or row.get('meaning_verified') is not True):
            c.error('TERM_UNVERIFIED','Term first occurrence lacks a verified meaning and source',term)
    coverage=load(project,data.get('source_coverage'))
    if data.get('has_sources'):
        points=coverage.get('points',[]);inventory=coverage.get('source_inventory',[])
        complete=bool(points and inventory and all(r.get('fully_read') and not r.get('unreadable') for r in inventory))
        if not points or any(not r.get('source_quote') or not r.get('reason') or r.get('disposition') not in {'retained','merged','omitted'} for r in points):
            c.error('SOURCE_COVERAGE_INCOMPLETE','All independent retained/omitted points and reasons must remain in the denominator')
        if not complete and coverage.get('rate') is not None:
            c.error('SOURCE_COVERAGE_FALSE_RATE','Incomplete source reading cannot claim a coverage percentage')
        if any(r.get('critical') and not r.get('conditions_and_exceptions') for r in points):
            c.error('SOURCE_RULE_CONDITION_MISSING','Critical rules must identify conditions/exceptions, including an explicit none')
        for row in coverage.get('additions',[]):
            if not row.get('reason') or not row.get('basis'):
                c.error('SOURCE_ADDITION_UNSUPPORTED','Authored addition lacks a reason and basis',row.get('id'))
        c.details['registered_denominator']=len(points)
        c.details['human_source_confirmation']='separate existing source-coverage gate; never created here'
    for demo in data.get('demonstrations',[]):
        if not all(demo.get(k) for k in ('id','object_ids','action','before','process','after')) or demo.get('before')==demo.get('after'):
            c.error('DEMONSTRATION_ABSTRACT','Demonstration must specify actual objects and different before/process/result',demo.get('id'))
    if purpose in {'script','design'}:
        return c.result()
    nodes,chains=graph(doc)
    from production_validation import changed
    for demo in data.get('demonstrations',[]):
        ids=demo.get('object_ids',[])
        if not ids or any(i not in nodes for i in ids):
            c.error('DEMONSTRATION_OBJECT_MISSING','Demonstration references missing actual subject objects',demo.get('id'))
        elif not any(changed(nodes[i],0,doc.get('sourceDurationFrames',0)) for i in ids):
            c.error('DEMONSTRATION_NOT_IMPLEMENTED','A description without real subject state operations is not an implemented demonstration',demo.get('id'))
    for ex in data.get('exercises',[]):
        eid=ex.get('id');q=ex.get('question_node_ids',[])+ex.get('material_node_ids',[])+ex.get('option_node_ids',[]);answers=ex.get('answer_node_ids',[])
        a,t=ex.get('question_start'),ex.get('answer_trigger')
        if not q or not answers or not ex.get('pause_cue') or type(a)is not int or type(t)is not int or a>=t or any(i not in nodes for i in q+answers):
            c.error('EXERCISE_BINDING_INVALID','Exercise requires full question/material/options/answer and pause/feedback timing',eid);continue
        if any(first_readable(doc,nodes,chains,i,end=t) is not None for i in answers):
            c.error('EXERCISE_ANSWER_EARLY','Answer is readable while the learner is still answering',eid)
        if any(not visible(doc,nodes,chains,i,t) for i in q):
            c.error('EXERCISE_MATERIAL_GONE','Full question and required material must remain for feedback comparison',eid)
    for d in data.get('dialogues',[]):
        eid=d.get('id');span=d.get('speech_range',[]);participants=[d.get('speaker_id')]+d.get('addressee_ids',[])
        if len(span)!=2 or not d.get('addressee_ids') or not d.get('listen_state') or not d.get('facing_target') or not d.get('response_action') or any(i not in nodes for i in participants):
            c.error('DIALOGUE_BINDING_INVALID','Dialogue must identify the real listener, facing and response',eid);continue
        if any(not visible(doc,nodes,chains,i,f) for i in participants for f in range(*span)):
            c.error('DIALOGUE_LISTENER_ABSENT','Speaker and addressees must be visible throughout the actual speech',eid)
        if d.get('leave_after_frame',span[1])<span[1]:
            c.error('DIALOGUE_LEAVES_EARLY','Listener leaves before the speech finishes',eid)
    for d in data.get('diagrams',[]):
        eid=d.get('id');labels=d.get('label_node_ids',[]);objects=d.get('object_ids',[]);span=d.get('frame_window',[])
        if len(span)!=2 or not d.get('meaning') or not d.get('direction') or not labels or not objects or any(i not in nodes for i in labels+objects):
            c.error('DIAGRAM_BINDING_INVALID','Diagram lacks actual meaning, objects, relation direction or common window',eid);continue
        if any(nodes[i].get('type')!='text' or nodes[i].get('role') in {'caption','title','navigation','decoration'} for i in labels):
            c.error('DIAGRAM_BODY_LABEL_MISSING','Caption/title/navigation cannot replace business labels',eid)
        if any(not visible(doc,nodes,chains,i,f) for i in labels+objects for f in (span[0],span[1]-1)):
            c.error('DIAGRAM_LABEL_NOT_COVISIBLE','Object and body label do not share the declared window',eid)
    if purpose in ENCODED and (data.get('dialogues') or data.get('demonstrations')):
        review=load(project,data.get('runtime_review'))
        rows=current_review(c,project,review,doc,video,'ACTING_RUNTIME_UNVERIFIED')
        for d in data.get('dialogues',[])+data.get('demonstrations',[]):
            evidence=[r for r in rows if r.get('event_id')==d.get('id')]
            if len({r.get('frame',r.get('encoded_frame')) for r in evidence})<3 or any(not r.get('object_states') for r in evidence):
                c.error('ACTING_RUNTIME_UNVERIFIED','Keyframes/descriptions alone are not actual before/mid/end actor state and pixels',d.get('id'))
            for row in evidence:
                if row.get('layout_violations'):
                    c.error('ACTING_RUNTIME_OCCLUDED','Actual runtime layout/contact receipt has unresolved violations',d.get('id'))
            if d.get('speaker_id') and evidence:
                speaker=d['speaker_id'];targets=d.get('addressee_ids',[])
                for row in evidence:
                    states=row.get('object_states',{});own=states.get(speaker,{})
                    for target in targets:
                        other=states.get(target,{})
                        yaw=own.get('actor',{}).get('orientation',{}).get('torsoYaw')
                        if not own or not other or yaw is None or (other.get('x',0)-own.get('x',0))*yaw<0:
                            c.error('DIALOGUE_FACING_UNVERIFIED','Actual actor receipt does not show the speaker facing the in-scene addressee',d.get('id'))
    return c.result()
