import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

import org.apache.maven.model.*;
import org.apache.maven.model.building.*;
import org.apache.maven.model.resolution.*;
import org.apache.maven.repository.internal.MavenRepositorySystemUtils;
import org.eclipse.aether.*;
import org.eclipse.aether.artifact.*;
import org.eclipse.aether.collection.*;
import org.eclipse.aether.graph.*;
import org.eclipse.aether.impl.DefaultServiceLocator;
import org.eclipse.aether.repository.*;
import org.eclipse.aether.spi.connector.RepositoryConnectorFactory;
import org.eclipse.aether.spi.connector.transport.TransporterFactory;
import org.eclipse.aether.connector.basic.BasicRepositoryConnectorFactory;
import org.eclipse.aether.transport.file.FileTransporterFactory;
import org.eclipse.aether.internal.impl.SimpleLocalRepositoryManagerFactory;

/** Research-only metadata resolver harness (NOT a production resolver). Offline by construction:
 *  no HTTP/Wagon transport is registered, the repository list is empty, project repositories are ignored. */
public class MetaResolve {
    static final List<String> events = new ArrayList<>();

    static class LocalModelResolver implements ModelResolver {
        final Path repo; final List<String> ignoredRepos;
        LocalModelResolver(Path repo, List<String> ignoredRepos) { this.repo = repo; this.ignoredRepos = ignoredRepos; }
        public ModelSource2 resolveModel(String g, String a, String v) throws UnresolvableModelException {
            Path p = repo.resolve(g.replace('.', '/')).resolve(a).resolve(v).resolve(a + "-" + v + ".pom");
            if (!Files.isRegularFile(p)) {
                events.add("MISSING-MODEL " + g + ":" + a + ":" + v);
                throw new UnresolvableModelException("not in offline cache: " + p, g, a, v);
            }
            events.add("POM-READ " + p.toAbsolutePath()); return new FileModelSource(p.toFile());
        }
        public ModelSource2 resolveModel(Parent parent) throws UnresolvableModelException { return resolveModel(parent.getGroupId(), parent.getArtifactId(), parent.getVersion()); }
        public ModelSource2 resolveModel(org.apache.maven.model.Dependency d) throws UnresolvableModelException { return resolveModel(d.getGroupId(), d.getArtifactId(), d.getVersion()); }
        public void addRepository(Repository r) { ignoredRepos.add(r.getId() + "=" + r.getUrl()); }
        public void addRepository(Repository r, boolean replace) { addRepository(r); }
        public ModelResolver newCopy() { return new LocalModelResolver(repo, ignoredRepos); }
    }

    static String ext(String type) { switch (type == null ? "jar" : type) { case "test-jar": case "ejb": case "bundle": case "maven-plugin": return "jar"; default: return type == null ? "jar" : type; } }
    static String cls(String type, String c) { return "test-jar".equals(type) ? "tests" : (c == null ? "" : c); }

    static org.eclipse.aether.graph.Dependency conv(org.apache.maven.model.Dependency d) {
        Artifact art = new DefaultArtifact(d.getGroupId(), d.getArtifactId(), cls(d.getType(), d.getClassifier()), ext(d.getType()), d.getVersion());
        List<org.eclipse.aether.graph.Exclusion> ex = new ArrayList<>();
        for (org.apache.maven.model.Exclusion e : d.getExclusions()) ex.add(new org.eclipse.aether.graph.Exclusion(e.getGroupId(), e.getArtifactId(), "*", "*"));
        String scope = d.getScope() == null || d.getScope().isEmpty() ? "compile" : d.getScope();
        return new org.eclipse.aether.graph.Dependency(art, scope, d.getOptional() != null && Boolean.parseBoolean(d.getOptional()), ex);
    }

    static void print(DependencyNode n, int depth, PrintStream out) {
        for (DependencyNode c : n.getChildren()) {
            org.eclipse.aether.graph.Dependency d = c.getDependency();
            Artifact a = d.getArtifact();
            out.println(depth + "\t" + a.getGroupId() + ":" + a.getArtifactId() + ":" + a.getExtension() + (a.getClassifier().isEmpty() ? "" : ":" + a.getClassifier()) + ":" + a.getBaseVersion() + "\t" + d.getScope() + "\t" + d.isOptional());
            print(c, depth + 1, out);
        }
    }

