#!/usr/bin/env python3
"""Local recording archive browser. Python 3.10+, standard library only."""
import argparse,csv,io,json,mimetypes,os,re,sqlite3,threading,time,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
BASE=Path(__file__).resolve().parent
STATE={'busy':False,'message':'Ready','errors':''}
LOCK=threading.Lock()
ROOT=None; DB=None

def connect():
 c=sqlite3.connect(DB,timeout=60);c.row_factory=sqlite3.Row;return c

def init():
 with connect() as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.execute('CREATE TABLE IF NOT EXISTS calls (xml TEXT PRIMARY KEY,mtime INTEGER,size INTEGER,id TEXT,start TEXT,end TEXT,duration REAL,direction TEXT,caller TEXT,called TEXT,extensions TEXT,agents TEXT,audioName TEXT,audio TEXT,text TEXT)')
  c.execute('CREATE INDEX IF NOT EXISTS call_start ON calls(start)')
  c.execute('CREATE INDEX IF NOT EXISTS call_direction ON calls(direction,start)')
  c.create_function('digits',1,lambda x:re.sub(r'\D','',str(x or '')),deterministic=True)

def mp3_name(name):
 # Legacy XML exports and cached rows may still name a WAV file.
 return Path(name.replace('\\','/')).with_suffix('.mp3').as_posix()

def parse(path):
 data=path.read_bytes()
 if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('DTD/entity declarations are unsupported')
 r=ET.fromstring(data)
 if r.tag!='conversation':raise ValueError('Not a conversation XML')
 get=lambda tag:(r.findtext(tag) or '').strip()
 ext=sorted(set((x.text or '').strip() for x in r.findall('participants/extension/number'))|{get('firstConnectedNumber')})
 agents=sorted(set((x.text or '').strip() for x in r.findall('participants/pbxAgentID'))|{get('firstConnectedPbxAgentID')})
 return dict(id=get('id') or str(path.relative_to(ROOT)),start=get('starttime'),end=get('endtime'),duration=float(get('duration') or 0),direction=get('direction'),caller=get('callerNumber'),called=get('calledNumber'),extensions=json.dumps([x for x in ext if x]),agents=json.dumps([x for x in agents if x]),audioName=mp3_name(get('conversationFileName') or path.name),text=' '.join(' '.join(r.itertext()).split()).lower())

def scan():
 errors=[]
 try:
  STATE.update(message='Discovering XML and MP3 files…',errors='')
  xml=[];names={};audio_files=set();paths={}
  def fail(e):raise e
  for parent,dirs,fs in os.walk(ROOT,onerror=fail,followlinks=False):
   dirs[:]=[d for d in dirs if not Path(parent,d).is_symlink()]
   for name in fs:
    p=Path(parent,name)
    if p.is_symlink():continue
    rel=p.relative_to(ROOT).as_posix()
    if p.suffix.lower()=='.xml':xml.append((p,rel))
    elif p.suffix.lower()=='.mp3':
     audio_files.add(rel);key=name.lower();names[key]=None if key in names else rel
     key=rel.lower();paths[key]=None if key in paths else rel
  with connect() as c:
   old={r['xml']:(r['mtime'],r['size']) for r in c.execute('SELECT xml,mtime,size FROM calls')}
   seen=set()
   for i,(p,rel) in enumerate(xml):
    seen.add(rel)
    try:
     s=p.stat()
     if old.get(rel)==(s.st_mtime_ns,s.st_size):
      r=c.execute('SELECT audioName FROM calls WHERE xml=?',(rel,)).fetchone();audio_name=mp3_name(r[0])
     else:
      r=parse(p);audio_name=r['audioName'];r.update(xml=rel,mtime=s.st_mtime_ns,size=s.st_size,audio=None)
      cols=list(r);c.execute('INSERT OR REPLACE INTO calls ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',[r[k] for k in cols])
     exact=(Path(rel).parent/Path(audio_name.replace('\\','/'))).as_posix()
     audio=exact if exact in audio_files else paths.get(exact.lower()) or names.get(Path(audio_name).name.lower())
     c.execute('UPDATE calls SET audio=?,audioName=? WHERE xml=?',(audio,audio_name,rel))
    except Exception as e:
     errors.append(f'{rel}: {e}');c.execute('DELETE FROM calls WHERE xml=?',(rel,))
    if i%250==0:
     c.commit();STATE['message']=f'Indexing {i+1:,} / {len(xml):,} XML files…'
   for stale in old.keys()-seen:c.execute('DELETE FROM calls WHERE xml=?',(stale,))
  STATE['message']=f'Index ready. Scanned {len(xml):,} XML files; {len(errors):,} errors. Unchanged XML files were reused.'
 except Exception as e:STATE['message']='Indexing failed: '+str(e)
 finally:
  STATE['errors']='\n'.join(errors[:15]);STATE['busy']=False

