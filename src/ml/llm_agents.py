#!/usr/bin/env python3
"""
LLM-Powered Autonomous Agents

Uses local LLM (cost: $0) for intelligent reasoning in ML improvement tasks:
- Creative hypothesis generation
- Feature engineering code generation
- Error analysis and diagnosis
- Experiment prioritization
- Report writing

Local LLM Configuration:
    URL: http://172.16.108.209:1234
    Model: openai/gpt-oss-20b
    API: OpenAI-compatible

Usage:
    from src.ml.llm_agents import LLMBrainstormAgent, LLMCodeGeneratorAgent

    # Generate creative feature ideas
    brainstorm = LLMBrainstormAgent()
    ideas = brainstorm.generate_feature_ideas(context)

    # Generate feature engineering code
    codegen = LLMCodeGeneratorAgent()
    code = codegen.generate_feature_code(feature_spec)
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import hashlib
import time
import logging
import re
import traceback
from abc import ABC, abstractmethod

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('llm_agents')


# =============================================================================
# Local LLM Client
# =============================================================================

@dataclass
class LLMConfig:
    """Configuration for local LLM."""
    base_url: str = "http://172.16.108.209:1234"
    model: str = "openai/gpt-oss-20b"
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 120


class LocalLLMClient:
    """
    Client for local LLM using OpenAI-compatible API.

    Cost: $0 (runs on local hardware)
    """

    def __init__(self, config: LLMConfig = None):
        self.config = config or LLMConfig()
        self.api_url = f"{self.config.base_url}/v1/chat/completions"
        self._available = None

    def is_available(self) -> bool:
        """Check if local LLM is available."""
        if self._available is not None:
            return self._available

        try:
            response = requests.get(
                f"{self.config.base_url}/v1/models",
                timeout=5
            )
            self._available = response.status_code == 200
        except Exception:
            self._available = False

        return self._available

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = None,
             max_tokens: int = None) -> Optional[str]:
        """
        Send chat completion request to local LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text or None on failure
        """
        if not self.is_available():
            logger.warning("Local LLM not available")
            return None

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                logger.error(f"LLM request failed: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.error("LLM request timed out")
            return None
        except Exception as e:
            logger.error(f"LLM request error: {e}")
            return None

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Simple prompt completion."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)


# Global client instance
_llm_client: Optional[LocalLLMClient] = None


def get_llm_client() -> LocalLLMClient:
    """Get or create global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LocalLLMClient()
    return _llm_client


# =============================================================================
# LLM Brainstorm Agent
# =============================================================================

class LLMBrainstormAgent:
    """
    Uses local LLM to brainstorm creative feature engineering ideas.

    Capabilities:
    - Generate novel feature ideas based on domain knowledge
    - Propose creative feature interactions
    - Suggest external data sources to explore
    - Identify potential predictive signals
    """

    SYSTEM_PROMPT = """You are an expert machine learning engineer specializing in fantasy football prediction models.

Your task is to brainstorm creative feature engineering ideas that could improve PPG (points per game) predictions for NFL players.

Current model context:
- Predicting next season's fantasy PPG for NFL players
- Position types: QB, RB, WR, TE
- Current R² score: ~0.80, RMSE: ~2.47 PPG
- Uses features: age, experience, past stats, snap counts, combine metrics, draft capital

When suggesting features, consider:
- Position-specific predictors (RB aging curves differ from WR)
- Usage metrics (targets, carries, snap share)
- Efficiency metrics (yards per attempt, catch rate)
- Opportunity indicators (team offense quality, depth chart)
- External factors (schedule strength, weather, injuries)

Output your ideas in JSON format with this structure:
{
    "features": [
        {
            "name": "feature_name",
            "description": "What this feature captures",
            "hypothesis": "Why this might predict future performance",
            "formula": "pandas code to compute it",
            "expected_correlation": 0.3,
            "data_requirements": ["required columns"]
        }
    ]
}"""

    def __init__(self, llm_client: LocalLLMClient = None):
        self.llm = llm_client or get_llm_client()

    def generate_feature_ideas(self, context: Dict = None) -> List[Dict]:
        """
        Generate creative feature ideas using LLM.

        Args:
            context: Optional context about current model state

        Returns:
            List of feature idea dictionaries
        """
        if not self.llm.is_available():
            logger.warning("LLM not available, returning empty ideas")
            return []

        # Build context prompt
        context_info = ""
        if context:
            if 'current_features' in context:
                context_info += f"\nCurrent features ({len(context['current_features'])} total): "
                context_info += ", ".join(context['current_features'][:20])

            if 'recent_experiments' in context:
                context_info += "\n\nRecent experiments:"
                for exp in context['recent_experiments'][:5]:
                    context_info += f"\n- {exp.get('name', 'unknown')}: "
                    context_info += f"R² change = {exp.get('improvement', 0):+.4f}"

            if 'top_correlations' in context:
                context_info += "\n\nTop correlated features with target:"
                for feat, corr in context['top_correlations'][:10]:
                    context_info += f"\n- {feat}: {corr:.3f}"

        prompt = f"""Based on the current model context, suggest 5 creative new features that could improve fantasy football PPG predictions.

{context_info}

Focus on features that:
1. Capture information not already in the model
2. Are computationally feasible
3. Have clear predictive logic

Respond with valid JSON only."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        response = self.llm.chat(messages, temperature=0.8)

        if not response:
            return []

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return data.get('features', [])
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        return []

    def suggest_data_sources(self) -> List[Dict]:
        """Suggest new data sources to explore."""
        if not self.llm.is_available():
            return []

        prompt = """Suggest 3 external data sources that could improve fantasy football predictions.