    public static void main(String[] args) throws Exception {
        Path pom = null, repo = null; Path out = null; boolean simple = false; boolean skipEmbeddedOptional = false;
        List<String> profiles = new ArrayList<>(); Properties user = new Properties();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--pom": pom = Paths.get(args[++i]); break;
                case "--repo": repo = Paths.get(args[++i]); break;
                case "--out": out = Paths.get(args[++i]); break;
                case "--profile": profiles.add(args[++i]); break;
                case "--simple-lrm": simple = true; break;
                default: if (args[i].startsWith("-D")) { String[] kv = args[i].substring(2).split("=", 2); user.setProperty(kv[0], kv.length > 1 ? kv[1] : "true"); } else throw new IllegalArgumentException(args[i]);
            }
        }
        List<String> ignoredRepos = new ArrayList<>();
        ModelBuilder mb = new DefaultModelBuilderFactory().newInstance();
        DefaultModelBuildingRequest req = new DefaultModelBuildingRequest();
        req.setPomFile(pom.toFile());
        req.setValidationLevel(ModelBuildingRequest.VALIDATION_LEVEL_MINIMAL);
        req.setProcessPlugins(false);
        req.setTwoPhaseBuilding(false);
        req.setSystemProperties(System.getProperties());
        req.setUserProperties(user);
        List<String> act=new ArrayList<>(), inact=new ArrayList<>(); for (String p0: profiles) { if (p0.startsWith("!")||p0.startsWith("-")) inact.add(p0.substring(1)); else act.add(p0);} req.setActiveProfileIds(act); req.setInactiveProfileIds(inact);
        req.setModelResolver(new LocalModelResolver(repo, ignoredRepos));
        ModelBuildingResult res;
        PrintStream ps = new PrintStream(Files.newOutputStream(out), false, "UTF-8");
        try { res = mb.build(req); } catch (ModelBuildingException e) { ps.println("#ERROR\tmodel\t" + e.getMessage().replace('\n', ' ')); ps.close(); return; }
        Model m = res.getEffectiveModel();

        DefaultServiceLocator locator = MavenRepositorySystemUtils.newServiceLocator();
        locator.addService(RepositoryConnectorFactory.class, BasicRepositoryConnectorFactory.class);
        locator.addService(TransporterFactory.class, FileTransporterFactory.class); // no http/wagon
        RepositorySystem system = locator.getService(RepositorySystem.class);
        DefaultRepositorySystemSession session = MavenRepositorySystemUtils.newSession();
        session.setOffline(true);
        LocalRepository lr = new LocalRepository(repo.toFile());
        session.setLocalRepositoryManager(simple ? new SimpleLocalRepositoryManagerFactory().newInstance(session, lr) : system.newLocalRepositoryManager(session, lr));
        session.setSystemProperties(System.getProperties()); session.setUserProperties(user);
        session.setRepositoryListener(new AbstractRepositoryListener() {
            @Override public void artifactDescriptorInvalid(RepositoryEvent e) { events.add("DESCRIPTOR-INVALID " + e.getArtifact() + " " + e.getException().getMessage().replace('\n', ' ')); }
            @Override public void artifactResolved(RepositoryEvent e) { if (e.getArtifact() != null && e.getArtifact().getFile() != null) events.add("POM-READ " + e.getArtifact().getFile().getAbsolutePath()); }
            @Override public void artifactDescriptorMissing(RepositoryEvent e) { events.add("DESCRIPTOR-MISSING " + e.getArtifact()); }
        });
        CollectRequest cr = new CollectRequest();
        cr.setRootArtifact(new DefaultArtifact(m.getGroupId() == null ? m.getParent().getGroupId() : m.getGroupId(), m.getArtifactId(), "jar", m.getVersion() == null ? m.getParent().getVersion() : m.getVersion()));
        for (org.apache.maven.model.Dependency d : m.getDependencies()) cr.addDependency(conv(d));
        if (m.getDependencyManagement() != null) for (org.apache.maven.model.Dependency d : m.getDependencyManagement().getDependencies()) cr.addManagedDependency(conv(d));
        CollectResult result;
        try { result = system.collectDependencies(session, cr); }
        catch (DependencyCollectionException e) { result = e.getResult(); events.add("COLLECT-EXCEPTION " + e.getMessage().replace('\n', ' ')); }
        if (result.getRoot() != null) print(result.getRoot(), 0, ps);
        for (Exception ex : result.getExceptions()) events.add("COLLECT-EXC " + ex.getClass().getSimpleName() + ": " + String.valueOf(ex.getMessage()).replace('\n', ' '));
        for (String r : ignoredRepos) events.add("IGNORED-PROJECT-REPOSITORY " + r);
        for (String e : new TreeSet<>(events)) ps.println("#EVENT\t" + e);
        ps.close();
    }
}
