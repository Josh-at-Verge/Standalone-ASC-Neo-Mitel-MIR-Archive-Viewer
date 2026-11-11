import importlib.util,json,tempfile,threading,unittest,urllib.request
from pathlib import Path

spec=importlib.util.spec_from_file_location('archive',Path(__file__).resolve().parents[1]/'server.py')
archive=importlib.util.module_from_spec(spec);spec.loader.exec_module(archive)

class MP3ArchiveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  archive.ROOT=self.root;archive.DB=self.root/'index.sqlite3';archive.init()
 def tearDown(self):self.tmp.cleanup()
 def xml(self,rel,audio=None):
  p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True)
  tag='' if audio is None else f'<conversationFileName>{audio}</conversationFileName>'
  p.write_text(f'<conversation><id>demo</id><starttime>2025-10-01 09:00:00</starttime><duration>13000</duration>{tag}</conversation>')
 def audio(self,rel):
  p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'ID3'+bytes(range(256)));return p
 def rows(self):
  with archive.connect() as c:return {r['xml']:dict(r) for r in c.execute('SELECT * FROM calls')}
 def test_legacy_names_case_and_duplicate_basenames(self):
  self.xml('a/call.xml','call.wav');self.xml('b/call.xml','call.WAV');self.xml('c/missing.xml','call.wav')
  self.audio('a/CALL.MP3');self.audio('b/call.mp3');archive.scan();r=self.rows()
  self.assertEqual(r['a/call.xml']['audio'],'a/CALL.MP3');self.assertEqual(r['b/call.xml']['audio'],'b/call.mp3')
  self.assertIsNone(r['c/missing.xml']['audio'])
 def test_filename_fallback_and_unique_other_folder(self):
  self.xml('a/fallback.xml');self.audio('a/fallback.mp3')
  self.xml('a/explicit.xml','other.MP3');self.audio('elsewhere/other.mp3');archive.scan();r=self.rows()
  self.assertEqual(r['a/fallback.xml']['audioName'],'fallback.mp3');self.assertEqual(r['a/explicit.xml']['audio'],'elsewhere/other.mp3')
 def test_existing_wav_index_migrates_without_reparsing(self):
  self.xml('call.xml','call.wav');p=self.audio('call.mp3');archive.scan()
  with archive.connect() as c:c.execute("UPDATE calls SET audioName='call.wav',audio='call.wav'")
  original=archive.parse
  try:
   archive.parse=lambda p:(_ for _ in ()).throw(AssertionError('unchanged XML must not be parsed'))
   archive.scan();r=self.rows()['call.xml'];self.assertEqual(r['audioName'],'call.mp3');self.assertEqual(r['audio'],'call.mp3')
   p.unlink();archive.scan();self.assertIsNone(self.rows()['call.xml']['audio'])
  finally:archive.parse=original
 def test_wav_only_is_unavailable(self):
  self.xml('call.xml','call.wav');self.audio('call.wav');archive.scan();self.assertIsNone(self.rows()['call.xml']['audio'])
 def test_mp3_http_type_range_and_csv(self):
  self.xml('call.xml','call.wav');p=self.audio('call.mp3');archive.scan()
  http=archive.ThreadingHTTPServer(('127.0.0.1',0),archive.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
  base=f'http://127.0.0.1:{http.server_port}'
  try:
   with urllib.request.urlopen(base+'/api/search?available=1') as r:self.assertEqual(json.load(r)['count'],1)
   req=urllib.request.Request(base+'/api/audio?id=call.xml',headers={'Range':'bytes=0-9'})
   with urllib.request.urlopen(req) as r:
    self.assertEqual(r.status,206);self.assertEqual(r.headers['Content-Type'],'audio/mpeg');self.assertEqual(r.read(),p.read_bytes()[:10])
   with urllib.request.urlopen(base+'/api/export') as r:self.assertIn('call.mp3',r.read().decode())
  finally:http.shutdown();http.server_close()

if __name__=='__main__':unittest.main()
