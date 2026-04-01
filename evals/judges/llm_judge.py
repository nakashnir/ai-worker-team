"""
evals/judges/llm_judge.py
LLM-as-a-Judge evaluator using existing provider infrastructure.
"""

from __future__ import annotations

import json
from typing import Any

from providers import resolve_provider
from providers.anthropic import AnthropicProvider, ProviderFatalError

from ..base import Evaluator
from ..schemas import EvalInput, EvalResult, RubricCriterion, RubricScore


# ─────────────────────────────────────────────────────────────────
# Default rubric when none is provided
# ─────────────────────────────────────────────────────────────────

DEFAULT_RUBRIC = [
    RubricCriterion(
        key="answered_user_request",
        label="Answered User Request",
        description="Did the model properly address the user's question or request?",
        weight=2.0,
        required=True,
    ),
    RubricCriterion(
        key="factual_accuracy",
        label="Factual Accuracy",
        description="Is the response factually correct (when verifiable)?",
        weight=2.0,
        required=False,
    ),
    RubricCriterion(
        key="completeness",
        label="Completeness",
        description="Does the response cover all necessary aspects?",
        weight=1.0,
        required=False,
    ),
    RubricCriterion(
        key="clarity",
        label="Clarity",
        description="Is the response clear and well-structured?",
        weight=1.0,
        required=False,
    ),
]


# ─────────────────────────────────────────────────────────────────
# LLM Judge Evaluator
# ─────────────────────────────────────────────────────────────────

