from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import hashlib
import json
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/corporate-training-motion/workbench'))
from material_library import library


class MaterialLibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.project=self.root/'project'; self.project.mkdir()
        (self.root/'inputs').mkdir()
        self.path='../inputs/shop.jpg'
        self.photo=self.root/'inputs/shop.jpg';self.photo.write_bytes(b'original photo')
        self.source_hash=hashlib.sha256(self.photo.read_bytes()).hexdigest()
        self.course=SimpleNamespace(project=self.project,relative=self.relative)
        self.sources=[dict(id='SRC-photo',title='现场照片',kind='file',location=self.path)]
        self.artifact=dict(path='../delivery/pilot.mp4',sha256='a'*64,available=True,duration_seconds=10.0)
        self.artifacts={'pilot':[self.artifact]}
        self.coverage=dict(current=True,report=dict(points=[dict(id='P01',source_id='SRC-photo',disposition='retained',locator='p1',reason='重要业务信息')]))

    def relative(self,path):
        result=(self.project/path).resolve()
        if Path(path).is_absolute() or not result.is_relative_to(self.root):raise ValueError('outside')
        return result

    def save(self,path,value):(self.project/path).write_text(json.dumps(value))

    def receipt(self,**kwargs):
        self.save('material-video-usage.json',dict(schema='material-video-usage/1',
            materials=[dict(source_id='SRC-photo',source_sha256=self.source_hash,**kwargs)]))

    def placements(self,**kwargs):
        placement=dict(stage='pilot',artifact_path=self.artifact['path'],artifact_sha256=self.artifact['sha256'],
                       start_seconds=3.4,end_seconds=6.2,method='encoded-video-viewing',evidence='在当前实际视频的画面中辨认出原图。')
        return [dict(placement,**kwargs)]

    def view(self):return library(self.course,self.sources,self.artifacts,self.coverage)

    def test_retained_and_storyboard_planned_dont_count_as_screened(self):
        self.save('source_images.json',dict(review_status='reviewed',images=[dict(source_id='SRC-photo',sha256=self.source_hash,decision='include',scene_ids=['X'])]))
        [item]=self.view()
        self.assertEqual(item['status'],'unverified')
        self.assertIn('分镜',item['reason'])
        self.assertEqual(item['source_points'][0]['disposition'],'retained')

    def test_current_actual_usage_only(self):
        self.receipt(placements=self.placements())
        [item]=self.view();self.assertEqual(item['status'],'used')
        self.assertEqual(item['placements'][0]['start_seconds'],3.4)
        self.artifact['sha256']='b'*64
        self.assertEqual(self.view()[0]['status'],'unverified')
        self.receipt(placements=self.placements())
        self.photo.write_bytes(b'superseded photo')
        self.assertEqual(self.view()[0]['status'],'unverified')

    def test_exclusion_requires_reason_and_owned_preview_path(self):
        self.sources.append(dict(id='out',title='outside',kind='file',location='../../secret.jpg'))
        self.receipt(status='excluded',reason='同一图片的重复文件')
        [item]=self.view();self.assertEqual(item['status'],'unused')
        self.assertEqual(item['path'],self.path)
        self.assertEqual(item['reason'],'同一图片的重复文件')
        self.receipt(status='excluded',reason=' ')
        self.assertEqual(self.view()[0]['status'],'unverified')

    def test_non_image_has_same_evidence_requirement_and_readable_segment_label(self):
        self.photo.rename(self.root/'inputs/shop.pdf')
        self.sources[0]['location']='../inputs/shop.pdf'
        self.receipt(placements=self.placements(segment_label='流程演示'))
        [item]=self.view()
        self.assertEqual(item['kind'],'file')
        self.assertEqual(item['status'],'used')
        self.assertEqual(item['placements'][0]['segment_label'],'流程演示')
        self.receipt(placements=self.placements())
        self.assertEqual(self.view()[0]['placements'][0]['segment_label'],'pilot.mp4')

    def test_reject_technical_reference_invalid_range_and_malformed_input(self):
        for placement in [self.placements(method='scene-graph'),self.placements(end_seconds=20),self.placements(evidence='')]:
            self.receipt(placements=placement)
            self.assertEqual(self.view()[0]['status'],'unverified')
        (self.project/'material-video-usage.json').write_text('{')
        self.assertEqual(self.view()[0]['status'],'unverified')


if __name__=='__main__':unittest.main()
