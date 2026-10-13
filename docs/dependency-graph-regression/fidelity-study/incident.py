import os,subprocess,sys,json
S=sys.argv[1]; JH=os.environ['JAVA_HOME']
ENV={'HOME':S+'/home','PATH':'/usr/bin:/bin','JAVA_HOME':JH}
vers=sys.argv[2:]
for v in vers:
    d=f'{S}/projects/inc-{v}'; os.makedirs(d,exist_ok=True)
    open(d+'/pom.xml','w').write(f'''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>inc</groupId><artifactId>inc-{v}</artifactId><version>1</version>
<dependencies>
<dependency><groupId>org.bouncycastle</groupId><artifactId>bc-fips</artifactId><version>1.0.2.4</version></dependency>
<dependency><groupId>org.bouncycastle</groupId><artifactId>bcpkix-fips</artifactId><version>1.0.7</version></dependency>
<dependency><groupId>org.springframework.cloud</groupId><artifactId>spring-cloud-starter-bootstrap</artifactId><version>{v}</version></dependency>
</dependencies></project>''')
    r=subprocess.run(['/opt/homebrew/bin/mvn','-B','-q','-s',S+'/empty-settings.xml','-gs',S+'/empty-settings.xml','-Dmaven.repo.local='+S+'/warm','org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree','-DoutputFile='+S+'/out/inc-'+v+'.warm.txt'],cwd=d,env=ENV,capture_output=True,text=True,timeout=300)
    print(v,r.returncode,(r.stdout+r.stderr).strip().splitlines()[-1][:150] if r.returncode else 'ok')
