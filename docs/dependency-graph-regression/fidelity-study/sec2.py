import os,subprocess,sys,time,shutil,json,hashlib,stat
S=sys.argv[1]; JH=os.environ['JAVA_HOME']
CP=open(S+'/harness/cp.txt').read().strip(); ENV={'HOME':S+'/home','PATH':'/usr/bin:/bin','JAVA_HOME':JH}
SBX='(version 1)(allow default)(deny network*)'
out={}
# ---- read-only cache + no-write proof
def snap(root):
    h=hashlib.sha256(); n=0
    for dp,dn,fn in sorted(os.walk(root)):
        for f in sorted(fn):
            p=os.path.join(dp,f); st=os.stat(p); h.update(f'{p}{st.st_size}{st.st_mtime_ns}'.encode()); n+=1
    return n,h.hexdigest()[:16]
ro=S+'/repo-ro'
if os.path.exists(ro):
    for dp,dn,fn in os.walk(ro):
        os.chmod(dp,0o755)
        for f in fn: os.chmod(os.path.join(dp,f),0o644)
    shutil.rmtree(ro)
shutil.copytree(S+'/repo-study',ro)
for dp,dn,fn in os.walk(ro):
    for f in fn: os.chmod(os.path.join(dp,f),0o444)
    os.chmod(dp,0o555)
b=snap(ro); ok=[]
for proj in ['s2-bom','s9-profiles','inc-3.1.8','inc-3.0.0','s10-missing-transitive-pom']:
    r=subprocess.run(['sandbox-exec','-p',SBX,JH+'/bin/java','-cp',S+'/harness/classes:'+CP,'MetaResolve','--pom',f'{S}/projects/{proj}/pom.xml','--repo',ro,'--out',f'{S}/out/ro-{proj}.txt'],env=ENV,capture_output=True,text=True,cwd=S)
    ok.append((proj,r.returncode,os.path.getsize(f'{S}/out/ro-{proj}.txt')>0))
a=snap(ro); out['readonly_cache']={'runs':ok,'before':b,'after':a,'unchanged':a==b}
# ---- pathological inputs
R=S+'/repo-dos'
shutil.rmtree(R,ignore_errors=True); shutil.copytree(S+'/repo-study',R)
def inst(g,a,v,xml):
    d=os.path.join(R,*g.split('.'),a,v); os.makedirs(d,exist_ok=True); open(os.path.join(d,f'{a}-{v}.pom'),'w').write(xml)
def P(a,deps='',parent='',mgmt='',pack=''):
    return f'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>{parent}<groupId>org.dos</groupId><artifactId>{a}</artifactId><version>1</version>{pack}'+(f'<dependencyManagement><dependencies>{mgmt}</dependencies></dependencyManagement>' if mgmt else '')+(f'<dependencies>{deps}</dependencies>' if deps else '')+'</project>'
dep=lambda a,v='1':f'<dependency><groupId>org.dos</groupId><artifactId>{a}</artifactId><version>{v}</version></dependency>'
par=lambda a:f'<parent><groupId>org.dos</groupId><artifactId>{a}</artifactId><version>1</version><relativePath/></parent>'
imp=lambda a:f'<dependency><groupId>org.dos</groupId><artifactId>{a}</artifactId><version>1</version><type>pom</type><scope>import</scope></dependency>'
projs={}
# a parent cycle
inst('org.dos','pa','1',P('pa',parent=par('pb'),pack='<packaging>pom</packaging>')); inst('org.dos','pb','1',P('pb',parent=par('pa'),pack='<packaging>pom</packaging>'))
projs['dos-parent-cycle']=P('app',parent=par('pa'))
# b import cycle
inst('org.dos','ba','1',P('ba',mgmt=imp('bb'),pack='<packaging>pom</packaging>')); inst('org.dos','bb','1',P('bb',mgmt=imp('ba'),pack='<packaging>pom</packaging>'))
projs['dos-import-cycle']=P('app',mgmt=imp('ba'))
# c deep chain
N=1500
for i in range(N): inst('org.dos',f'c{i}','1',P(f'c{i}',deps=dep(f'c{i+1}') if i<N-1 else ''))
projs['dos-deep-chain-1500']=P('app',deps=dep('c0'))
# d wide
W=5000
for i in range(W): inst('org.dos',f'w{i}','1',P(f'w{i}'))
projs['dos-wide-5000']=P('app',deps=''.join(dep(f'w{i}') for i in range(W)))
# f diamond lattice, distinct versions per layer
L=22
for l in range(L):
    for k in ('a','b'):
        nxt=''.join(dep(f'l{l+1}{kk}',str(l+1)+kk) for kk in ('a','b')) if l<L-1 else ''
        inst('org.dos',f'l{l}{k}',str(l)+k,P(f'l{l}{k}',deps=nxt))