For each source, provide:
1. Name of the data source
2. What data it contains
3. How it could improve predictions
4. How to access it (API, web scraping, etc.)

Respond with valid JSON:
{
    "sources": [
        {
            "name": "source name",
            "description": "what data it has",
            "predictive_value": "how it helps predictions",
            "access_method": "how to get the data"
        }
    ]
}"""

        response = self.llm.generate(prompt, temperature=0.7)

        if not response:
            return []

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return data.get('sources', [])
        except json.JSONDecodeError:
            pass

        return []


# =============================================================================
# LLM Code Generator Agent
# =============================================================================

class LLMCodeGeneratorAgent:
    """
    Uses local LLM to generate feature engineering code.

    Capabilities:
    - Generate pandas code for feature computation
    - Create complex feature transformations
    - Write data preprocessing pipelines
    - Generate test cases for features
    """

    SYSTEM_PROMPT = """You are an expert Python programmer specializing in pandas and feature engineering for machine learning.

Your task is to generate clean, efficient pandas code for computing features from NFL player statistics data.

The input DataFrame typically has columns like:
- player_id, player_name, team, position, season
- age, years_exp, games
- targets, receptions, receiving_yards, receiving_tds
- carries, rushing_yards, rushing_tds
- snap_pct, games_started
- ppg_ppr (fantasy points per game)
- next_ppg_ppr (target variable)

Requirements for generated code:
1. Use vectorized pandas operations (no loops)
2. Handle missing values appropriately
3. Avoid division by zero
4. Add comments explaining the logic
5. Return the feature as a pandas Series

Output format:
```python
# Feature: {feature_name}
# Description: {description}
def compute_{feature_name}(df):
    \"\"\"Compute {feature_name} feature.\"\"\"
    # Your code here
    return result
```"""

    def __init__(self, llm_client: LocalLLMClient = None):
        self.llm = llm_client or get_llm_client()

    def generate_feature_code(self, feature_spec: Dict) -> Optional[str]:
        """
        Generate pandas code for a feature specification.

        Args:
            feature_spec: Dict with 'name', 'description', 'formula' (optional)

        Returns:
            Python code string or None
        """
        if not self.llm.is_available():
            return None

        name = feature_spec.get('name', 'unnamed_feature')
        description = feature_spec.get('description', 'A feature')
        hint = feature_spec.get('formula', '')

        prompt = f"""Generate pandas code to compute this feature:

Feature Name: {name}
Description: {description}
{f'Hint/Formula: {hint}' if hint else ''}

Requirements:
1. Handle NaN values
2. Avoid division by zero
3. Use efficient vectorized operations
4. Include docstring and comments

