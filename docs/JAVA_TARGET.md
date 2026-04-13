# Java Reimplementation Target

Masquerade has parallel reimplementation tracks: Python (the original) and **Java** (added in the Java track workstreams W0-W8). This document covers the Java side end-to-end: prerequisites, bootstrap, generation, the runner protocol, and how to add a new Java reimplementation.

The locked PRD decision (`PRD/locked-decisions.md`) puts Java as the *default* generated target — it earns better acceptance in regulated enterprise modernization than Python. The Python track stays as the reference implementation for cross-language correctness checking.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| **JDK** | 17 LTS | Eclipse Temurin recommended. Java 17 is the version every generated `pom.xml` targets. |
| **Maven** | 3.9.x | Apache Maven (`mvn`). Not the same as Gradle. |

Install on Windows:

```bash
# JDK 17 via winget (admin elevation handled automatically by the installer)
winget install --id EclipseAdoptium.Temurin.17.JDK --silent

# Maven — NOT in winget, manual install
curl -sSLo maven.zip https://dlcdn.apache.org/maven/maven-3/3.9.14/binaries/apache-maven-3.9.14-bin.zip
unzip maven.zip -d "$HOME/tools/"
```

The bash session Claude Code spawns doesn't pick up new PATH entries automatically. Set the environment per command:

```bash
export JAVA_HOME="/c/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot"
export PATH="$HOME/tools/apache-maven-3.9.14/bin:$JAVA_HOME/bin:$PATH"
java -version   # → openjdk 17.0.18 ...
mvn -version    # → Apache Maven 3.9.14 ...
```

---

## Bootstrap (one-time per machine)

The Java track depends on a `cobol-decimal` artifact (the Java port of `pipeline/cobol_decimal.py`) that must be installed in your local Maven repo. Every generated module declares `com.modernization.masquerade:cobol-decimal:0.1.0-SNAPSHOT` as a dependency.

```bash
cd pipeline/reimpl/java/cobol-decimal
mvn install
```

This compiles `CobolDecimal.java`, runs the 49-test JUnit 5 parity suite (which mirrors `pipeline/tests/test_cobol_decimal.py` test-for-test), and installs the artifact to `~/.m2/repository/com/modernization/masquerade/cobol-decimal/`.

After this is done once, every generated Java module can resolve the dependency without further setup.

---

## Generating Java Modules

Use `pipeline/java_codegen.py` to generate Java skeletons from a parsed COBOL codebase.

```bash
# Prerequisite: codebase must already be parsed
python pipeline/analyze.py test-codebases/carddemo

# Generate Java for one program
python pipeline/java_codegen.py \
    --codebase test-codebases/carddemo \
    --program COSGN00C \
    --output out/java \
    --codebase-name carddemo

# Generate Java for every program in the codebase
python pipeline/java_codegen.py \
    --codebase test-codebases/carddemo \
    --output out/java \
    --codebase-name carddemo
```

The output for each program looks like:

```
out/java/cosgn00c/
  pom.xml                                # depends on cobol-decimal
  src/main/java/com/modernization/carddemo/cosgn00c/
    Main.java                            # paragraphs as Java methods, run() entry point
    dto/SecUserData.java                 # one DTO per copybook (empty class shells today — see R4)
    service/CobdatftService.java         # one stub per external CALLed program
    controller/Cosgn00cController.java   # only for CICS Online programs
```

To verify a generated module compiles:

```bash
cd out/java/cosgn00c
mvn -q compile
```

---

## The Java Runner Protocol

The differential harness can drive Java reimplementations through a JSON I/O contract — the same one Python reimplementations use. This is what makes parity verification possible.

### Architecture

```
DiffVector (Python)
       |
       v
populate_actuals(vectors, JavaRunner())   ← pipeline/vector_runner.py
       |
       v
java -jar masquerade-runner.jar           ← stdin: JSON request
       |                                    stdout: JSON response
       v
RunnerMain.java                            ← reads JSON, dispatches
       |
       v
ProgramRegistry.get("COSGN00C")            ← static map
       |
       v
new Cosgn00c().runVector(inputs)           ← business logic
       |
       v
{"vector_id": ..., "outputs": {...}, "errors": []}
       |
       v (back to Python)
DiffVector.actual_outputs populated
       |
       v
run_vectors(vectors) → DiffReport
```

### Wire format

Request (Python → Java, on stdin):
```json
{
  "program": "COSGN00C",
  "vector_id": "ADMIN_LOGIN",
  "inputs": {
    "USERID": "ADMIN001",
    "PASSWD": "PASS1234"
  }
}
```

Response (Java → Python, on stdout):
```json
{
  "vector_id": "ADMIN_LOGIN",
  "outputs": {
    "XCTL_TARGET": "COADM01C",
    "HAS_COMMAREA": "Y",
    "ERROR_MSG": ""
  },
  "errors": []
}
```

### Building the runner JAR

