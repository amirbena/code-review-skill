# Fidelity-study artifacts

Research-only scripts and results behind
[`../fidelity-study.md`](../fidelity-study.md) (#723). **Not a production
resolver, not packaged, not maintained.** They are kept so the study can be
re-run and audited.

| File | Purpose |
| --- | --- |
| `MetaResolve.java` | The candidate harness: Maven's model builder and Resolver as a library, file transport only, empty repository list, project repositories ignored. |
| `gen.py` | Generates the hermetic synthetic POM repository and scenario projects. |
| `run.py` | Runs real Maven (`dependency:tree`, offline, network-denied sandbox) and the harness on each scenario and compares the trees. |
| `incident.py` | Resolves the public Spring Cloud / BouncyCastle chain online into an isolated cache. |
| `sec1.py`, `sec2.py` | Security and resource checks (declared-repository exfiltration, credential decoys, read-only cache, pathological POMs). |
| `results-summary.json` | Results of the runs reported in the study. |

Requirements: Maven 3.9.16, a JDK 17, macOS `sandbox-exec`, and `JAVA_HOME`.
The classpath is the Maven distribution's own `lib/*.jar` minus the HTTP and
Wagon transports. Scripts take a scratch directory as their first argument and
use an isolated local repository, an empty `HOME`, and empty settings; they
never touch `~/.m2`.
