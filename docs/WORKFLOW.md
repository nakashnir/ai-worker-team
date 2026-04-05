# Repository Workflow

## Overview

This document describes the development workflow used in `ai-worker-team`, covering how changes move from planning to code to verification, and how the repository is structured for both versioned source control and runtime verification.

---

## Two-Tree Model

The project maintains two separate directory trees:

### 1. Repository Tree (Source of Truth)
**Location:** `/home/administrator/ai-worker-team-repo`

- **Purpose:** Versioned source of truth for all code and documentation
- **Git Status:** Tracked by Git, commits pushed to GitHub
- **Usage:** All development work happens here first
- **Sync Direction:** Changes flow FROM repo TO live

### 2. Live Tree (Runtime Verification)
**Location:** `/home/administrator/ai-worker-team`

- **Purpose:** Runtime environment for testing and verification
- **Git Status:** Not tracked (may be a Git clone but treated as disposable)
- **Usage:** Verify changes work in actual runtime environment
- **Sync Direction:** Receives changes FROM repo via mirror/copy

**Key Principle:** Repository is the source of truth. Live tree is for verification only. Changes are made in repo, then synced to live for testing.

---

## Development Stages

### Stage 1: Builder

**Role:** Claude (or human developer) implementing features/fixes

**Activities:**
- Write code in repository tree
- Implement features, bug fixes, or improvements
- Update tests as needed
- Create draft documentation

**Output:** Code changes ready for QA review

**Location:** `/home/administrator/ai-worker-team-repo`

---

### Stage 2: QA Gate

**Role:** Human reviewer or QA process

**Activities:**
- Review code changes in repository
- Check for logic errors, edge cases, regressions
- Verify test coverage
- Validate documentation accuracy
- Run targeted tests if needed

**Decision Points:**
- ✅ **PASS:** Proceed to Codex stage
- ❌ **REJECT:** Return to Builder with specific feedback

**Output:** QA-approved changes ready for integration

---

### Stage 3: Verification

**Role:** Runtime validation in live environment

**Activities:**
1. **Sync to Live:** Mirror changes from repo to live tree
   ```bash
   rsync -av --delete /home/administrator/ai-worker-team-repo/ /home/administrator/ai-worker-team/
   ```

2. **Runtime Verification:**
   - Run full test suite: `pytest tests/`
   - Test integration workflows
   - Verify Docker Compose stack: `docker-compose up`
   - Check nightly workflow execution
   - Validate dashboard rendering

3. **Validation:**
   - All tests pass
   - No runtime errors
   - Features work as documented

**Decision Points:**
- ✅ **PASS:** Changes verified, proceed to Codex stage
- ❌ **FAIL:** Return to Builder, fix issues in repo

**Output:** Verified working code ready for commit

---

### Stage 4: Codex

**Role:** Final integration and commit after verification

**Activities:**
- Review complete verified changeset
- Ensure all files are consistent
- Verify commit message accuracy
- Execute Git commit and push

**Decision Points:**
- Confirm verification passed
- Check commit message follows conventions
- Verify no unintended changes

**Output:** Committed and pushed to GitHub

---

## Commit Discipline

### Commit Timing

**The actual workflow: Verify BEFORE committing**

```bash
# 1. Make changes in repository
cd /home/administrator/ai-worker-team-repo
# ... develop features, write tests ...

# 2. Sync to live for verification
rsync -av --delete /home/administrator/ai-worker-team-repo/ /home/administrator/ai-worker-team/

# 3. Verify in live tree
cd /home/administrator/ai-worker-team
pytest tests/
docker-compose up  # verify runtime behavior

# 4. ONLY AFTER verification passes, commit in repo
cd /home/administrator/ai-worker-team-repo
git add <files>
git commit -m "descriptive message"
git push origin main
```

### Why This Order?

1. **Verification before commitment** - Don't commit broken code
2. **Live tree catches runtime issues** - Integration problems surface before Git history
3. **Clean Git history** - Only working, verified code gets committed
4. **Confidence in commits** - Every commit has been runtime-verified

### Commit Messages

Follow conventional format:
- `feat: Add failure taxonomy classification`
- `fix: Handle empty verdict lists in compare`
- `docs: Update ARCHITECTURE.md with taxonomy design`
- `test: Add backward compatibility integration tests`

---

## When to Use Claude vs Codex

### Use Claude For:

**Development and Iteration:**
- Writing new features
- Debugging code
- Iterating on implementation
- Drafting documentation
- Exploring solutions
- Prototyping changes

**Characteristics:**
- Builder stage work
- Needs reasoning and problem-solving
- Multiple iterations expected
- Draft/work-in-progress acceptable

---

### Use Codex For:

**Final Integration (After Verification):**
- Reviewing complete changesets that have been verified
- Preparing commits for verified code
- Final documentation polish
- Ensuring consistency across files
- Git operations (commit, push)

**Characteristics:**
- Codex stage work happens AFTER verification passes
- Final review and integration of verified code
- Clean, production-ready state
- Ready for Git history

---

## Sync Pattern: Build, Verify, Then Commit

### Standard Workflow

