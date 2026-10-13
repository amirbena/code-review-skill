import os, re, subprocess, sys, json, shutil
S=sys.argv[1]; REPO=os.path.join(S,'repo-study'); OUT=os.path.join(S,'out','study'); os.makedirs(OUT,exist_ok=True)
JH=os.environ['JAVA_HOME']
CP=open(os.path.join(S,'harness','cp.txt')).read().strip()
ENV={'HOME':os.path.join(S,'home'),'PATH':'/usr/bin:/bin','JAVA_HOME':JH}
SBX='(version 1)(allow default)(deny network*)'
def baseline(proj,args,repo=REPO,offline=True):
    d=os.path.join(S,'projects',proj); of=os.path.join(OUT,proj+'.base.txt')
    if os.path.exists(of): os.remove(of)
    cmd=['/opt/homebrew/bin/mvn','-B','-s',S+'/empty-settings.xml','-gs',S+'/empty-settings.xml','-Dmaven.repo.local='+repo]+(['-o'] if offline else [])+args+['org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree','-DoutputFile='+of]
    r=subprocess.run(['sandbox-exec','-p',SBX]+cmd,cwd=d,env=ENV,capture_output=True,text=True,timeout=180)
    if r.returncode!=0 or not os.path.exists(of):
        err=[l for l in (r.stdout+r.stderr).splitlines() if '[ERROR]' in l]
        return {'status':'ERROR','msg':(err[0] if err else 'no output')[:300],'warn':[l for l in r.stdout.splitlines() if 'WARN' in l][:5]}
    tree=[]
    for l in open(of).read().splitlines()[1:]:
        m=re.match(r'^((?:[|]  |   )*)[+\\]- (\S+?)( \(optional\))?( .*)?$',l)
        if not m: continue
        depth=len(m.group(1))//3; gav=m.group(2); parts=gav.split(':'); scope=parts[-1]; core=':'.join(parts[:-1])
        tree.append((depth,core,scope,bool(m.group(3))))
    warns=[l for l in r.stdout.splitlines() if 'WARN' in l][:5]
    return {'status':'OK','tree':tree,'warn':warns}
def harness(proj,args,repo=REPO,pom=None):
    of=os.path.join(OUT,proj+'.harness.txt')
    pom=pom or os.path.join(S,'projects',proj,'pom.xml')
    cmd=[JH+'/bin/java','-cp',S+'/harness/classes:'+CP,'MetaResolve','--pom',pom,'--repo',repo,'--out',of]+args
    r=subprocess.run(['sandbox-exec','-p',SBX]+cmd,env=ENV,capture_output=True,text=True,timeout=120,cwd=S)
    if not os.path.exists(of): return {'status':'CRASH','msg':(r.stderr or r.stdout)[-400:]}
    tree=[];events=[];err=None
    for l in open(of).read().splitlines():
        if l.startswith('#EVENT\t'): events.append(l.split('\t',1)[1])
        elif l.startswith('#ERROR'): err=l.split('\t',2)[2][:300]
        else:
            d,gav,sc,opt=l.split('\t'); tree.append((int(d),gav,sc,opt=='true'))
    if err: return {'status':'MODEL-ERROR','msg':err,'events':events}
    return {'status':'OK','tree':tree,'events':[e for e in events if not e.startswith('IGNORED-PROJECT-REPOSITORY central')]}
def unsupported(proj):
    d=os.path.join(S,'projects',proj); r=[]
    if os.path.exists(os.path.join(d,'.mvn','extensions.xml')): r.append('.mvn/extensions.xml present')
    return r
