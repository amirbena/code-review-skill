import os, sys, shutil
S=sys.argv[1]; REPO=os.path.join(S,'repo-study'); PROJ=os.path.join(S,'projects')
shutil.rmtree(PROJ,ignore_errors=True); os.makedirs(PROJ)
def dep(g,a,v=None,scope=None,opt=False,excl=(),typ=None):
    s=f"<dependency><groupId>{g}</groupId><artifactId>{a}</artifactId>"
    if v: s+=f"<version>{v}</version>"
    if typ: s+=f"<type>{typ}</type>"
    if scope: s+=f"<scope>{scope}</scope>"
    if opt: s+="<optional>true</optional>"
    if excl: s+="<exclusions>"+"".join(f"<exclusion><groupId>{eg}</groupId><artifactId>{ea}</artifactId></exclusion>" for eg,ea in excl)+"</exclusions>"
    return s+"</dependency>"
def pom(g,a,v,deps=(),mgmt=(),parent=None,props=None,pack=None,profiles="",extra=""):
    s='<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
    if parent: s+=f"<parent><groupId>{parent[0]}</groupId><artifactId>{parent[1]}</artifactId><version>{parent[2]}</version>"+(f"<relativePath>{parent[3]}</relativePath>" if len(parent)>3 else "<relativePath/>")+"</parent>"
    if g: s+=f"<groupId>{g}</groupId>"
    s+=f"<artifactId>{a}</artifactId>"
    if v: s+=f"<version>{v}</version>"
    if pack: s+=f"<packaging>{pack}</packaging>"
    if props: s+="<properties>"+"".join(f"<{k}>{x}</{k}>" for k,x in props.items())+"</properties>"
    if mgmt: s+="<dependencyManagement><dependencies>"+"".join(mgmt)+"</dependencies></dependencyManagement>"
    if deps: s+="<dependencies>"+"".join(deps)+"</dependencies>"
    s+=profiles+extra+"</project>"
    return s
def install(g,a,v,xml):
    d=os.path.join(REPO,*g.split('.'),a,v); os.makedirs(d,exist_ok=True)
    open(os.path.join(d,f"{a}-{v}.pom"),"w").write(xml)
def lib(a,v="1.0",deps=(),mgmt=(),pack=None,g="org.synth",**k): install(g,a,v,pom(g,a,v,deps,mgmt,pack=pack,**k))
def project(name,xml,files=None):
    d=os.path.join(PROJ,name); os.makedirs(d,exist_ok=True); open(os.path.join(d,"pom.xml"),"w").write(xml)
    for fn,c in (files or {}).items():
        os.makedirs(os.path.dirname(os.path.join(d,fn)),exist_ok=True); open(os.path.join(d,fn),"w").write(c)
    return d
