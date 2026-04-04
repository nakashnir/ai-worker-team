# CV / Resume Bullet Points

## Option 1: Technical Depth Focus

**Built production-inspired EvalOps infrastructure for LLM quality regression detection**
- Designed and implemented task queue architecture using FastAPI, Redis, and PostgreSQL handling structured evaluation jobs with persistent storage and CI integration
- Developed LLM-as-judge evaluator with failure taxonomy classification (hallucination, incomplete answer, format errors) validated by 99 passing tests (39 integration + 60 unit)
- Created taxonomy-aware comparison system with diagnostic delta visualization (judge pass rate, top failure categories) enabling root cause analysis of quality regressions
- Automated nightly regression detection via GitHub Actions with webhook alerting (Discord-compatible), designed to shorten manual review cycles through automated checks

## Option 2: Product/Impact Focus

**Shipped end-to-end EvalOps system for automated LLM regression detection**
- Built automated evaluation pipeline processing multi-provider LLM outputs (Anthropic, OpenAI) with deterministic scoring and LLM-as-judge assessment, surfacing quality signals through web dashboard
- Implemented diagnostic failure taxonomy with 6 canonical categories, enabling teams to identify root causes (hallucination vs incomplete answer vs format error) rather than just detect regressions
- Designed backward-compatible metric rendering system supporting legacy runs without taxonomy while enabling new diagnostic features, eliminating data migration requirements
- Integrated nightly CI workflows with webhook alerting, providing automated regression detection for baseline evaluation datasets with pass/fail verdict alignment

## Option 3: Infrastructure/Systems Focus

**Architected worker-based EvalOps infrastructure for LLM quality monitoring**
- Implemented task queue system with worker-based task queue execution, retry logic with exponential backoff, and structured error handling, achieving stateless execution and operational resilience
- Designed dual-evaluator architecture combining deterministic scorers (exact match, contains expected) with LLM-as-judge for hybrid verdict calculation, maintaining backward compatibility while enabling advanced diagnostics
- Built read-only dashboard with run inspection, sample-level drill-down, and run-to-run comparison views using server-side rendering (Jinja2) and RESTful API design
- Deployed Docker Compose stack with task queue workers, PostgreSQL persistence, Redis coordination, and GitHub Actions integration for scheduled regression workflows

## Option 4: Concise/Senior Focus

**Designed and shipped portfolio-grade EvalOps infrastructure for LLM regression detection**
- Built evaluation system (FastAPI, PostgreSQL, Redis) with LLM-as-judge, failure taxonomy classification, and automated nightly regression detection
- Implemented taxonomy-aware comparison views with diagnostic deltas, reducing time-to-root-cause from manual inspection to automated categorization
- Validated with 99 passing tests (39 integration + 60 unit) and backward-compatible architecture supporting legacy runs while enabling progressive feature rollout

## Option 5: Startup/Generalist Focus

**Built full-stack EvalOps platform from zero to working state**
- Architected and implemented complete evaluation infrastructure: FastAPI backend, PostgreSQL/Redis data layer, web dashboard UI, GitHub Actions automation, and webhook alerting
- Developed LLM integration layer with structured output parsing, retry logic, and multi-provider fallback (Anthropic, OpenAI)
- Created diagnostic taxonomy system categorizing LLM failures (hallucination, incomplete answer, format errors) with normalized classification and run-level aggregation
- Shipped nightly regression automation providing automated baseline checks with webhook alerts

---

## Bullet Point Components (Mix and Match)

### Technical Achievements
- "Designed task queue architecture using FastAPI, Redis, and PostgreSQL"
- "Implemented LLM-as-judge evaluator with structured JSON verdict extraction"
- "Built failure taxonomy with 6 canonical categories and normalization logic"
- "Validated with 99 passing tests (39 integration + 60 unit)"
- "Created backward-compatible metric rendering supporting legacy runs"

### Product Impact
- "Automated baseline evaluation with nightly CI integration"
- "Enabled root cause analysis of quality degradations"
- "Shifted visibility from metric deltas to diagnostic categories"
- "Shipped diagnostic dashboard with sample-level drill-down"

### Infrastructure/Scale
- "Worker-based task queue execution with coordination"
- "Retry logic with exponential backoff and structured error handling"
- "Multi-provider LLM integration with fallback handling"
- "Docker Compose setup with configurable worker processes"

### Domain Expertise
- "LLM quality evaluation and regression detection"
- "Failure taxonomy classification for diagnostic visibility"
- "Hybrid verdict calculation (deterministic + LLM-as-judge)"
- "EvalOps / Applied AI Infrastructure"

---

## Tailoring Guide

**For Machine Learning Engineer roles:**
- Lead with LLM-as-judge evaluator
- Emphasize taxonomy classification
- Highlight test coverage and validation

**For Backend/Infrastructure roles:**
- Lead with task queue architecture
- Emphasize worker patterns, retry logic, task queue execution
- Highlight Docker/CI integration

**For Full-Stack/Generalist roles:**
- Lead with end-to-end platform build
- Balance backend (API, workers) and frontend (dashboard)
- Emphasize complete ownership

**For Applied AI/ML Ops roles:**
- Lead with EvalOps positioning
- Emphasize regression detection workflow
- Highlight Docker setup and automation

---

## Usage Examples

**Traditional Resume:**
```
Software Engineer — Personal Project (2024-2025)
• Built production-inspired EvalOps infrastructure for LLM quality regression detection
• Designed task queue architecture using FastAPI, Redis, and PostgreSQL handling
  structured evaluation jobs with persistent storage and CI integration
• Developed LLM-as-judge evaluator with failure taxonomy classification validated
  by 99 passing tests (39 integration + 60 unit)
```

**LinkedIn Experience:**
```
Personal Project: ai-worker-team (2024-2025)
EvalOps Infrastructure for LLM Quality Monitoring

Shipped end-to-end evaluation platform with automated regression detection workflows.
Built worker-based task queue system, LLM-as-judge evaluator with diagnostic taxonomy,
and automated nightly CI workflows.
Tech: Python, FastAPI, PostgreSQL, Redis, Docker, GitHub Actions.
```

**Portfolio Summary:**
```
ai-worker-team
Production-inspired EvalOps infrastructure for automated LLM regression detection.
Handles evaluation execution, diagnostic failure taxonomy, and webhook alerting.

Key contributions:
• Distributed task queue architecture (FastAPI, Redis, PostgreSQL)
• LLM-as-judge with structured verdict extraction and taxonomy classification
• Taxonomy-aware comparison views with diagnostic deltas
• Nightly CI automation with Discord-compatible webhook alerts
```
