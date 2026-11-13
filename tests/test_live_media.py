from pathlib import Path
from types import SimpleNamespace
import json,sys,tempfile,time,unittest,os,hashlib,ast
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/corporate-training-motion/workbench'))
from live_media import index,publish_render_preview,publish_saved_audio,_verified_digest
class LiveMediaTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.project=self.root/'project';self.project.mkdir();self.file=self.project/'workbench.json';self.file.write_text('{}');self.space=SimpleNamespace(root=self.root,file=self.file)
 def tearDown(self):self.tmp.cleanup()
 def put(self,path,body):
  p=self.project/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body);return p
 def manifest(self,items):self.put('work/live-media.json',json.dumps({'items':items}).encode())
 def read(self):return index(self.space,now=time.time()+2)['items']
 def test_manifest_only_indexes_saved_in_course_media(self):
  self.put('media/a.png',b'\x89PNG\r\n\x1a\n'+b'fixture');self.manifest([{'path':'media/a.png','label':'画面一','segment_id':'S1'},{'path':'media/missing.wav'}]);items=self.read();self.assertEqual(len(items),1);self.assertEqual(items[0]['kind'],'image');self.assertEqual(items[0]['segment_id'],'S1');self.assertEqual(items[0]['status'],'saved')
 def test_rejects_escape_hidden_wrong_magic_and_kind(self):
  outside=self.root.parent/(self.root.name+'-outside.png');outside.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
  try:
   self.put('media/secret.png',b'password=secret');self.put('.private/a.png',b'\x89PNG\r\n\x1a\nfixture');self.put('media/good.png',b'\x89PNG\r\n\x1a\nfixture');(self.project/'media/link.png').symlink_to(outside)
   self.manifest([{'path':str(outside)},{'path':'../../'+outside.name},{'path':'media/link.png'},{'path':'media/secret.png'},{'path':'.private/a.png'},{'path':'media/good.png','kind':'audio'}]);self.assertEqual(self.read(),[])
  finally:outside.unlink()
 def test_bound_audio_and_storyboard_preview_appear_without_manifest(self):
  self.put('voice/one.wav',b'RIFF'+b'0000'+b'WAVE'+b'fixture');self.file.write_text(json.dumps({'media':{'audio':'voice/one.wav'}}));self.put('frames/one.png',b'\x89PNG\r\n\x1a\nfixture');self.put('storyboard.json',json.dumps({'segments':[{'id':'S1','selected':'A','options':[{'id':'A','preview_file':'frames/one.png'}]}]}).encode());items=self.read();self.assertEqual({i['kind'] for i in items},{'audio','image'});self.assertTrue(all(i['current'] for i in items))
 def test_digest_mismatch_excluded_and_replaced_bytes_get_new_version(self):
  self.put('a.png',b'\x89PNG\r\n\x1a\nfirst');self.manifest([{'path':'a.png','sha256':'0'*64}]);self.assertEqual(self.read(),[]);self.manifest([{'path':'a.png'}]);old=self.read()[0];self.put('a.png',b'\x89PNG\r\n\x1a\nsecond-longer');new=self.read()[0];self.assertEqual(old['id'],new['id']);self.assertNotEqual(old['bytes'],new['bytes'])
 def test_renderer_publishes_atomic_jpeg_and_index_discovers_it(self):
  folder=self.project/'work/workbench/exports/abcdef123456';folder.mkdir(parents=True)
  publish_render_preview(folder,b'\xff\xd8\xfffixture');items=index(self.space)['items'];self.assertEqual(len(items),1);self.assertEqual(items[0]['source'],'render_preview');self.assertFalse((folder/'live-preview.pending').exists())
 def test_tts_receipt_is_scoped_and_auto_discovered(self):
  p=self.put('voice/segment-01.wav',b'RIFF0000WAVEfixture');self.assertFalse(publish_saved_audio(p));self.put('course-state.json',b'{}');self.assertTrue(publish_saved_audio(p));items=self.read();self.assertEqual(len(items),1);self.assertEqual(items[0]['source'],'saved_audio_receipt');self.assertIn('sha256',items[0])
 def test_digest_cache_reuses_unchanged_file_and_invalidates_replacement(self):
  _verified_digest.cache_clear();p=self.put('a.png',b'\x89PNG\r\n\x1a\nfirst');digest=hashlib.sha256(p.read_bytes()).hexdigest();self.manifest([{'path':'a.png','sha256':digest}])
  original=hashlib.file_digest
  with patch('live_media.hashlib.file_digest',wraps=original) as hashing:
   self.assertEqual(len(self.read()),1);self.assertEqual(len(self.read()),1);self.assertEqual(hashing.call_count,1)
   before=p.stat();p.write_bytes(b'\x89PNG\r\n\x1a\nother');os.utime(p,ns=(before.st_atime_ns,before.st_mtime_ns+1000000))
   self.assertEqual(self.read(),[]);self.assertEqual(hashing.call_count,2)
  self.assertEqual(_verified_digest.cache_info().maxsize,256)
 def test_preview_write_is_nonblocking_in_actual_render_loop(self):
  tree=ast.parse((ROOT/'skills/corporate-training-motion/workbench/render_worker.py').read_text())
  guarded=[node for node in ast.walk(tree) if isinstance(node,ast.Try) and any(isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='publish_render_preview' for stmt in node.body for call in ast.walk(stmt))]
  handler=next(handler for node in guarded for handler in node.handlers if isinstance(handler.type,ast.Name) and handler.type.id=='OSError')
  self.assertFalse(any(isinstance(node,ast.Raise) for node in ast.walk(handler)))
  self.assertTrue(any(isinstance(node,ast.If) for node in handler.body))
 def test_bad_manifest_is_nonfatal(self):
  self.put('work/live-media.json',b'{broken');self.assertEqual(self.read(),[])
if __name__=='__main__':unittest.main()