```bash
cd pipeline/reimpl/java/runner
mvn package
```

Produces `target/masquerade-runner.jar` — a fat jar including `cobol-decimal`, Jackson, and every registered program. The Python `JavaRunner` looks for it at this exact path by default; pass `--jar` to `vector_runner.py` to override.

### Manual smoke test

```bash
echo '{"program":"COSGN00C","vector_id":"V001","inputs":{"USERID":"ADMIN001","PASSWD":"PASS1234"}}' \
    | java -jar pipeline/reimpl/java/runner/target/masquerade-runner.jar
# → {"vector_id":"V001","outputs":{"XCTL_TARGET":"COADM01C","HAS_COMMAREA":"Y","ERROR_MSG":""},"errors":[]}
```

### Driving via Python

```bash
python pipeline/vector_runner.py \
    --program COSGN00C \
    --vectors path/to/vectors_dir \
    --runner java
```

---

## Adding a New Java Reimplementation

Steps to add `MYPROG` as a Java reimplementation:

1. **Generate the skeleton:**
   ```bash
   python pipeline/java_codegen.py --codebase test-codebases/carddemo --program MYPROG --output out/java --codebase-name carddemo
   ```

2. **Hand-port the business logic** into `pipeline/reimpl/java/runner/src/main/java/com/modernization/masquerade/runner/programs/Myprog.java`. Use the existing `Cosgn00c.java` as a template — implement `ProgramRunner`, expose `runVector(Map<String,String> inputs)`, return a string-keyed output map.

3. **Register it:** add one line to `ProgramRegistry.java`:
   ```java
   REGISTRY.put("MYPROG", new Myprog());
   ```

4. **Rebuild the runner JAR:**
   ```bash
   cd pipeline/reimpl/java/runner && mvn package
   ```

5. **Add a Python test** under `pipeline/tests/` (mirror `test_java_runner_pilot.py`) that runs the program through the differential harness with `JavaRunner` and asserts 100% confidence against expected outputs.

6. **Run it:**
   ```bash
   python -m pytest pipeline/tests/test_java_runner_pilot.py -v
   ```

---

## Differences from the Python Track

| Aspect | Python | Java |
|---|---|---|
| Numeric semantics | `cobol_decimal.py` | `CobolDecimal.java` (49-test parity suite) |
| Reimpl location | `pipeline/reimpl/<program>.py` | `pipeline/reimpl/java/runner/src/main/java/.../programs/<Program>.java` |
| Runner | In-process import via `PythonRunner` | JVM subprocess via `JavaRunner` |
| Cold start | <10ms | ~700ms per JVM (per-vector cost is real) |
| Service stubs | Plain Python classes | Spring Boot 3 (CICS programs only) |
| Repository pattern | Plain Python classes | `extends CrudRepository<T, K>` (Spring Data) |
| API contracts | Pydantic + FastAPI | JSR-380 DTOs + Spring `@RestController` |
| Test harness | pytest | JUnit 5 |
| Build manifest | None (just .py files) | `pom.xml` per program + cobol-decimal install |
| Dependency footprint | None | JDK 17 + Maven 3.9.x + ~50 MB Spring (CICS only) |

---

## Troubleshooting

**`Could not find artifact com.modernization.masquerade:cobol-decimal:jar:0.1.0-SNAPSHOT`**
You haven't run the Bootstrap step. `cd pipeline/reimpl/java/cobol-decimal && mvn install`.

**`java: command not found` from a bash session**
Set the env vars inline:
```bash
export JAVA_HOME="/c/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot"
export PATH="$JAVA_HOME/bin:$PATH"
```
Bash sessions don't inherit Windows PATH updates from the installer until you start a new shell.

**JavaRunner: runner JAR not found at `pipeline/reimpl/java/runner/target/masquerade-runner.jar`**
You haven't built the runner. `cd pipeline/reimpl/java/runner && mvn package`. Or pass `--jar /path/to/your.jar` to `vector_runner.py`.

**`mvn -q test` produces no output but exits 0**
Maven's quiet flag suppresses success output. That's a passing test run. Drop `-q` to see the test report.

**Tests skipped with reason "Java runner JAR not built"**
The `test_java_runner_pilot.py` tests skip cleanly if the JAR doesn't exist, so the test suite stays green on machines without the Java toolchain configured. Build the JAR to enable them.

---

## See Also

- `PRD/java-target-parallel.md` — strategic PRD for the Java track
- `PRD/java-track-review-points.md` — running list of decisions and deferrals to revisit
- `PRD/locked-decisions.md` — original strategic locks (Java as default target)
- `pipeline/vector_runner.py` — the JSON contract Python and Java both speak
- `pipeline/reimpl/java/cobol-decimal/` — the foundation: `BigDecimal`-backed COBOL arithmetic
- `pipeline/reimpl/java/runner/` — the dispatcher fat jar + per-program reimplementations