Return ONLY the Python code, no explanations."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        response = self.llm.chat(messages, temperature=0.3)

        if not response:
            return None

        # Extract code from response
        code_match = re.search(r'```python\n([\s\S]*?)```', response)
        if code_match:
            return code_match.group(1).strip()

        # If no code block, try to extract function definition
        func_match = re.search(r'(def compute_[\s\S]+)', response)
        if func_match:
            return func_match.group(1).strip()

        return response.strip()

    def generate_batch_features(self, feature_specs: List[Dict]) -> Dict[str, str]:
        """Generate code for multiple features."""
        results = {}
        for spec in feature_specs:
            code = self.generate_feature_code(spec)
            if code:
                results[spec.get('name', 'unnamed')] = code
        return results

    def validate_generated_code(self, code: str, df: pd.DataFrame) -> Dict:
        """
        Validate generated code against sample data.

        Returns dict with 'valid', 'error', 'sample_output'
        """
        result = {
            'valid': False,
            'error': None,
            'sample_output': None,
        }

        try:
            # Create a safe execution environment
            local_vars = {'df': df.copy(), 'pd': pd, 'np': np}

            # Execute the code
            exec(code, {'pd': pd, 'np': np}, local_vars)

            # Find the compute function
            compute_func = None
            for name, obj in local_vars.items():
                if name.startswith('compute_') and callable(obj):
                    compute_func = obj
                    break

            if compute_func:
                output = compute_func(df)
                result['valid'] = True
                result['sample_output'] = output.head(5).tolist()
            else:
                result['error'] = "No compute function found in generated code"

        except Exception as e:
            result['error'] = str(e)

        return result


# =============================================================================
# LLM Error Analyzer Agent
# =============================================================================

class LLMErrorAnalyzerAgent:
    """
    Uses local LLM to analyze prediction errors and diagnose issues.

    Capabilities:
    - Analyze patterns in prediction errors
    - Identify systematic biases
    - Suggest targeted fixes
    - Explain error causes
    """

    SYSTEM_PROMPT = """You are an expert in machine learning model diagnostics and fantasy football analytics.

Your task is to analyze prediction errors from a fantasy football PPG prediction model and identify:
1. Systematic patterns in the errors
2. Potential causes of poor predictions
3. Specific improvements to fix the issues

When analyzing errors, consider:
- Position-specific patterns (are we worse at predicting RBs vs WRs?)
- Age-related biases (over/under predicting young/old players)
- Breakout detection (missing players who significantly improve)
- Decline detection (missing players who significantly regress)
- Injury impact (not properly accounting for injury risk)
- Team context (not accounting for team changes, coaching, etc.)

Provide actionable recommendations with specific feature suggestions."""

    def __init__(self, llm_client: LocalLLMClient = None):
        self.llm = llm_client or get_llm_client()

    def analyze_errors(self, error_data: Dict) -> Dict:
        """
        Analyze prediction errors and provide diagnosis.

        Args:
            error_data: Dict containing error statistics and samples

        Returns:
            Analysis dict with patterns, causes, and recommendations
        """
        if not self.llm.is_available():
            return {'error': 'LLM not available'}

        # Format error data for LLM
        error_summary = json.dumps(error_data, indent=2, default=str)

        prompt = f"""Analyze these prediction errors from our fantasy football PPG model:

{error_summary}

Provide:
1. Key patterns you observe
2. Likely causes of the errors
3. Specific feature engineering suggestions to fix each issue
4. Priority ranking of fixes (highest impact first)

Respond with valid JSON:
{{
    "patterns": ["pattern 1", "pattern 2"],
    "causes": ["cause 1", "cause 2"],
    "recommendations": [
        {{
            "issue": "description",
            "fix": "specific fix",
            "feature_suggestion": "pandas formula or feature idea",
            "priority": 1-10
        }}
    ]
}}"""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        response = self.llm.chat(messages, temperature=0.5)

        if not response:
            return {'error': 'No response from LLM'}

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {'raw_response': response}

    def explain_prediction_error(self, player_data: Dict, predicted: float,
                                  actual: float) -> str:
        """Explain why a specific prediction was wrong."""
        if not self.llm.is_available():
            return "LLM not available for explanation"

        error = predicted - actual
        error_pct = (error / actual * 100) if actual != 0 else 0

        prompt = f"""Explain why this fantasy football prediction was wrong:

Player: {player_data.get('name', 'Unknown')}
Position: {player_data.get('position', 'Unknown')}
Age: {player_data.get('age', 'Unknown')}
Previous PPG: {player_data.get('prev_ppg', 'Unknown')}

Predicted PPG: {predicted:.1f}
Actual PPG: {actual:.1f}
Error: {error:+.1f} ({error_pct:+.1f}%)

What likely caused this prediction error? Consider:
- Player-specific factors
- Team context changes
- Injury history
- Typical model blindspots

Provide a brief (2-3 sentence) explanation."""

        response = self.llm.generate(prompt, temperature=0.5, max_tokens=256)
        return response or "Unable to generate explanation"


