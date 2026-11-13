"""Small encoded fixtures for timing, speech pitch and cover delivery checks."""
import copy,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'workbench'))
from cover_quality import review,CRITERIA
from finish_media import finish,retime,read_srt,pitch_filter,closing_warnings

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):subprocess.run(['ffmpeg','-v','error','-y',*args],check=True)

class TimingTests(unittest.TestCase):
    def test_one_mapping_for_body_and_bookends(self):
        cues=retime([dict(start=11,end=12.1,text='正文')],1.1,[dict(start=1.1,end=2.2,text='开场')])
        self.assertEqual([c['start'] for c in cues],[1,10]);self.assertAlmostEqual(cues[-1]['end'],11)
    def test_invalid_rates_and_overlaps_rejected(self):
        for rate in [0,float('nan'),3]:
            with self.assertRaises(ValueError):retime([],rate)
        with self.assertRaises(ValueError):retime([dict(start=1,end=3,text='一'),dict(start=2,end=4,text='二')],1)
    def test_pitch_and_speed_are_independent(self):
        self.assertIn('asetrate=50854',pitch_filter(1.1,1))
        self.assertIn('atempo=1.100000000000',pitch_filter(1.1,0))
    def test_existing_farewell_is_flagged_before_adding_another(self):
        old=[dict(start=90,end=93,text='这节课就到这里谢谢大家')]
        added=[dict(start=95,end=98,text='本节课程到此结束感谢大家观看')]
        self.assertTrue(closing_warnings(old,added,100))
        self.assertEqual(closing_warnings(old,[],100),[])
        self.assertEqual(old[0]['text'],'这节课就到这里谢谢大家')

class EncodedCoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.p=Path(cls.tmp.name);p=cls.p;(p/'qa').mkdir()
        run(['-f','lavfi','-i','color=c=black:size=160x90:rate=10:duration=2','-c:v','libx264','-pix_fmt','yuv420p',str(p/'source.mp4')])
        for name,freq in [('speech',440),('bed',880)]:
            run(['-f','lavfi','-i',f'sine=frequency={freq}:sample_rate=48000:duration=2','-af','volume=0.1','-c:a','pcm_s16le',str(p/(name+'.wav'))])
        Image.new('RGB',(1280,720),'#a85b39').save(p/'cover.png')
        Image.new('RGB',(320,180),'#a85b39').save(p/'thumbnail.png')
        (p/'source.srt').write_text('1\n00:00:00,500 --> 00:00:01,500\nTechnical fixture only\n\n')
        plan=dict(video='source.mp4',srt='source.srt',speech='speech.wav',bed='bed.wav',cover='cover.png',output_video='output.mp4',output_srt='output.srt',rate=1.1,pitch_semitones=1,fps=10,cover_hold_seconds=.2,cover_fade_seconds=.1)
        (p/'plan.json').write_text(json.dumps(plan));cls.receipt=finish(p/'plan.json')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.doc=dict(title='Technical fixture',qualityPolicy=dict(coverRequired=True))
        self.record=dict(schema='course-cover-review/1',status='reviewed',title=self.doc['title'],videoSha256=sha(self.p/'output.mp4'),coverPath='cover.png',coverSha256=sha(self.p/'cover.png'),thumbnailPath='thumbnail.png',thumbnailSha256=sha(self.p/'thumbnail.png'),mode='first-frame',reviewer='Automated fixture, not a real aesthetic review',scope='Technical cover pixel contract only',unresolvedIssues=[],**{k:'Fixture observation '+k for k in CRITERIA})
    def check(self,pixels=False):
        (self.p/'qa/cover-review.json').write_text(json.dumps(self.record));return review(self.p,self.doc,self.p/'output.mp4',verify_pixels=pixels)
    def test_real_encode_and_retimed_captions(self):
        self.assertTrue(self.receipt['full_decode']);self.assertEqual(self.receipt['frames'],18)
        self.assertAlmostEqual(read_srt(self.p/'output.srt')[0]['start'],.455,places=3)
        self.assertEqual(self.check(True)['status'],'pass')
        import numpy as np
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(self.p/'output.mp4'),'-map','0:a:0','-ar','48000','-ac','1','-f','f32le','-'])
        y=np.frombuffer(raw,dtype='<f4')[9600:57600];power=abs(np.fft.rfft(y*np.hanning(len(y))))
        # The speech sine must rise one semitone while the music sine stays at 880 Hz.
        for frequency in [440*2**(1/12),880]:
            lo=round(frequency)-8;hi=round(frequency)+9
            peak=lo+int(np.argmax(power[lo:hi]));self.assertLess(abs(peak-frequency),2)
    def test_old_video_and_missing_observation_rejected(self):
        self.record['videoSha256']='old';self.assertEqual(self.check()['status'],'pending')
        self.record['videoSha256']=sha(self.p/'output.mp4');self.record.pop('thumbnailObservation')
        self.assertEqual(self.check()['status'],'pending')
    def test_cover_image_alone_does_not_prove_player_or_first_frame(self):
        self.record['mode']='image-only';self.assertEqual(self.check()['status'],'pending')
        self.record['mode']='first-frame';self.record['videoSha256']=sha(self.p/'source.mp4')
        (self.p/'qa/cover-review.json').write_text(json.dumps(self.record))
        self.assertEqual(review(self.p,self.doc,self.p/'source.mp4')['status'],'pending')
    def test_real_player_poster_is_checked(self):
        self.record.update(mode='player-poster',pagePath='page.html')
        (self.p/'page.html').write_text('<video poster="cover.png" src="output.mp4"></video>')
        self.assertEqual(self.check()['status'],'pass')
        (self.p/'page.html').write_text('<video src="output.mp4"></video>')
        self.assertEqual(self.check()['status'],'pending')
    def test_new_cover_contract_cannot_be_deleted_and_legacy_is_unchanged(self):
        self.doc['qualityPolicy'].pop('coverRequired');self.assertEqual(self.check()['status'],'legacy-not-opted-in')
        marker=self.p/'craft-contract.json';marker.write_text('{"coverRequired":true}')
        try:self.assertEqual(self.check()['status'],'pending')
        finally:marker.unlink()
    def test_existing_output_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError,'already exists'):finish(self.p/'plan.json')

if __name__=='__main__':unittest.main()
