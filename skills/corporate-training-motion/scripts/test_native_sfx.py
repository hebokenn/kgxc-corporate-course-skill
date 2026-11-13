"""Exercise native-source provenance, stereo alignment, group mixing and old plans."""
from array import array
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workbench'))
from sound import PALETTE,NATURAL_PALETTE,RATE,catalog,make_plan,mix,sha,write_wav


class NativeSoundTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=Path(self.temp.name)/'project'
        (self.p/'source').mkdir(parents=True)
        (self.p/'workbench.json').write_text(json.dumps(dict(status='draft')))
        (self.p/'source/composition.json').write_text(json.dumps(dict(sourceDurationFrames=180,fps=30)))
        write_wav(self.p/'audio/voice.wav',[0.]*(6*RATE))

    def plan(self,events,palette=None):
        spec=dict(events=events)
        if palette:spec['palette']=palette
        path=self.p/'source/events.json';path.write_text(json.dumps(spec))
        return make_plan(self.p,path)['plan']

    def test_default_uses_exact_two_selected_originals_and_stereo_peak_frames(self):
        data=catalog();self.assertEqual(data['id'],PALETTE)
        self.assertEqual(len(data['assets']),15)
        self.assertEqual(len({a['sha256'] for a in data['assets']}),2)
        folder=ROOT/'assets/sfx'/PALETTE
        source=json.loads((folder/'source.json').read_text())
        self.assertEqual({a['originalSha256'] for a in source['clips'].values()},
                         {'0e44878ef86e8a1b9f3f30e2ecb8e69f849cbd0748e03de160386ac0ce68dcff',
                          'bdb886c9361538ad821ff8cd2026f119050dbd2be0c44c34a8c85e499cd5135c'})
        for item in source['clips'].values():self.assertEqual(sha(folder/item['original']),item['originalSha256'])
        for asset in data['assets']:
            with wave.open(str(folder/asset['path']),'rb') as audio:
                self.assertEqual((audio.getframerate(),audio.getnchannels(),audio.getsampwidth()),(RATE,2,2))
                samples=array('h');samples.frombytes(audio.readframes(audio.getnframes()))
            peak=max(range(len(samples)//2),key=lambda i:max(abs(samples[i*2]),abs(samples[i*2+1])))
            self.assertEqual(asset['peakSample'],peak)
        plan=self.plan([dict(id='pop',frame=30,role='appear'),dict(id='quiet',frame=60,role='none')])
        self.assertEqual(plan['palette'],PALETTE);self.assertEqual(plan['events'][0]['assetId'],'appear-native')
        self.assertEqual(plan['events'][0]['gainDb'],-17);self.assertEqual(len(plan['skipped']),1)

    def test_native_stereo_mix_keeps_voice_and_source_files(self):
        plan=self.plan([dict(id='pop',frame=30,role='appear'),dict(id='done',frame=90,role='confirm')])
        voice=self.p/'audio/voice.wav';before=sha(voice)
        receipt=mix(self.p,self.p/'audio/sfx-plan.json','audio/voice.wav','audio/mix.wav')
        self.assertEqual(sha(voice),before);self.assertEqual(receipt['duration'],6)
        self.assertEqual(len(receipt['appliedGains']),2)
        with wave.open(str(self.p/'audio/mix.wav'),'rb') as audio:
            self.assertEqual((audio.getnchannels(),audio.getnframes()),(2,6*RATE))
            data=array('h');data.frombytes(audio.readframes(audio.getnframes()))
        self.assertGreater(max(abs(x) for x in data),0)
        self.assertLess(receipt['peak'],.98)

    def custom(self):
        folder=self.p/'audio/sfx/test-native-v1';folder.mkdir(parents=True)
        samples=[]
        for i in range(2400):samples.extend([.4*math.sin(2*math.pi*i/31),0.])
        write_wav(folder/'left.wav',samples,2)
        data=array('h')
        with wave.open(str(folder/'left.wav'),'rb') as audio:data.frombytes(audio.readframes(audio.getnframes()))
        peak=max(range(len(data)//2),key=lambda i:abs(data[i*2]))
        asset=dict(id='left',role='appear',path='left.wav',sha256=sha(folder/'left.wav'),peakSample=peak)
        (folder/'palette.json').write_text(json.dumps(dict(id=folder.name,assets=[asset])))
        return folder.name,peak

    def test_custom_stereo_is_not_collapsed_or_offset_by_channel_count(self):
        palette,peak=self.custom();self.plan([dict(id='left',frame=30,role='appear')],palette)
        mix(self.p,self.p/'audio/sfx-plan.json','audio/voice.wav','audio/mix.wav')
        with wave.open(str(self.p/'audio/mix-sfx.wav'),'rb') as audio:
            data=array('h');data.frombytes(audio.readframes(audio.getnframes()))
        self.assertTrue(any(data[0::2]));self.assertFalse(any(data[1::2]))
        self.assertEqual(max(range(len(data)//2),key=lambda i:abs(data[i*2])),RATE)

    def test_equal_group_uses_common_ducking_gain_and_reports_it(self):
        palette,_=self.custom();voice=[]
        for i in range(6*RATE):
            amplitude=.07 if i<2*RATE else .5
            voice.append(amplitude*math.sin(2*math.pi*173*i/RATE))
        write_wav(self.p/'audio/voice.wav',voice)
        events=[dict(id='a',frame=30,role='appear',groupId='choices'),dict(id='b',frame=90,role='appear',groupId='choices')]
        self.plan(events,palette)
        grouped=mix(self.p,self.p/'audio/sfx-plan.json','audio/voice.wav','audio/group.wav')
        self.assertEqual(grouped['appliedGains'][0]['gainDb'],grouped['appliedGains'][1]['gainDb'])
        for event in events:event.pop('groupId')
        self.plan(events,palette)
        ungrouped=mix(self.p,self.p/'audio/sfx-plan.json','audio/voice.wav','audio/ungrouped.wav')
        self.assertNotEqual(ungrouped['appliedGains'][0]['gainDb'],ungrouped['appliedGains'][1]['gainDb'])

    def test_mismatched_group_and_palette_traversal_fail_before_output(self):
        with self.assertRaisesRegex(ValueError,'平等音效组'):
            self.plan([dict(id='a',frame=30,role='appear',groupId='choices'),dict(id='b',frame=60,role='confirm',groupId='choices')])
        plan=self.plan([dict(id='a',frame=30,role='appear',groupId='choices'),dict(id='b',frame=60,role='appear',groupId='choices')])
        plan['events'][1]['gainDb']+=1
        (self.p/'audio/sfx-plan.json').write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError,'平等音效组'):
            mix(self.p,self.p/'audio/sfx-plan.json','audio/voice.wav','audio/bad.wav')
        self.assertFalse((self.p/'audio/bad.wav').exists())
        with self.assertRaises(ValueError):catalog(self.p,'../escape')

    def test_explicit_old_palette_and_cli_catalog_stay_available(self):
        self.assertEqual(len(catalog(palette=NATURAL_PALETTE)['assets']),45)
        plan=self.plan([dict(id='old',frame=30,role='enter')],NATURAL_PALETTE)
        self.assertEqual(plan['palette'],NATURAL_PALETTE)
        before=(self.p/'audio/sfx-plan.json').read_bytes()
        result=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/course_tools.py'),'sfx-catalog'],text=True))
        self.assertEqual(result['id'],PALETTE)
        self.assertEqual((self.p/'audio/sfx-plan.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