def start_scan():
 with LOCK:
  if STATE['busy']:return
  STATE['busy']=True;threading.Thread(target=scan,daemon=True).start()

def query(params):
 clauses=[];args=[]
 def add(sql,*v):clauses.append(sql);args.extend(v)
 def like(s):return '%'+s.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
 for key,col in [('q','text'),('caller','caller'),('called','called'),('extension','extensions'),('agent','agents')]:
  if params.get(key):
   val=params[key];num=re.sub(r'\D','',val)
   if key in ('extension','agent'):
    sub="EXISTS (SELECT 1 FROM json_each("+col+") WHERE lower(value) LIKE ? ESCAPE '\\'"
    vals=[like(val.lower())]
    if num:sub+=" OR digits(value) LIKE ? ESCAPE '\\'";vals.append(like(num))
    add(sub+')',*vals);continue
   if num:add(f"(lower({col}) LIKE ? ESCAPE '\\' OR digits({col}) LIKE ? ESCAPE '\\')",like(val.lower()),like(num))
   else:add(f"lower({col}) LIKE ? ESCAPE '\\'",like(val.lower()))
 if params.get('direction'):add('direction=?',params['direction'])
 if params.get('from'):add('start>=?',params['from'])
 if params.get('to'):add('start<?',params['to']+'\uffff')
 if params.get('min'):add('duration>=?',float(params['min'])*1000)
 if params.get('max'):add('duration<=?',float(params['max'])*1000)
 if params.get('available') in ('0','1'):add('audio IS '+('NOT NULL' if params['available']=='1' else 'NULL'))
 return (' WHERE '+' AND '.join(clauses) if clauses else ''),args