class LLMJudgeEvaluator(Evaluator):
    """
    LLM-as-a-Judge evaluator.
    
    Uses an LLM to evaluate model outputs based on rubric criteria.
    Returns structured evaluation results in JSON format.
    """
    
    def __init__(
        self,
        judge_model: str = "anthropic:claude-sonnet-4-5-20250929",
        max_tokens: int = 2048,
    ) -> None:
        """
        Initialize the LLM Judge evaluator.
        
        Args:
            judge_model: Model string for the judge (e.g., "anthropic:claude-sonnet-4-5")
            max_tokens: Max tokens for judge response
        """
        self.judge_model = judge_model
        self.max_tokens = max_tokens
        
    def evaluate(self, eval_input: EvalInput) -> EvalResult:
        """
        Evaluate a model output using an LLM judge.
        
        Returns:
            EvalResult with structured judge assessment
        """
        try:
            # Resolve provider for judge
            provider, fallback_reason = resolve_provider(self.judge_model)
            
            if fallback_reason:
                return EvalResult(
                    evaluator_name="llm_judge",
                    score=None,
                    passed=None,
                    confidence=None,
                    failure_category="provider_error",
                    summary_reason=None,
                    rubric_scores=[],
                    metrics={},
                    raw_judge_output=None,
                    error=f"Judge provider unavailable: {fallback_reason}",
                )
            
            # Validate provider supports judge role
            # LLM judge requires structured JSON output, only Anthropic provider is tested/supported
            if not isinstance(provider, AnthropicProvider):
                provider_type = type(provider).__name__
                return EvalResult(
                    evaluator_name="llm_judge",
                    score=None,
                    passed=None,
                    confidence=None,
                    failure_category="provider_error",
                    summary_reason=None,
                    rubric_scores=[],
                    metrics={},
                    raw_judge_output=None,
                    error=(
                        f"LLM judge requires Anthropic provider; got {provider_type}. "
                        f"Judge model must be 'anthropic:...' with valid ANTHROPIC_API_KEY."
                    ),
                )
            
            # Build judge prompt
            prompt = self._build_judge_prompt(eval_input)
            
            # Call judge using AnthropicProvider's extended interface
            try:
                judge_response = provider.generate(prompt=prompt, max_tokens=self.max_tokens)
            except ProviderFatalError as exc:
                return EvalResult(
                    evaluator_name="llm_judge",
                    score=None,
                    passed=None,
                    confidence=None,
                    failure_category="provider_error",
                    summary_reason=None,
                    rubric_scores=[],
                    metrics={},
                    raw_judge_output=None,
                    error=f"Judge API fatal error: {exc}",
                )
            
            # Parse judge response
            return self._parse_judge_response(judge_response, eval_input)
            
        except Exception as exc:
            return EvalResult(
                evaluator_name="llm_judge",
                score=None,
                passed=None,
                confidence=None,
                failure_category="unknown",
                summary_reason=None,
                rubric_scores=[],
                metrics={},
                raw_judge_output=None,
                error=f"Unexpected error in LLM judge: {exc}",
            )
    
    def _build_judge_prompt(self, eval_input: EvalInput) -> str:
        """
        Build the prompt for the LLM judge.
        
        Returns strict JSON-only prompt with rubric criteria.
        """
        rubric = eval_input.rubric or DEFAULT_RUBRIC
        
        # Build rubric description
        rubric_lines: list[str] = []
        for criterion in rubric:
            required_marker = " (REQUIRED)" if criterion.required else ""
            rubric_lines.append(
                f"- {criterion.key}{required_marker}: {criterion.description} (weight: {criterion.weight})"
            )
        rubric_text = "\n".join(rubric_lines)
        
        # Build expected answer section
        expected_section = ""
        if eval_input.expected_answer:
            expected_section = f"""
Reference Answer (if helpful for comparison):
{eval_input.expected_answer}
"""
        
        # Build the prompt
        prompt = f"""You are an expert evaluator assessing the quality of an AI model's response.

INPUT PROMPT:
{eval_input.prompt}
{expected_section}
MODEL OUTPUT:
{eval_input.model_output}

EVALUATION RUBRIC:
{rubric_text}

INSTRUCTIONS:
1. Evaluate the model output against each rubric criterion
2. For each criterion, assign a score from 0.0 to 1.0 (1.0 = perfect)
3. Determine if each criterion passed (true/false)
4. Provide a brief reason for each score
5. Calculate an overall score (weighted average)
6. Determine overall pass/fail
7. Assign a failure category if applicable
8. Provide a brief summary

FAILURE CATEGORIES (use when passed=false):
- hallucination: Model invented facts or information
- incomplete_answer: Response is missing critical information
- format_error: Response format is incorrect or unusable
- refusal_mismatch: Model refused when it shouldn't have (or vice versa)
- low_quality_reasoning: Reasoning is flawed or unclear
- unknown: Unclear why the response failed

OUTPUT FORMAT:
Respond ONLY with valid JSON. No markdown, no preamble, no explanation outside the JSON.
Use exactly this structure:

{{
  "score": 0.85,
  "passed": true,
  "summary_reason": "Brief explanation of overall assessment",
  "failure_category": null,
  "confidence": 0.9,
  "rubric_scores": [
    {{
      "key": "answered_user_request",
      "score": 1.0,
      "passed": true,
      "reason": "Directly addressed the question"
    }},
    {{
      "key": "factual_accuracy",
      "score": 0.8,
      "passed": true,
      "reason": "Mostly accurate with minor imprecision"
    }}
  ]
}}

Respond now with ONLY the JSON:"""
        
        return prompt
    
    def _parse_judge_response(
        self,
        response: str,
        eval_input: EvalInput,
    ) -> EvalResult:
        """
        Parse the judge's JSON response into an EvalResult.
        
        Handles malformed responses gracefully.
        """
        try:
            # Strip any markdown fencing if present
            response = response.strip()
            if response.startswith("```"):
                # Remove ```json or ``` prefix
                lines = response.split("\n")
                if lines[0].strip() in ["```json", "```"]:
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                response = "\n".join(lines)
            
            # Parse JSON
            try:
                judge_data = json.loads(response)
            except json.JSONDecodeError as exc:
                return EvalResult(
                    evaluator_name="llm_judge",
                    score=None,
                    passed=None,
                    confidence=None,
                    failure_category="judge_parsing_error",
                    summary_reason=None,
                    rubric_scores=[],
                    metrics={},
                    raw_judge_output={"raw_response": response},
                    error=f"Failed to parse judge JSON: {exc}",
                )
            
            # Extract rubric scores
            rubric_scores: list[RubricScore] = []
            if "rubric_scores" in judge_data and isinstance(judge_data["rubric_scores"], list):
                for rs in judge_data["rubric_scores"]:
                    if isinstance(rs, dict):
                        rubric_scores.append(RubricScore(
                            key=rs.get("key", "unknown"),
                            score=rs.get("score"),
                            passed=rs.get("passed"),
                            reason=rs.get("reason"),
                            weight=rs.get("weight", 1.0),
                        ))
            
            # Build EvalResult
            return EvalResult(
                evaluator_name="llm_judge",
                score=judge_data.get("score"),
                passed=judge_data.get("passed"),
                confidence=judge_data.get("confidence"),
                failure_category=judge_data.get("failure_category"),
                summary_reason=judge_data.get("summary_reason"),
                rubric_scores=rubric_scores,
                metrics={},
                raw_judge_output=judge_data,
                error=None,
            )
            
        except Exception as exc:
            return EvalResult(
                evaluator_name="llm_judge",
                score=None,
                passed=None,
                confidence=None,
                failure_category="judge_parsing_error",
                summary_reason=None,
                rubric_scores=[],
                metrics={},
                raw_judge_output={"raw_response": response if isinstance(response, str) else None},
                error=f"Unexpected error parsing judge response: {exc}",
            )