# =============================================================================
# LLM Hypothesis Prioritizer
# =============================================================================

class LLMHypothesisPrioritizer:
    """
    Uses local LLM to intelligently prioritize experiment hypotheses.

    Capabilities:
    - Evaluate hypothesis quality
    - Predict experiment success probability
    - Rank hypotheses by expected value
    - Identify redundant or conflicting hypotheses
    """

    SYSTEM_PROMPT = """You are an expert in machine learning experimentation and A/B testing.

Your task is to evaluate and prioritize experiment hypotheses for a fantasy football prediction model.

Consider:
1. Expected impact on model performance
2. Likelihood of success based on similar past experiments
3. Resource cost (computation time)
4. Novelty vs. proven approaches
5. Risk of negative impact

Score each hypothesis from 0-10 based on expected value (impact * probability of success)."""

    def __init__(self, llm_client: LocalLLMClient = None):
        self.llm = llm_client or get_llm_client()

    def prioritize_hypotheses(self, hypotheses: List[Dict],
                             experiment_history: List[Dict] = None) -> List[Dict]:
        """
        Re-prioritize hypotheses using LLM reasoning.

        Args:
            hypotheses: List of hypothesis dicts
            experiment_history: Optional past experiment results

        Returns:
            Prioritized list of hypotheses with scores
        """
        if not self.llm.is_available():
            return hypotheses

        # Prepare context
        hypotheses_text = json.dumps(hypotheses[:20], indent=2, default=str)

        history_text = ""
        if experiment_history:
            history_text = "\n\nPast experiment results:\n"
            for exp in experiment_history[:10]:
                history_text += f"- {exp.get('name', 'unknown')}: "
                history_text += f"R² change = {exp.get('improvement', 0):+.4f}\n"

        prompt = f"""Evaluate and score these experiment hypotheses:

{hypotheses_text}
{history_text}

For each hypothesis, provide:
1. Score (0-10) based on expected value
2. Brief rationale

Respond with JSON:
{{
    "rankings": [
        {{
            "id": "hypothesis_id",
            "score": 7.5,
            "rationale": "brief reason"
        }}
    ]
}}"""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        response = self.llm.chat(messages, temperature=0.3)

        if not response:
            return hypotheses

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                rankings = {r['id']: r for r in data.get('rankings', [])}

                # Update hypothesis priorities
                for h in hypotheses:
                    if h.get('id') in rankings:
                        h['llm_score'] = rankings[h['id']]['score']
                        h['llm_rationale'] = rankings[h['id']]['rationale']
                        h['priority'] = rankings[h['id']]['score']

                # Sort by priority
                hypotheses.sort(key=lambda x: -x.get('priority', 0))

        except json.JSONDecodeError:
            pass

        return hypotheses


# =============================================================================
# LLM Report Generator
# =============================================================================