def row(r):
 r=dict(r);r['key']=r['xml'];r['extensions']=json.loads(r['extensions']);r['agents']=json.loads(r['agents']);return r

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def end_headers(self):
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');super().end_headers()
 def safe_request(self):
  # This server intentionally accepts only local browser requests.
  host=self.headers.get('Host','').split(':')[0]
  return host in ('localhost','127.0.0.1') and (not self.headers.get('Origin') or self.headers['Origin'] in (f'http://localhost:{self.server.server_port}',f'http://127.0.0.1:{self.server.server_port}'))
 def output(self,obj,status=200):
  b=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_POST(self):
  if not self.safe_request():return self.output({'error':'Local origin required'},403)
  if self.path!='/api/reindex':return self.output({'error':'Not found'},404)
  start_scan();self.output({'started':True})
 def do_GET(self):
  if not self.safe_request():return self.output({'error':'Local origin required'},403)
  try:self.get()
  except (BrokenPipeError,ConnectionResetError):pass
  except (ValueError,sqlite3.Error) as e:self.output({'error':str(e)},400)
 def get(self):
  url=urllib.parse.urlsplit(self.path);params={k:v[-1] for k,v in urllib.parse.parse_qs(url.query).items()}
  if url.path=='/api/status':
   with connect() as c:r=c.execute('SELECT count(*) count,min(start) first,max(start) last FROM calls').fetchone()
   return self.output({**dict(r),**STATE,'root':str(ROOT),'localArchive':True})
  if url.path in ('/api/search','/api/export'):
   where,args=query(params);order='ASC' if params.get('sort')=='asc' else 'DESC'
   with connect() as c:
    c.create_function('digits',1,lambda x:re.sub(r'\D','',str(x or '')))
    sql='SELECT * FROM calls'+where+' ORDER BY start '+order+',xml'
    if url.path=='/api/search':
     count=c.execute('SELECT count(*) FROM calls'+where,args).fetchone()[0];page=max(0,int(params.get('page','0')))
     return self.output({'count':count,'rows':[row(r) for r in c.execute(sql+' LIMIT 50 OFFSET ?',args+[page*50])]})
    self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="call-search-results.csv"');self.end_headers();self.wfile.write(b'\xef\xbb\xbf')
    cols=['id','start','end','direction','caller','called','extensions','agents','duration','xml','audioName'];buffer=io.StringIO();writer=csv.writer(buffer)
    def emit(vals):
     buffer.seek(0);buffer.truncate();writer.writerow([("'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v) for v in vals]);self.wfile.write(buffer.getvalue().encode())
    emit(cols)
    for r in c.execute(sql,args):
     r=row(r);emit(['; '.join(r[k]) if isinstance(r[k],list) else r[k] for k in cols])
    return
  if url.path=='/api/audio':
   with connect() as c:r=c.execute('SELECT audio FROM calls WHERE xml=?',(params.get('id',''),)).fetchone()
   if not r or not r[0]:return self.output({'error':'No matching audio'},404)
   p=(ROOT/r[0]).resolve()
   if not p.is_relative_to(ROOT) or not p.is_file():return self.output({'error':'Audio no longer available'},404)
   return self.serve_file(p,'audio/mpeg',ranges=True)
  static={'/':'index.html','/index.html':'index.html','/sample-metadata.json':'sample-metadata.json'}
  if url.path not in static:return self.output({'error':'Not found'},404)
  p=BASE/'dist'/static[url.path];return self.serve_file(p,mimetypes.guess_type(str(p))[0] or 'application/octet-stream')
 def serve_file(self,p,mime,ranges=False):
  size=p.stat().st_size;start=0;end=size-1;partial=False
  if ranges and self.headers.get('Range'):
   m=re.fullmatch(r'bytes=(\d*)-(\d*)',self.headers['Range'])
   if not m or not any(m.groups()):self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
   a,b=m.groups()
   if a:start=int(a);end=min(int(b),end) if b else end
   else:start=max(0,size-int(b))
   if start>end or start>=size:self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
   partial=True
  self.send_response(206 if partial else 200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(max(0,end-start+1)))
  if ranges:self.send_header('Accept-Ranges','bytes')
  if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  self.end_headers()
  with p.open('rb') as f:
   f.seek(start);left=end-start+1
   while left>0:
    data=f.read(min(left,256*1024))
    if not data:break
    self.wfile.write(data);left-=len(data)

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('recordings',help='Root folder containing exported XML and MP3 files');ap.add_argument('--port',type=int,default=8765);ap.add_argument('--db',help='SQLite index location (default: beside server, unique per archive)');a=ap.parse_args();ROOT=Path(a.recordings).expanduser().resolve()
 if not ROOT.is_dir():ap.error('Recordings folder does not exist')
 import hashlib
 DB=Path(a.db).resolve() if a.db else BASE/('archive-'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]+'.sqlite3')
 init();start_scan();http=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);print(f'Call Archive: http://127.0.0.1:{a.port}\nRecordings: {ROOT}\nIndex: {DB}\nPress Ctrl+C to stop.',flush=True)
 try:http.serve_forever()
 except KeyboardInterrupt:http.server_close()
