# Interview Scripts

## 30-Second Explanation

### Version 1: Technical Focus

"I built ai-worker-team, which is production-inspired EvalOps infrastructure for detecting LLM quality regressions. The system runs structured evaluations, classifies failures into diagnostic categories like hallucination or incomplete answer, and surfaces those insights through a dashboard and automated nightly alerts. It's built on FastAPI with a task queue architecture using Redis and PostgreSQL, and includes an LLM-as-judge evaluator with structured verdict extraction. The key innovation is shifting from 'did we regress?' to 'where and why did we regress?' with taxonomy-aware comparison views."

**Use when:** Interviewer is technical, role is backend/infrastructure-focused

---

### Version 2: Product/Impact Focus

"I built an automated evaluation system for LLM-backed features. Teams shipping these features need to know if quality regressed, where it regressed, and how quickly they can detect it. My system automates the entire workflow: runs nightly evaluations, classifies failures into categories like hallucination or format error, compares runs to show diagnostic deltas, and sends alerts when quality drops. It's designed to shorten manual regression review cycles through automated checks. Built it from scratch using Python, FastAPI, and PostgreSQL with 99 passing tests."

**Use when:** Interviewer is non-technical, role emphasizes product thinking

---

### Version 3: Problem-Solution Structure

"The problem: teams shipping LLM features have scattered eval scripts but no unified workflow for regression detection. Manual review takes days. I built ai-worker-team to solve this—it's a portfolio-grade EvalOps system that automates evaluation execution, classifies failures into diagnostic categories, and sends automated alerts. The architecture uses a task queue pattern with task queue workers, and I designed it to be backward-compatible so legacy runs still work. Validated with 99 passing tests and nightly CI integration."

**Use when:** Need to demonstrate problem-solving approach

---

### Version 4: Learning-Oriented

"I built end-to-end EvalOps infrastructure to understand how LLM quality systems work. The project handles evaluation execution, diagnostic failure taxonomy, automated comparison, and webhook alerting. I learned a lot about task queue architectures, retry logic, structured output parsing from LLMs, and designing backward-compatible metrics. It's validated with 99 passing tests (39 integration + 60 unit) and deployed using Docker Compose with GitHub Actions automation."

**Use when:** Interviewer values learning/growth, junior/mid-level role

---

## 60-Second Explanation

### Version 1: Comprehensive Technical

"I built ai-worker-team, which is production-inspired EvalOps infrastructure for automated LLM regression detection.

The architecture uses a task queue pattern: FastAPI orchestrator receives evaluation tasks, pushes them to Redis, and task queue workers execute evaluations against configured datasets. Workers run both deterministic scorers and an LLM-as-judge evaluator that I built with structured JSON output parsing.

The key differentiator is the failure taxonomy system—instead of just showing 'exact match rate dropped 5%', it classifies failures into diagnostic categories like hallucination, incomplete answer, or format error, then surfaces those in comparison views. So you see 'hallucinations increased 20%, judge pass rate dropped 10%' which makes root cause analysis much faster.

I designed it to be backward-compatible, so older runs without taxonomy still render correctly while new runs expose the full diagnostic depth. It's deployed with Docker Compose, includes nightly regression automation via GitHub Actions, and has 99 passing tests (39 integration + 60 unit).

The whole system went from zero to working state in about 3 months, and I learned a ton about task queue systems, LLM integration patterns, and designing for operational resilience."

**Use when:** Interviewer is very technical, role is senior/staff level

---

### Version 2: Business Impact Focus

"I built an automated quality monitoring system for teams shipping LLM-backed features.

The problem it solves: teams have evaluation scripts everywhere but no unified workflow for detecting regressions, diagnosing root causes, and routing alerts. Manual review cycles take significant time, and when you find a regression, you still don't know if it's hallucinations, incomplete answers, or format errors.