projs['dos-lattice-22']=P('app',deps=dep('l0a','0a')+dep('l0b','0b'))
# e entity expansion + XXE
bl='<!DOCTYPE project [<!ENTITY a0 "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">'+''.join(f'<!ENTITY a{i+1} "'+f'&a{i};'*10+'">' for i in range(9))+']>'
projs['dos-billion-laughs']=bl+P('app',deps=dep('c0')).replace('<artifactId>app</artifactId>','<artifactId>&a9;</artifactId>')
projs['dos-xxe-file']='<!DOCTYPE project [<!ENTITY x SYSTEM "file:///etc/hosts">]>'+P('app').replace('<artifactId>app</artifactId>','<artifactId>&x;</artifactId>')
res={}
for name,xml in projs.items():
    d=f'{S}/projects/{name}'; os.makedirs(d,exist_ok=True); open(d+'/pom.xml','w').write(xml)
    t=time.time()
    try:
        r=subprocess.run(['sandbox-exec','-p',SBX,JH+'/bin/java','-Xmx256m','-cp',S+'/harness/classes:'+CP,'MetaResolve','--pom',d+'/pom.xml','--repo',R,'--out',f'{S}/out/{name}.h.txt'],env=ENV,capture_output=True,text=True,cwd=S,timeout=90)
        h=open(f'{S}/out/{name}.h.txt').read() if os.path.exists(f'{S}/out/{name}.h.txt') else ''
        lines=h.splitlines(); nodes=sum(1 for l in lines if l and not l.startswith('#'))
        hs=f'rc={r.returncode} nodes={nodes} '+(next((l for l in lines if l.startswith('#ERROR')),'')[:200])+(' stderr='+r.stderr.strip().splitlines()[-1][:120] if r.returncode and r.stderr.strip() else '')
    except subprocess.TimeoutExpired: hs='TIMEOUT>90s'
    ht=round(time.time()-t,1)
    t=time.time()
    try:
        r=subprocess.run(['sandbox-exec','-p',SBX,'/opt/homebrew/bin/mvn','-B','-o','-s',S+'/empty-settings.xml','-gs',S+'/empty-settings.xml','-Dmaven.repo.local='+R,'org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree','-DoutputFile='+f'{S}/out/{name}.b.txt'],env=dict(ENV,MAVEN_OPTS='-Xmx256m'),capture_output=True,text=True,cwd=d,timeout=90)
        err=[l for l in r.stdout.splitlines() if '[ERROR]' in l]
        bs=f'rc={r.returncode} '+(err[0][:200] if err else '')
    except subprocess.TimeoutExpired: bs='TIMEOUT>90s'
    res[name]={'harness':hs,'harness_s':ht,'baseline':bs,'baseline_s':round(time.time()-t,1)}
    print(name,res[name],flush=True)
out['pathological']=res
json.dump(out,open(S+'/out/study/sec2.json','w'),indent=1); print(json.dumps(out['readonly_cache']))