class LLMReportGenerator:
    """
    Uses local LLM to generate insightful reports on ML improvement progress.

    Capabilities:
    - Summarize experiment results
    - Identify key insights and trends
    - Recommend next steps
    - Generate human-readable narratives
    """

    def __init__(self, llm_client: LocalLLMClient = None):
        self.llm = llm_client or get_llm_client()

    def generate_cycle_report(self, cycle_stats: Dict) -> str:
        """Generate a narrative report for an improvement cycle."""
        if not self.llm.is_available():
            return self._fallback_report(cycle_stats)

        stats_json = json.dumps(cycle_stats, indent=2, default=str)

        prompt = f"""Write a brief (3-4 paragraph) report summarizing this ML improvement cycle:

{stats_json}

Include:
1. What was attempted and why
2. Key results and insights
3. What worked and what didn't
4. Recommendations for next steps

Write in a professional but accessible tone."""

        response = self.llm.generate(prompt, temperature=0.6, max_tokens=512)
        return response or self._fallback_report(cycle_stats)

    def generate_weekly_digest(self, weekly_stats: List[Dict]) -> str:
        """Generate a weekly digest of ML improvement progress."""
        if not self.llm.is_available():
            return "Weekly digest unavailable (LLM not connected)"

        stats_json = json.dumps(weekly_stats, indent=2, default=str)

        prompt = f"""Write a weekly digest summarizing ML model improvement progress:

{stats_json}

Include:
1. Overall progress this week
2. Best experiments and their impact
3. Patterns in what works
4. Strategic recommendations for next week

Keep it concise (4-5 paragraphs)."""

        response = self.llm.generate(prompt, temperature=0.6, max_tokens=768)
        return response or "Unable to generate weekly digest"

    def _fallback_report(self, cycle_stats: Dict) -> str:
        """Generate basic report when LLM unavailable."""
        report = []
        report.append("=== Improvement Cycle Report ===")
        report.append(f"Hypotheses generated: {cycle_stats.get('hypotheses_generated', 0)}")
        report.append(f"Experiments run: {cycle_stats.get('experiments_run', 0)}")
        report.append(f"Models promoted: {cycle_stats.get('models_promoted', 0)}")
        return "\n".join(report)


# =============================================================================
# Integrated LLM Agent Hub
# =============================================================================

class LLMAgentHub:
    """
    Central hub for all LLM-powered agents.

    Provides unified interface for:
    - Brainstorming new ideas
    - Generating code
    - Analyzing errors
    - Prioritizing experiments
    - Generating reports
    """

    def __init__(self, config: LLMConfig = None):
        self.llm = LocalLLMClient(config)
        self.brainstorm = LLMBrainstormAgent(self.llm)
        self.codegen = LLMCodeGeneratorAgent(self.llm)
        self.error_analyzer = LLMErrorAnalyzerAgent(self.llm)
        self.prioritizer = LLMHypothesisPrioritizer(self.llm)
        self.reporter = LLMReportGenerator(self.llm)

    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self.llm.is_available()

    def get_status(self) -> Dict:
        """Get LLM connection status."""
        return {
            'available': self.is_available(),
            'base_url': self.llm.config.base_url,
            'model': self.llm.config.model,
        }


# =============================================================================
# CLI for Testing
# =============================================================================

def main():
    """Test LLM agents."""
    import argparse

    parser = argparse.ArgumentParser(description='Test LLM Agents')
    parser.add_argument('--test-connection', action='store_true',
                       help='Test LLM connection')
    parser.add_argument('--brainstorm', action='store_true',
                       help='Generate feature ideas')
    parser.add_argument('--codegen', type=str, metavar='FEATURE_NAME',
                       help='Generate code for a feature')
    parser.add_argument('--status', action='store_true',
                       help='Show LLM status')

    args = parser.parse_args()

    hub = LLMAgentHub()

    if args.status or args.test_connection:
        status = hub.get_status()
        print(f"LLM Status: {'Connected' if status['available'] else 'Not Available'}")
        print(f"  URL: {status['base_url']}")
        print(f"  Model: {status['model']}")

        if args.test_connection and status['available']:
            print("\nTesting with simple prompt...")
            response = hub.llm.generate("What is 2+2? Answer with just the number.")
            print(f"Response: {response}")

    elif args.brainstorm:
        print("Brainstorming feature ideas...")
        ideas = hub.brainstorm.generate_feature_ideas()
        for i, idea in enumerate(ideas, 1):
            print(f"\n{i}. {idea.get('name', 'unnamed')}")
            print(f"   {idea.get('description', '')}")
            print(f"   Hypothesis: {idea.get('hypothesis', '')}")

    elif args.codegen:
        print(f"Generating code for feature: {args.codegen}")
        spec = {
            'name': args.codegen,
            'description': f'Compute {args.codegen} feature for fantasy prediction'
        }
        code = hub.codegen.generate_feature_code(spec)
        print("\nGenerated code:")
        print(code)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