My solution automates the entire workflow: nightly CI runs baseline evaluations, an LLM-as-judge evaluator classifies failures into diagnostic categories, comparison views show not just metric deltas but root causes, and webhook alerts notify teams with structured summaries.

The design goal: shift visibility from 'did we regress?' to 'where and why?', and enable teams to act on regressions faster because they have diagnostic context immediately.

Technically, it's a worker-based system built on FastAPI, Redis, and PostgreSQL with task queue architecture and configurable worker processes. I built it with high standards—99 passing tests, backward compatibility for legacy runs, Docker Compose setup, and GitHub Actions automation.

The project demonstrates both infrastructure engineering skills and deep understanding of LLM evaluation workflows."

**Use when:** Interviewer cares about impact/outcomes, role involves product thinking

---

### Version 3: Architecture Deep-Dive

"ai-worker-team is EvalOps infrastructure I built for automated LLM regression detection.

The architecture is a task queue system. Orchestrator layer is FastAPI with REST endpoints for task submission and a read-only dashboard for run inspection. Tasks get pushed to Redis queue, task queue workers poll and execute evaluations, results persist to PostgreSQL with sample-level granularity, and artifacts write to filesystem as JSON.

Workers run dual evaluators: deterministic scorers for baseline metrics like exact match, and an LLM-as-judge I built with structured output parsing. The judge returns JSON with passed/failed verdict, failure category, and reasoning. I normalize categories into a fixed taxonomy—hallucination, incomplete answer, format error, provider error, unknown—and aggregate at run level.

The comparison system is taxonomy-aware: it shows judge pass rate deltas, top failure category changes, and valid verdict rates. I designed it for backward compatibility—older runs without taxonomy still render, new runs expose full diagnostics, no data migration required.

Deployment is Docker Compose with configurable worker processes, GitHub Actions for nightly CI, and webhook integration for alerting. The stack supports queue-based execution, has retry logic with exponential backoff, and achieves stateless worker design for operational resilience.

Test validation is 99 passing tests (39 integration + 60 unit) covering taxonomy normalization, verdict logic, comparison behavior, and backward compatibility scenarios."

**Use when:** Interviewer is architect/principal level, role involves system design

---

### Version 4: Narrative Journey

"I wanted to understand how LLM quality systems work, so I built ai-worker-team from zero to working state.

Started with the evaluation execution layer: task queue architecture using FastAPI and Redis, task queue workers with retry logic, PostgreSQL for persistence. Got that working end-to-end with deterministic scorers.

Then added the LLM-as-judge evaluator with structured output parsing—that was interesting because I had to handle malformed JSON, extract verdicts reliably, and normalize failure categories. Built a taxonomy system with six canonical categories and normalization logic that maps variations to canonical forms.

Next came the diagnostic layer: instead of just showing metric deltas, surface root causes. Built taxonomy-aware comparison views that show judge pass rate changes and top failure category shifts. Made it backward-compatible so legacy runs still work—that required conditional rendering in templates and safe field extraction in the backend.

Finally added operational integration: nightly CI via GitHub Actions, webhook alerts with structured payloads, artifact persistence for debugging. Deployed with Docker Compose and wrote 99 tests (39 integration + 60 unit) to validate taxonomy logic, verdict calculation, and comparison behavior.

The whole journey taught me about task queue patterns, LLM integration challenges, backward-compatible design, and building infrastructure with operational patterns. Took about 3 months from conception to where it is now."

**Use when:** Interviewer values learning process, junior/mid role, portfolio review

---

## Question-Response Pairs

### Q: "What was the hardest technical challenge?"

**A:** "Backward-compatible metrics. I wanted to add failure taxonomy and verdict quality metrics without breaking older runs. The challenge was designing a data model where new fields are optional, template rendering checks for field presence before displaying, and comparison logic handles None values gracefully. I solved it with conditional extraction in the backend—`m.get('top_failure_category')` returns None for old runs—and conditional rendering in templates using Jinja2 checks. Validated with 18 backward compatibility tests covering old-vs-old, old-vs-new, and missing metrics scenarios."