```
1. BUILDER (Claude)
   ↓
   Work in: /home/administrator/ai-worker-team-repo
   Create/modify files
   ↓
2. QA GATE
   ↓
   Review in: /home/administrator/ai-worker-team-repo
   Verify correctness
   ↓
3. SYNC TO LIVE
   ↓
   rsync repo → live
   ↓
4. VERIFICATION
   ↓
   Test in: /home/administrator/ai-worker-team
   pytest tests/
   docker-compose up
   ↓
   ✅ Tests pass? → Continue
   ❌ Tests fail? → Back to Builder
   ↓
5. CODEX (after verification)
   ↓
   Commit in: /home/administrator/ai-worker-team-repo
   git commit && git push
   ↓
6. DONE ✅
```

### Why Verify-Then-Commit?

**Confidence:**
- Only verified working code enters Git history
- Every commit has been runtime-tested
- No "fix broken commit" commits needed

**Clean History:**
- Git log shows only working states
- Easy to bisect when debugging
- Each commit is a known-good state

**Integration Testing:**
- Live tree catches environment-specific issues
- Docker Compose integration verified
- Full pytest suite validates changes

**Development Safety:**
- Can iterate in repo without polluting Git
- Failed experiments don't enter history
- Commit represents "this definitely works"

---

## Example Workflow Execution

### Sprint 3A: Backward Compatibility

**Builder Stage:**
```bash
cd /home/administrator/ai-worker-team-repo
# Claude implements backward compatibility logic
# Updates compare.html template with conditional rendering
# Adds tests for legacy run handling
```

**QA Gate:**
```
Review changes:
- ✓ Conditional rendering correct
- ✓ Safe field extraction with .get()
- ✓ Tests cover legacy scenarios
→ APPROVED for verification
```

**Sync to Live:**
```bash
rsync -av --delete /home/administrator/ai-worker-team-repo/ /home/administrator/ai-worker-team/
```

**Verification Stage:**
```bash
cd /home/administrator/ai-worker-team
pytest tests/integration/test_compare_backward_compat.py
# All tests pass ✅

docker-compose up -d
# Visit dashboard, verify legacy runs render correctly ✅
```

**Codex Stage (after verification passes):**
```bash
cd /home/administrator/ai-worker-team-repo
git add orchestrator/templates/compare.html
git add tests/integration/test_compare_backward_compat.py
git commit -m "feat: Add backward-compatible metric rendering for legacy runs"
git push origin main
```

**Result:** Sprint 3A complete, changes verified in live then committed to repo.

---

## Directory Structure Reference

```
/home/administrator/
├── ai-worker-team-repo/          # Repository (source of truth)
│   ├── .git/                     # Git repository
│   ├── evals/                    # Evaluator implementations
│   ├── orchestrator/             # FastAPI orchestrator
│   ├── workers/                  # Worker processes
│   ├── tests/                    # Test suite
│   │   ├── unit/                 # Unit tests
│   │   └── integration/          # Integration tests
│   ├── docs/                     # Documentation
│   │   ├── ARCHITECTURE.md
│   │   ├── WORKFLOW.md           # This file
│   │   └── runbooks/
│   └── docker-compose.yml
│
└── ai-worker-team/               # Live tree (runtime verification)
    ├── evals/                    # Synced from repo
    ├── orchestrator/             # Synced from repo
    ├── workers/                  # Synced from repo
    ├── tests/                    # Synced from repo
    └── docker-compose.yml        # Synced from repo
```

---

## Common Operations

### Starting New Work

```bash
cd /home/administrator/ai-worker-team-repo
git pull origin main
# Start development
```

### Syncing Repo to Live (for Verification)

```bash
rsync -av --delete /home/administrator/ai-worker-team-repo/ /home/administrator/ai-worker-team/
```

### Running Tests in Live

```bash
cd /home/administrator/ai-worker-team
pytest tests/
```

### Committing Changes (After Verification)

```bash
# First verify in live tree, then:
cd /home/administrator/ai-worker-team-repo
git add <files>
git commit -m "type: description"
git push origin main
```

---

## Troubleshooting

### Live Tree Out of Sync

**Problem:** Live tree has stale code  
**Solution:** Re-sync from repo
```bash
rsync -av --delete /home/administrator/ai-worker-team-repo/ /home/administrator/ai-worker-team/
```

### Changes Made in Live by Mistake

**Problem:** Edited files in live tree instead of repo  
**Solution:** Discard live changes, work in repo
```bash
# Option 1: Re-sync from repo (discards live changes)
rsync -av --delete /home/administrator/ai-worker-team-repo/ /home/administrator/ai-worker-team/

# Option 2: Manually port changes to repo, then re-sync
# Copy specific fixes to repo, commit, then re-sync
```

### Tests Pass in Repo but Fail in Live

**Problem:** Environmental differences  
**Solution:** Check for:
- Different Python dependencies
- Missing environment variables
- Stale Docker containers
- Database state differences

```bash
cd /home/administrator/ai-worker-team
docker-compose down
docker-compose up --build
pytest tests/
```

---

## Best Practices

1. **Always work in repo** - Never edit code directly in live tree
2. **Verify before commit** - Always test changes in live environment before committing
3. **Sync to live for testing** - Use rsync to mirror repo → live for verification
4. **Clean commits** - Each commit should be a verified, working change
5. **Use rsync carefully** - `--delete` flag removes files not in source (repo)
6. **Test in live before push** - Run full test suite in live tree before Git push
7. **Document as you go** - Update docs in same commit as code changes

---

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) - System design and technical details
- [README.md](../README.md) - Project overview and quick start
- [runbooks/](runbooks/) - Operational procedures