# scenario: (id, project, baseline args, harness args, note)
SC=[
('S1a','s1-parent-from-cache',[],[]),('S1b','s1-parent-relpath',[],[]),
('S2a','s2-bom',[],[]),('S2b','s2-bom-vs-explicit',[],[]),
('S3a','s3-mgmt-transitive-version',[],[]),('S3b','s3-mgmt-transitive-scope',[],[]),('S3c','s3-mgmt-vs-direct-version',[],[]),
('S4','s4-transitives',[],[]),
('S5a','s5-exclusion-single',[],[]),('S5b','s5-exclusion-wildcard',[],[]),('S5c','s5-exclusion-mid',[],[]),
('S6a','s6-nearest-depth',[],[]),('S6b','s6-tie-first-declared',[],[]),('S6c','s6-tie-swapped',[],[]),
('S7','s7-scopes',[],[]),('S8','s8-optional',[],[]),
('S9a','s9-profiles',[],[]),('S9b','s9-profiles',['-Dfeature=1'],['-Dfeature=1']),
('S9c','s9-profiles',['-Dfeature=1','-Pcli-only'],['-Dfeature=1','--profile','cli-only']),
('S9d','s9-profiles',['-Pmgmt'],['--profile','mgmt']),
('S9e','s9-profiles-nofile',[],[]),('S9f','s9-parent-profile',['-Dfeature=1'],['-Dfeature=1']),
('S9g','s9-profiles',['-Dfeature=1'],[]),   # environment/profile selection NOT mirrored in harness
('S9h','s9-profiles',['-P','!by-jdk'],['--profile','!by-jdk']),
('S10a','s10-missing-transitive-pom',[],[]),('S10b','s10-missing-direct-pom',[],[]),('S10c','s10-missing-parent',[],[]),('S10d','s10-missing-bom',[],[]),
('S11a','s11-families-both',[],[]),('S11b','s11-families-excluded',[],[]),('S11c','s11-families-optional',[],[]),('S11d','s11-families-test-scope',[],[]),
('S12','s12-relocation',[],[]),('S13a','s13-range-no-metadata',[],[]),('S13b','s13-range-with-metadata',[],[]),
('S14','s14-extensions-present',[],[]),('S15','s15-declared-repository',[],[]),
]
INC=['3.0.0','3.0.1','3.0.2','3.0.3','3.0.4','3.0.5','3.1.0','3.1.1','3.1.2','3.1.3','3.1.4','3.1.5','3.1.6','3.1.7','3.1.8','3.1.9','3.0.6']
SC+= [('I'+v,'inc-'+v,[],[]) for v in INC]+[('I'+v+'-simple','inc-'+v,[],['--simple-lrm']) for v in INC[:2]]
ONLY=sys.argv[2] if len(sys.argv)>2 else ''
RES=sys.argv[3] if len(sys.argv)>3 else 'results.json'
res=[]
for sid,proj,ba,ha in [x for x in SC if (x[0].startswith('I')==(ONLY=='inc') if ONLY else True)]:
    b=baseline(proj,ba); h=harness(proj,ha)
    row={'id':sid,'project':proj,'base_args':ba,'harness_args':ha,'unsupported':unsupported(proj),'baseline':b['status'],'harness':h['status']}
    if b['status']=='OK' and h['status']=='OK':
        bt,ht=b['tree'],h['tree']
        row['equal']=bt==ht
        row['only_baseline']=[x for x in bt if x not in ht]; row['only_harness']=[x for x in ht if x not in bt]
        row['order_only']=(sorted(bt)==sorted(ht)) and bt!=ht
    row['base_msg']=b.get('msg',''); row['base_warn']=b.get('warn',[]); row['h_msg']=h.get('msg',''); row['h_events']=h.get('events',[])
    row['base_tree']=b.get('tree'); row['h_tree']=h.get('tree')
    res.append(row)
json.dump(res,open(os.path.join(S,'out','study',RES),'w'),indent=1)
for r in res:
    eq=r.get('equal'); 
    print(r['id'].ljust(5),r['project'].ljust(30),'base='+r['baseline'].ljust(5),'harn='+r['harness'].ljust(11),'EQUAL' if eq else ('DIFF' if eq is False else '-'),('order-only' if r.get('order_only') else ''), r['unsupported'] or '', (r['base_msg'][:90] if r['baseline']!='OK' else ''), ([e[:70] for e in r['h_events']] if r['h_events'] else ''))
