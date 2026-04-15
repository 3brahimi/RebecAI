# Troubleshooting Guide

## Understanding the Difference: Counterexample vs. Syntax Error

This is the most common source of confusion.

### Counterexample (not a bug by default)

```
[RMC] Property violation found
Counterexample trace:
  State 0: s1.ship_length = 60, s1.masthead_light = 0
  Rule22 violated: !isLongVessel || hasRequiredLight = FALSE
```

**What this means:** The model has a reachable state where a vessel longer than 50m has no masthead light. The property correctly identifies this as unsafe.

**What to do:**
1. Read the full counterexample trace in the RMC output.
2. Determine: Is the unsafe state a legitimate flaw in the actor model, or did the translation introduce an incorrect abstraction?
3. If the model is wrong: fix the `.rebeca` file (add a guard, update message handler logic).
4. If the property is wrong: verify the Legata `assure` clause was encoded correctly.
5. Re-run WF-05.

### Syntax Error (always a translation bug)

```
[RMC] Parse error in model.rebeca:
  Line 14: unexpected token '->'
```

**What this means:** The `.rebeca` or `.property` file has a malformed construct. RMC cannot check anything until this is fixed.

**Common causes:**

| Error pattern | Likely cause |
|--------------|-------------|
| `unexpected token '->'` | Used implication operator `->` (forbidden in Rebeca property files) |
| `undefined variable` | Variable used in `define` section before it was declared, or typo in name |
| `unexpected '=>'` | Logical implication `=>` (forbidden; use `||` instead) |
| `missing semicolon` | Assertion line not terminated with `;` |
| `chained assignment` | `x = (y = condition)` is not allowed; define `y` separately |

**How to fix:**
See the [rebeca_handbook skill](skills/rebeca_handbook.md) for forbidden patterns and syntax reference.

---

## C++ Compilation Failure

```
[RMC] Generated C++ source files
Error: RMC generated C++ but compilation failed
Check /path/to/output/rmc_stderr.log for C++ compiler errors
```

**What this means:** RMC successfully parsed your `.rebeca` and `.property` files and generated C++ code, but the C++ compiler (g++ or clang) failed to compile the generated code.

**Common causes:**

| Error pattern | Likely cause | Fix |
|--------------|--------------|-----|
| `g++: command not found` | C++ compiler not installed | Install: `sudo apt install g++` (Linux) or `xcode-select --install` (macOS) |
| `fatal error: iostream: No such file` | C++ standard library missing | Install build-essential: `sudo apt install build-essential` |
| `undefined reference to 'pthread_create'` | Missing pthread library | Add `-lpthread` to RMC compilation flags |
| `error: 'std::vector' has not been declared` | C++ standard version mismatch | Ensure g++ supports C++11: `g++ --version` |

**How to diagnose:**

1. Check if C++ compiler is installed:
   ```bash
   g++ --version
   # or
   clang++ --version
   ```

2. Try compiling the generated C++ manually:
   ```bash
   cd /path/to/rmc/output
   g++ -o model.out *.cpp -std=c++11 -lpthread
   ```

3. If manual compilation fails, the issue is with your C++ toolchain, not RMC.

4. If manual compilation succeeds, RMC may need additional compiler flags. Check `configs/rmc_defaults.json`.

**How to fix:**