G="org.synth"; D=lambda a,v="1.0",**k: dep(G,a,(v or None),**k)
P=lambda name,deps=(),mgmt=(),**k: project(name,pom(G,name,"1.0",deps,mgmt,**k))
# leaves
for a in "abcdefgmnoprxyzt": lib("leaf-"+a)
lib("leaf-1"); lib("leaf-2"); lib("leaf-c","2.0"); lib("leaf-c","1.0")
# S1 parent inheritance
install(G,"parent-s1","1.0",pom(G,"parent-s1","1.0",deps=[D("lib-a","${lib.version}")],mgmt=[D("lib-b","3.0")],props={"lib.version":"2.0"},pack="pom"))
lib("lib-a","2.0",deps=[D("lib-b","1.0")]); lib("lib-b","1.0",deps=[D("leaf-a")]); lib("lib-b","3.0",deps=[D("leaf-b")])
project("s1-parent-from-cache",pom(None,"s1-parent-from-cache","1.0",deps=[D("lib-b",False)],parent=(G,"parent-s1","1.0")))
project("s1-parent-relpath",pom(None,"s1-parent-relpath","1.0",deps=[D("lib-b",False)],parent=(G,"parent-s1","1.0","../s1-local-parent/pom.xml")))
project("s1-local-parent",pom(G,"parent-s1","1.0",deps=[D("lib-a","${lib.version}")],mgmt=[D("lib-b","3.0")],props={"lib.version":"2.0"},pack="pom"))
# S2 BOMs
install(G,"bom-nested","1.0",pom(G,"bom-nested","1.0",mgmt=[D("lib-d","7.0")],pack="pom"))
install(G,"bom-s2","1.0",pom(G,"bom-s2","1.0",mgmt=[D("lib-a","5.0"),D("lib-c","1.5"),dep(G,"bom-nested","1.0",scope="import",typ="pom")],pack="pom"))
for v in ("5.0","2.0"): lib("lib-a",v,deps=[D("lib-b","1.0")])
lib("lib-c","1.5",deps=[D("leaf-c","2.0")]); lib("lib-d","7.0",deps=[D("leaf-d")]); lib("lib-d","1.0")
P("s2-bom",deps=[D("lib-a",False),D("lib-d",False),D("lib-c",False)],mgmt=[dep(G,"bom-s2","1.0",scope="import",typ="pom")])
P("s2-bom-vs-explicit",deps=[D("lib-a","2.0"),D("lib-c",False)],mgmt=[dep(G,"bom-s2","1.0",scope="import",typ="pom")])
# S3 dependencyManagement overrides
lib("lib-e","1.0",deps=[D("lib-b","1.0"),D("leaf-e")]); lib("lib-f","1.0",deps=[D("lib-b","1.0")]); lib("lib-b","9.0",deps=[D("leaf-z")])
P("s3-mgmt-transitive-version",deps=[D("lib-e")],mgmt=[D("lib-b","9.0")])
P("s3-mgmt-transitive-scope",deps=[D("lib-e")],mgmt=[D("leaf-e","1.0",scope="runtime")])
P("s3-mgmt-vs-direct-version",deps=[D("lib-b","1.0")],mgmt=[D("lib-b","9.0")])
# S4 transitives
lib("t1","1.0",deps=[D("t2"),D("t5")]); lib("t2","1.0",deps=[D("t3")]); lib("t3","1.0",deps=[D("t4")]); lib("t4","1.0"); lib("t5","1.0",deps=[D("t3")])
P("s4-transitives",deps=[D("t1")])
# S5 exclusions
lib("x1","1.0",deps=[D("leaf-1"),D("x2")]); lib("x2","1.0",deps=[D("leaf-2"),D("leaf-1")])
P("s5-exclusion-single",deps=[D("x1",excl=[(G,"leaf-1")])])
P("s5-exclusion-wildcard",deps=[D("x1",excl=[("*","*")])])
P("s5-exclusion-mid",deps=[D("x1",excl=[(G,"x2")])])
# S6 nearest wins
lib("n-a","1.0",deps=[D("leaf-c","1.0")]); lib("n-b","1.0",deps=[D("n-d")]); lib("n-d","1.0",deps=[D("leaf-c","2.0")])
P("s6-nearest-depth",deps=[D("n-a"),D("n-b")])
lib("n-a2","1.0",deps=[D("leaf-c","1.0")]); lib("n-b2","1.0",deps=[D("leaf-c","2.0")])
P("s6-tie-first-declared",deps=[D("n-a2"),D("n-b2")]); P("s6-tie-swapped",deps=[D("n-b2"),D("n-a2")])
# S7 scopes
lib("sc-a","1.0",deps=[D("sc-compile"),D("sc-runtime",scope="runtime"),D("sc-provided",scope="provided"),D("sc-test",scope="test")])
for n in ("sc-compile","sc-runtime","sc-provided","sc-test"): lib(n)
lib("sc-r","1.0",deps=[D("sc-compile2")]); lib("sc-p","1.0",deps=[D("sc-compile3")]); lib("sc-x","1.0",deps=[D("sc-compile4")]); lib("sc-compile2"); lib("sc-compile3"); lib("sc-compile4")
P("s7-scopes",deps=[D("sc-a"),D("sc-r",scope="runtime"),D("sc-p",scope="provided"),D("sc-x",scope="test")])
# S8 optional
lib("op-m","1.0",deps=[D("leaf-o",opt=True),D("leaf-m")]); lib("op-own","1.0",deps=[D("leaf-p")])
P("s8-optional",deps=[D("op-m"),D("op-own",opt=True)])
# S9 profiles
lib("pf-prop"); lib("pf-default"); lib("pf-jdk"); lib("pf-file"); lib("pf-os"); lib("pf-cli"); lib("pf-notjdk"); lib("pf-mgmt","1.0"); lib("pf-mgmt","2.0")
prof=lambda id,act,deps="",mgmt="": f"<profile><id>{id}</id><activation>{act}</activation>"+(f"<dependencies>{deps}</dependencies>" if deps else "")+(f"<dependencyManagement><dependencies>{mgmt}</dependencies></dependencyManagement>" if mgmt else "")+"</profile>"
profs="<profiles>"+prof("by-prop","<property><name>feature</name></property>",D("pf-prop"))+prof("by-default","<activeByDefault>true</activeByDefault>",D("pf-default"))+prof("by-jdk","<jdk>[17,)</jdk>",D("pf-jdk"))+prof("by-old-jdk","<jdk>[1.8,11)</jdk>",D("pf-notjdk"))+prof("by-file","<file><exists>${basedir}/flag.txt</exists></file>",D("pf-file"))+prof("by-os","<os><family>mac</family></os>",D("pf-os"))+prof("cli-only","<property><name>nope</name></property>",D("pf-cli"))+prof("mgmt","<property><name>usemgmt</name></property>","",D("pf-mgmt","2.0"))+"</profiles>"
project("s9-profiles",pom(G,"s9-profiles","1.0",deps=[D("pf-mgmt","1.0"),],profiles=profs),files={"flag.txt":"x"})
project("s9-profiles-nofile",pom(G,"s9-profiles-nofile","1.0",deps=[D("pf-mgmt","1.0")],profiles=profs))
# default-activation suppression: activeByDefault is off when another profile is active (covered by by-prop with -Dfeature)
# profile in parent
install(G,"parent-s9","1.0",pom(G,"parent-s9","1.0",pack="pom",profiles="<profiles>"+prof("p-parent","<property><name>feature</name></property>",D("pf-prop"))+"</profiles>"))
project("s9-parent-profile",pom(None,"s9-parent-profile","1.0",parent=(G,"parent-s9","1.0")))
# S10 missing offline
lib("ms-m","1.0",deps=[D("ms-gone"),D("leaf-a")])   # ms-gone absent
P("s10-missing-transitive-pom",deps=[D("ms-m")])
P("s10-missing-direct-pom",deps=[D("ms-direct-gone"),D("leaf-a")])
project("s10-missing-parent",pom(None,"s10-missing-parent","1.0",deps=[D("leaf-a")],parent=(G,"parent-gone","1.0")))
P("s10-missing-bom",deps=[D("lib-a")],mgmt=[dep(G,"bom-gone","1.0",scope="import",typ="pom")])
# POM present but jar absent (all our artifacts have no jars)
# S11 families
lib("fips-core","1.0",deps=[D("fips-util")]); lib("fips-util"); lib("nonfips-core","1.0",deps=[D("nonfips-util")]); lib("nonfips-util")
lib("framework","1.0",deps=[D("nonfips-core")]); lib("framework-safe","1.0",deps=[D("nonfips-core",opt=True)])
P("s11-families-both",deps=[D("fips-core"),D("framework")])
P("s11-families-excluded",deps=[D("fips-core"),D("framework",excl=[(G,"nonfips-core")])])
P("s11-families-optional",deps=[D("fips-core"),D("framework-safe")])
P("s11-families-test-scope",deps=[D("fips-core"),D("framework",scope="test")])
# extras: relocation, ranges, snapshot-like
install(G,"old-lib","1.0",pom(G,"old-lib","1.0",extra=f"<distributionManagement><relocation><groupId>{G}</groupId><artifactId>new-lib</artifactId><version>2.0</version></relocation></distributionManagement>"))
lib("new-lib","2.0",deps=[D("leaf-a")])
P("s12-relocation",deps=[D("old-lib")])
lib("rg","1.0"); lib("rg","1.5"); lib("rg2","1.0"); lib("rg2","1.5")
P("s13-range-no-metadata",deps=[D("rg2","[1.0,2.0)")])
P("s13-range-with-metadata",deps=[D("rg","[1.0,2.0)")])
md=os.path.join(REPO,"org","synth","rg","maven-metadata-central.xml")
open(md,"w").write('<metadata><groupId>org.synth</groupId><artifactId>rg</artifactId><versioning><versions><version>1.0</version><version>1.5</version></versions></versioning></metadata>')
# extension scenario (detection only; never executed by baseline)
P("s14-extensions-present",deps=[D("leaf-a")]); 
os.makedirs(os.path.join(PROJ,"s14-extensions-present",".mvn"),exist_ok=True)
open(os.path.join(PROJ,"s14-extensions-present",".mvn","extensions.xml"),"w").write('<extensions><extension><groupId>org.synth</groupId><artifactId>ext-gone</artifactId><version>1.0</version></extension></extensions>')
# project-declared repository (must be ignored)
project("s15-declared-repository",pom(G,"s15","1.0",deps=[D("leaf-a")],extra='<repositories><repository><id>evil</id><url>http://127.0.0.1:9/${env.HOME}</url></repository></repositories>'))
print(sorted(os.listdir(PROJ)))