---

### Q: "How did you ensure quality/reliability?"

**A:** "Three layers: unit tests for taxonomy normalization and verdict logic, integration tests for end-to-end workflows, and manual validation. Built up to 99 passing tests (39 integration + 60 unit) covering taxonomy classification, compare behavior, backward compatibility, and edge cases like empty categories or missing metrics. Also designed for operational resilience—retry logic with exponential backoff, non-fatal alerting so webhook failures don't break regression checks, and structured error handling at every layer."

---

### Q: "Why did you build this?"

**A:** "I wanted to understand ML evaluation infrastructure at a deeper level than just using existing tools. I'd seen teams struggle with regression detection—they'd have scattered eval scripts, manual review processes taking significant time, and no diagnostic visibility when things regressed. Built this to learn the architecture patterns for task queues, worker execution, LLM integration, and diagnostic classification. Turned into a portfolio piece demonstrating infrastructure engineering, testing discipline, and backward-compatible design."

---

### Q: "What would you do differently?"

**A:** "If rebuilding from scratch, I'd start with the taxonomy system earlier—I added it later which required careful backward compatibility design. I'd also invest more upfront in observability: metrics for queue depth, worker processing latency, LLM API latency distribution. Current design has health checks but not comprehensive operational metrics. For Docker setup, I'd add environment profiles (dev/staging/prod) and infrastructure-as-code configs rather than just Docker Compose. But the core architecture decisions—task queue pattern, backward-compatible metrics, read-only dashboard—I'd keep those the same."

---

### Q: "How does this compare to existing tools?"

**A:** "Existing tools like Weights & Biases or PromptLayer focus on experiment tracking and general observability. Mine is specifically EvalOps—operational regression detection with diagnostic taxonomy. The differentiator is taxonomy-aware comparison: instead of just 'EM rate dropped', you see 'hallucinations increased, judge pass rate fell, top failure shifted from X to Y'. It's also designed for CI integration first—nightly workflows, webhook alerts, automated baseline checks. Not as feature-rich as commercial tools but purpose-built for the regression detection workflow with full code transparency and solid architecture."

---

## Follow-Up Topics to Prepare

If interviewer asks deeper questions, be ready to discuss:

**Architecture:**
- Why task queue vs direct execution
- Worker-based architecture approach
- Redis vs alternative queue systems
- Read-only dashboard decision

**LLM Integration:**
- Structured output parsing approach
- Retry logic and fallback handling
- Cost considerations for LLM-as-judge
- Multi-provider strategy

**Data Model:**
- PostgreSQL schema design
- JSONB for flexible metrics
- Sample-level vs run-level storage
- Backward compatibility strategy

**Testing:**
- Test pyramid (unit vs integration)
- Backward compatibility validation
- Mock strategies for LLM calls
- CI/CD setup

**Deployment:**
- Docker Compose vs Kubernetes
- GitHub Actions workflow design
- Webhook security/validation
- Monitoring and alerting

---

## Tailoring Guide

**For Backend/Infrastructure roles:**
- Lead with architecture (task queue, worker-based execution)
- Emphasize worker patterns, retry logic, operational resilience
- Deep-dive on PostgreSQL, Redis, Docker

**For ML/AI roles:**
- Lead with LLM-as-judge evaluator
- Emphasize taxonomy classification, verdict extraction
- Deep-dive on structured output parsing, failure categories

**For Full-Stack roles:**
- Balance backend (API, workers) and frontend (dashboard)
- Emphasize end-to-end ownership
- Mention both technical depth and product thinking

**For Senior/Staff roles:**
- Lead with system design and architecture decisions
- Emphasize backward compatibility, operational concerns
- Deep-dive on trade-offs and alternative approaches

**For Startup/Generalist roles:**
- Lead with full ownership and breadth
- Emphasize shipping complete features independently
- Mention learning across full stack (backend, frontend, infra, CI)