**On Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install build-essential g++ make
```

**On macOS:**
```bash
xcode-select --install
```

**On Fedora/RHEL:**
```bash
sudo dnf install gcc-c++ make
```

---

## Parse Error vs. Compilation Error

**How to distinguish:**

| Symptom | Diagnosis | Action |
|---------|-----------|--------|
| No `.cpp` files in output directory | **Parse error** - Rebeca syntax invalid | Fix `.rebeca` or `.property` syntax |
| `.cpp` files exist but no executable | **Compilation error** - C++ toolchain issue | Install/fix C++ compiler |
| Executable exists but verification fails | **Model checking error** - Property violation or timeout | Inspect counterexample or increase timeout |

**Check the output directory:**
```bash
ls -la /path/to/rmc/output/
```

- If you see `*.cpp` and `*.h` files but no executable → **compilation error**
- If you see no files at all → **parse error**
- If you see an executable (`.out`, `a.out`, `model`) → **verification ran** (check logs for results)

---

## Functional Test Failures

### Running functional tests

```bash
bash rebecai/tests/run_functional_tests.sh
```

### Test categories

| Test prefix | What it checks |
|------------|---------------|
| `SYNTAX-*` | `.rebeca` and `.property` files parse correctly |
| `SCORING-*` | Scoring outputs match contract field names and ranges |
| `TRIAGE-*` | Classifier returns correct statuses for known inputs |
| `FALLBACK-*` | Fallback mapper generates valid provisional properties |
| `REPORT-*` | Aggregate report contains required contract fields |

### Common functional test failures

**SYNTAX-001 fails:** Sample `.rebeca` file has invalid syntax.
- Open the file, look for `->`, `=>`, or chained assignments.
- Run: `java -jar .agents/rmc/rmc.jar --check-syntax model.rebeca`

**SCORING-001 fails:** score_total out of [0, 100] range.
- The scoring script returned a value outside the contract range.
- Likely cause: verify_status value not in `[pass, fail, timeout, blocked, unknown]`.

**TRIAGE-001 fails:** Status classifier returns unexpected value.
- Check the Legata file being tested — it may have unexpected formatting.
- Ensure the file contains standard `condition`, `exclude`, `assure` section keywords.

---

## Platform Support

All platforms are now supported with cross-platform Python tooling:

**Windows:** Use native Python with MinGW/g++, or WSL2 (recommended)
```bash
# Inside WSL2 Ubuntu shell:
sudo apt-get install -y build-essential openjdk-17-jre python3
# Then follow the Linux installation steps in guides/installation.md
```

**macOS:** Native support with Xcode Command Line Tools
```bash
xcode-select --install
brew install openjdk python3
```

**Linux:** Native support with build-essential
```bash
sudo apt install build-essential openjdk-17-jre python3
```

See [Installation Guide](guides/installation.md) for complete setup instructions.

---

## RMC Issues

### RMC Phase 2: C++ compilation failed

```
Error: Phase 2 failed — C++ compilation error
Detail: model.cpp:42: error: 'undeclaredVar' was not declared
```

**What this means:** RMC successfully parsed the `.rebeca` and `.property` files (Phase 1 OK — `.cpp` files exist in output dir), but the generated C++ code failed to compile. This is distinct from a parse/syntax error.

**Common causes:**

| Symptom | Likely cause |
|---------|-------------|
| `'g++' not found` or `command not found` | C++ compiler not installed |
| `error: 'X' was not declared` | Variable referenced in property not defined in `.rebeca` actor state |
| `error: use of undeclared identifier` | Actor name in property doesn't match actor name in `.rebeca` |
| `error: no member named 'X' in 'Y'` | State variable name in property doesn't match field in `.rebeca` `statevars` block |

**Fix steps:**
1. Install `g++` if missing:
   - macOS: `xcode-select --install`
   - Linux: `sudo apt-get install build-essential`
2. Verify actor and state variable names match exactly between `.rebeca` and `.property`:
   ```rebeca
   // .rebeca: actor named "vessel1" with field "mastheadLight"
   reactiveclass vessel1(10) { statevars { boolean mastheadLight; } ... }
   // .property: must use exact same names
   Assertion { Rule22: !vessel1.isUnderway || vessel1.mastheadLight; }
   ```
3. Check output dir for `.cpp` files — open them to see what variable names RMC generated.

### RMC jar not found

```
[RMC Hook] rmc.jar not found or invalid, downloading...
[RMC Hook] ERROR: Failed to download rmc.jar
```

**Fix:**
```bash
python3 ~/.agents/skills/rebeca_tooling/scripts/download_rmc.py \
  --url https://github.com/rebeca-lang/org.rebecalang.rmc/releases/latest \
  --dest-dir .agents/rmc
```

If the download fails (network issue), try manual download or check network connectivity.

### RMC timeout

```
[RMC] Verification timed out after 120 seconds
```

**Fix:** Increase timeout when running RMC:
```bash
python3 ~/.agents/skills/rebeca_tooling/scripts/run_rmc.py \
  --jar ~/.agents/rmc/rmc.jar \
  --model model.rebeca \
  --property property.property \
  --output-dir output \
  --timeout-seconds 300
```

Or simplify the actor model to reduce state space.

### Java OutOfMemoryError

**Fix:** Increase Java heap size when running RMC:
```bash
export JAVA_OPTS="-Xmx4g"
python3 ~/.agents/skills/rebeca_tooling/scripts/run_rmc.py ...
```

---

## Triage Issues

### Classifier always returns `not-formalized`

The Legata file exists but has no `condition`, `exclude`, or `assure` keywords.

Check: Is the Legata file using a non-standard keyword convention?
The classifier looks for exact keywords: `condition`, `exclude`/`exclusion`, `assure`/`assurance`.

### Fallback mapper returns `confidence: low`

The COLREG source text has insufficient keywords for the mapper to extract vessel/equipment context.

Provide more specific text, e.g., include terms like `vessel`, `light`, `visibility`, `shall not`.

---

## Install Issues

### install_artifacts reports missing source

```
⚠ Agent source not found: /path/to/rebecai/agents/legata_to_rebeca.md
```

**Fix:** Ensure the script is being run from the project root directory, not from inside `rebecai/`.

```bash
# Correct:
cd /path/to/RebecAI
python3 skills/rebeca_tooling/scripts/install_artifacts.py --target-root ~/.agents --mode all

# Wrong:
cd rebecai/skills && python3 rebeca_tooling/scripts/install_artifacts.py ...
```
