"""Behavioral production gates against real files, not reported event counts."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/corporate-training-motion/workbench'))
from production_contract import ensure, inspect, load, document_digest, _sha, _native_assets


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class ProductionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory()
        path = Path(cls.media.name) / 'real.mp4'
        if not shutil.which('ffmpeg'):
            raise unittest.SkipTest('ffmpeg required for real encoded media fixtures')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=white:s=64x64:r=30:d=2',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True, capture_output=True)
        cls.video_bytes = path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.media.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name)
        self.video = self.p / 'arbitrary-candidate-name.mp4'
        self.video.write_bytes(self.video_bytes)
        self.preferences = dict(schema='course-production-preferences/1',
                                choices=dict(customer='none', sound_effects='off', flower_text='off'))
        write(self.p / 'production-preferences.json', self.preferences)
        self.doc = dict(title='Example course', profile='example-corp', width=1920, height=1080, fps=30,
                        sourceDurationFrames=60, scenes=[dict(id='S1')], media={},
                        captions=[dict(text='Read the facts first.', startFrame=0, endFrame=60)],
                        sceneGraph=dict(nodes=[dict(id='subject', type='rect', startFrame=0, endFrame=60,
                            motion=[dict(kind='move', startFrame=0, endFrame=30, **{'from': 0, 'to': 100})]),
                            dict(id='nav', type='text', text='Facts', startFrame=0, endFrame=60,
                                 motion=[dict(kind='color', startFrame=0, endFrame=10, **{'from': '#aaa', 'to': '#123'})])]))
        ensure(self.p, profile='example-corp')

    def tearDown(self):
        self.tmp.cleanup()

    def contract(self):
        return json.loads((self.p / 'production-contract.json').read_text())

    def save(self, value):
        write(self.p / 'production-contract.json', value)

    def proof(self):
        return dict(status='verified', actor='fixture-producer', evidence='Observed current encoded frames',
                    document_sha256=document_digest(self.doc), video_sha256=_sha(self.video),
                    observations=[dict(scene_id='S1', frame=15, observation='Subject moves to the facts')])

    def complete_nonbrand(self):
        contract = self.contract()
        contract['requirements']['direction'].update(
            scenes=[dict(scene_id='S1', quote='Read the facts first.', purpose='Demonstrate a first step',
                         before='Fact outside focus', process='Move the fact into focus', after='Fact in focus',
                         node_ids=['subject'], start_frame=0, end_frame=60)], review=self.proof())
        contract['requirements']['chapters'].update(segments=[dict(id='facts', label='Facts', node_id='nav',
            start_frame=0, end_frame=60, states=[dict(frame=0, state='current')])], review=self.proof())
        self.save(contract)

    def diagram_contract(self):
        self.doc['sceneGraph']['nodes'].append(dict(id='diagram-label', type='text', text='Team work',
            role='subject', sceneId='S1', startFrame=0, endFrame=60))
        self.complete_nonbrand()
        contract = self.contract()
        contract['requirements']['direction']['scenes'][0]['diagram_labels'] = [dict(
            diagram_node_ids=['subject'], label_node_ids=['diagram-label'], meaning='Work carried by the team',
            start_frame=0, end_frame=60)]
        self.save(contract)
        return contract

    def direction_errors(self):
        return [e['message'] for e in inspect(self.p, self.doc, self.video)['errors']
                if e['requirement'] == 'direction']

    def test_current_standalone_document_can_pass_without_forcing_kg_brand(self):
        self.complete_nonbrand()
        result = inspect(self.p, document=self.doc, video=self.video)
        self.assertTrue(result['ready'], result['errors'])
        self.assertFalse(result['checks']['logo']['required'])
        self.assertFalse(result['checks']['bookends']['required'])

    def test_deleting_preferences_and_contract_never_opts_active_video_out(self):
        self.complete_nonbrand()
        (self.p / 'production-contract.json').unlink()
        (self.p / 'production-preferences.json').unlink()
        result = inspect(self.p, document=self.doc, video=self.video)
        self.assertTrue(result['required'])
        self.assertFalse(result['ready'])
        self.assertTrue({'contract', 'preferences'} <= {e['requirement'] for e in result['errors']})

    def test_choice_sync_preserves_plans_archives_old_basis_and_is_idempotent(self):
        contract = self.contract()
        contract['requirements']['emphasis']['events'] = [dict(id='saved-plan')]
        self.save(contract)
        old = (self.p / 'production-contract.json').read_bytes()
        self.preferences['choices']['sound_effects'] = 'native'
        write(self.p / 'production-preferences.json', self.preferences)
        ensure(self.p)
        self.assertEqual(self.contract()['requirements']['emphasis']['events'], [dict(id='saved-plan')])
        self.assertTrue(self.contract()['requirements']['sfx']['assets'])
        history = self.p / 'work/production-contract-history' / (hashlib.sha256(old).hexdigest() + '.json')
        self.assertEqual(history.read_bytes(), old)
        current = (self.p / 'production-contract.json').read_bytes()
        ensure(self.p)
        self.assertEqual((self.p / 'production-contract.json').read_bytes(), current)

    def test_old_library_with_native_label_and_reported_counts_cannot_pass(self):
        self.preferences['choices']['sound_effects'] = 'native'
        write(self.p / 'production-preferences.json', self.preferences)
        ensure(self.p)
        asset = self.p / 'audio/old.wav'
        asset.parent.mkdir()
        asset.write_bytes(b'old library pretending to be selected ding')
        write(self.p / 'audio/sfx-plan.json', dict(palette='teaching-native-v1', events=[dict(
            id='fake-ding', assetId='focus-native', path='audio/old.wav', sha256=_sha(asset), frame=15)]))
        contract = self.contract()
        contract['requirements']['sfx']['review'] = dict(self.proof(), encoded_audio_sha256='invented')
        self.save(contract)
        errors = [e['message'] for e in inspect(self.p, self.doc, self.video)['errors'] if e['requirement'] == 'sfx']
        self.assertTrue(any('冻结' in error for error in errors))
        self.assertTrue(any('叮' in error for error in errors))

    def test_changed_video_invalidates_producer_observations(self):
        self.complete_nonbrand()
        self.video.write_bytes(self.video_bytes + b'new candidate bytes')
        result = inspect(self.p, self.doc, self.video)
        self.assertFalse(result['ready'])
        self.assertTrue(any(e['requirement'] == 'direction' and '当前' in e['message'] for e in result['errors']))

    def test_fade_only_claim_needs_real_information_change_and_before_after_review(self):
        self.doc['sceneGraph']['nodes'][0]['motion'] = [dict(kind='fade-in', startFrame=0, endFrame=10)]
        self.complete_nonbrand()
        self.assertFalse(inspect(self.p, self.doc, self.video)['checks']['direction']['ready'])
        contract = self.contract()
        direction = contract['requirements']['direction']
        direction['scenes'][0]['change_kind'] = 'information-reveal'
        direction['review']['observations'] = [dict(scene_id='S1', frame=0, stage='before', observation='Fact is hidden'),
                                              dict(scene_id='S1', frame=15, stage='after', observation='New fact is visible')]
        self.save(contract)
        self.assertTrue(inspect(self.p, self.doc, self.video)['checks']['direction']['ready'])

    def test_purposeful_stable_reading_is_allowed_with_a_reason_and_current_observation(self):
        self.doc['sceneGraph']['nodes'][0]['motion'] = []
        self.complete_nonbrand()
        contract = self.contract()
        contract['requirements']['direction']['scenes'][0].update(change_kind='purposeful-reading',
            reason='Retain the concise result while the narrator explains it', reading_window=[10, 60])
        self.save(contract)
        self.assertTrue(inspect(self.p, self.doc, self.video)['checks']['direction']['ready'])

    def test_export_document_is_resolved_by_real_hash_without_filename_convention(self):
        self.complete_nonbrand()
        exported = self.p / 'work/workbench/exports/unrelated-job/document.json'
        write(exported, self.doc)
        write(self.video.with_suffix('.json'), dict(document_sha256=_sha(exported), video_sha256=_sha(self.video)))
        result = inspect(self.p, video=self.video)
        self.assertTrue(result['ready'], result['errors'])
        exported.write_text('{}')
        self.assertFalse(inspect(self.p, video=self.video)['ready'])

    def test_frozen_legacy_is_not_migrated_but_new_candidate_cannot_borrow_it(self):
        (self.p / 'production-contract.json').unlink()
        (self.p / 'production-contract-required.json').unlink()
        write(self.p / 'course-state.json', dict(version='6.4.0', branch='video',
            artifacts=dict(final=[self.video.name])))
        self.preferences['recorded_existing_production'] = dict(video_path=self.video.name,
            video_sha256=_sha(self.video), actor='historical-producer', evidence='Verified historical delivery')
        write(self.p / 'production-preferences.json', self.preferences)
        before = {f.name: f.read_bytes() for f in self.p.iterdir() if f.is_file()}
        self.assertFalse(ensure(self.p)['required'])
        self.assertEqual(before, {f.name: f.read_bytes() for f in self.p.iterdir() if f.is_file()})
        other = self.p / 'new.mp4'
        other.write_bytes(self.video_bytes + b'changed')
        self.assertTrue(inspect(self.p, self.doc, other)['required'])
        self.assertTrue(ensure(self.p, activate=True)['required'])
        self.assertTrue((self.p / 'production-contract-required.json').is_file())

    def test_stale_modern_final_receipt_cannot_exempt_current_revision(self):
        (self.p / 'production-contract.json').unlink()
        (self.p / 'production-contract-required.json').unlink()
        write(self.p / 'course-state.json', dict(schema='course-workflow/2', version='6.8.1', branch='video',
            gates=dict(final=dict(sha256='stale-content-context')), artifacts=dict(final=[self.video.name]),
            deliveries=[dict(branch='video', files=[dict(path=self.video.name, sha256=_sha(self.video))])]))
        self.assertTrue(load(self.p)['required'])

    def test_pilot_checks_current_scene_instead_of_unshown_future_scenes(self):
        self.doc['scenes'][0].update(sourceStartFrame=0, sourceEndFrame=30)
        self.doc['scenes'].append(dict(id='future', sourceStartFrame=30, sourceEndFrame=60))
        self.complete_nonbrand()
        write(self.video.with_suffix('.json'), dict(video_sha256=_sha(self.video),
            range=dict(firstFrame=0, lastFrame=30, fps=30)))
        result = inspect(self.p, self.doc, self.video, 'pilot')
        self.assertTrue(result['checks']['direction']['ready'], result['errors'])
        self.assertFalse(inspect(self.p, self.doc, self.video, 'final')['checks']['direction']['ready'])

    def test_logo_exception_requires_recorded_actual_choice_evidence(self):
        self.preferences['choices']['logo'] = 'off'
        write(self.p / 'production-preferences.json', self.preferences)
        ensure(self.p, profile='kgxc')
        result = inspect(self.p, self.doc, self.video)
        self.assertTrue(result['checks']['logo']['required'])
        self.preferences['answers'] = dict(logo=dict(value='off', actor='user', evidence='Explicit hide logo choice for this course'))
        write(self.p / 'production-preferences.json', self.preferences)
        ensure(self.p)
        self.assertFalse(inspect(self.p, self.doc, self.video)['checks']['logo']['required'])

    def test_sample_deferral_never_carries_into_final(self):
        ensure(self.p, profile='kgxc')
        contract = self.contract()
        contract['requirements']['bookends']['pilot_defer'] = dict(actor='fixture-producer',
            reason='Middle body sample excludes the bookends', evidence='Observed selected sample',
            source_range=[10, 50], document_sha256=document_digest(self.doc), video_sha256=_sha(self.video))
        self.save(contract)
        self.assertEqual(inspect(self.p, self.doc, self.video, 'pilot')['checks']['bookends']['status'],
                         'deferred-outside-current-pilot')
        self.assertFalse(inspect(self.p, self.doc, self.video, 'final')['checks']['bookends']['ready'])

    def test_explicit_body_labels_can_explain_several_diagram_objects(self):
        contract = self.diagram_contract()
        self.doc['sceneGraph']['nodes'].append(dict(id='other-team-work', type='rect', sceneId='S1'))
        direction = contract['requirements']['direction']
        direction['scenes'][0]['diagram_labels'][0]['diagram_node_ids'].append('other-team-work')
        direction['review'] = self.proof()
        contract['requirements']['chapters']['review'] = self.proof()
        self.save(contract)
        self.assertTrue(inspect(self.p, self.doc, self.video)['ready'], self.direction_errors())

    def test_declared_binding_cannot_omit_or_invent_diagram_or_label_nodes(self):
        original = self.diagram_contract()
        for field in ['diagram_node_ids', 'label_node_ids']:
            for bad in [None, [], ['not-a-current-node']]:
                with self.subTest(field=field, bad=bad):
                    contract = copy.deepcopy(original)
                    binding = contract['requirements']['direction']['scenes'][0]['diagram_labels'][0]
                    if bad is None:
                        binding.pop(field)
                    else:
                        binding[field] = bad
                    self.save(contract)
                    self.assertTrue(any('图示标签绑定' in e for e in self.direction_errors()))

    def test_empty_or_nontext_nodes_cannot_stand_in_for_labels(self):
        original = self.diagram_contract()
        for change in [dict(text='  \n '), dict(type='rect'), dict(text=None)]:
            with self.subTest(change=change):
                label = next(n for n in self.doc['sceneGraph']['nodes'] if n['id'] == 'diagram-label')
                label.update(type='text', text='Team work')
                label.update(change)
                contract = copy.deepcopy(original)
                contract['requirements']['direction']['review'] = self.proof()
                self.save(contract)
                self.assertTrue(any('非空正文text' in e for e in self.direction_errors()))

    def test_caption_header_and_navigation_cannot_substitute_for_body_labels(self):
        original = self.diagram_contract()
        label = next(n for n in self.doc['sceneGraph']['nodes'] if n['id'] == 'diagram-label')
        for role in ['caption', 'subtitle', 'navigation', 'title', 'header', 'footer']:
            with self.subTest(role=role):
                label['role'] = role
                contract = copy.deepcopy(original)
                contract['requirements']['direction']['review'] = self.proof()
                self.save(contract)
                self.assertTrue(any('不能替代正文' in e for e in self.direction_errors()))
        label['role'] = 'subject'
        contract = copy.deepcopy(original)
        contract['requirements']['direction']['scenes'][0]['diagram_labels'][0]['label_node_ids'] = ['nav']
        contract['requirements']['direction']['review'] = self.proof()
        self.save(contract)
        # This known chapter node has no explicit role in the base fixture.
        self.assertTrue(any('不能替代正文' in e for e in self.direction_errors()))
        self.doc['captions'][0]['id'] = 'diagram-label'
        contract = copy.deepcopy(original)
        contract['requirements']['direction']['review'] = self.proof()
        self.save(contract)
        self.assertTrue(any('不能替代正文' in e for e in self.direction_errors()))

    def test_binding_window_must_fit_scene_and_label_visibility(self):
        original = self.diagram_contract()
        for start, end in [(-1, 60), (0, 61), (30, 30)]:
            with self.subTest(start=start, end=end):
                contract = copy.deepcopy(original)
                contract['requirements']['direction']['scenes'][0]['diagram_labels'][0].update(
                    start_frame=start, end_frame=end)
                self.save(contract)
                self.assertTrue(any('帧窗' in e for e in self.direction_errors()))
        label = next(n for n in self.doc['sceneGraph']['nodes'] if n['id'] == 'diagram-label')
        label['startFrame'] = 10
        contract = copy.deepcopy(original)
        contract['requirements']['direction']['review'] = self.proof()
        self.save(contract)
        self.assertTrue(any('未覆盖登记帧窗' in e for e in self.direction_errors()))

    def test_group_label_inherits_scene_scope_and_uses_parent_window(self):
        original = self.diagram_contract()
        label = self.doc['sceneGraph']['nodes'].pop()
        label.pop('sceneId')
        parent = dict(id='label-group', type='group', sceneId='S1', startFrame=0, endFrame=60,
                      children=[label])
        self.doc['sceneGraph']['nodes'].append(parent)
        contract = copy.deepcopy(original)
        contract['requirements']['direction']['review'] = self.proof()
        contract['requirements']['chapters']['review'] = self.proof()
        self.save(contract)
        self.assertTrue(inspect(self.p, self.doc, self.video)['ready'], self.direction_errors())
        for change in [dict(visible=False), dict(opacity=0), dict(startFrame=10),
                       dict(endFrame=50), dict(sceneId='S2'), dict(role='navigation')]:
            with self.subTest(parent=change):
                parent.clear()
                parent.update(id='label-group', type='group', sceneId='S1', startFrame=0, endFrame=60,
                              children=[label])
                parent.update(change)
                contract['requirements']['direction']['review'] = self.proof()
                self.save(contract)
                self.assertTrue(self.direction_errors())

    def test_registered_label_list_and_business_meaning_cannot_be_empty(self):
        original = self.diagram_contract()
        for bad in [None, {}, []]:
            with self.subTest(bindings=bad):
                contract = copy.deepcopy(original)
                contract['requirements']['direction']['scenes'][0]['diagram_labels'] = bad
                self.save(contract)
                self.assertTrue(any('图示标签已登记' in e for e in self.direction_errors()))
        contract = copy.deepcopy(original)
        contract['requirements']['direction']['scenes'][0]['diagram_labels'][0]['meaning'] = '  '
        self.save(contract)
        self.assertTrue(any('业务含义' in e for e in self.direction_errors()))


if __name__ == '__main__':
    unittest.main()
