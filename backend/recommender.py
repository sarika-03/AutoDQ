"""
recommender.py
LLM-powered data quality test recommender for dq-pilot.
Takes a TableProfile + TestDefinitions and returns structured recommendations.
"""

import os
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import anthropic

from om_client import ColumnProfile, TableProfile, TestDefinition, ExistingTest

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"


# ---------------------------------------------------------------------------
# Output data class
# ---------------------------------------------------------------------------

@dataclass
class TestRecommendation:
    column_name: Optional[str]          # None = table-level test
    test_definition_name: str
    display_name: str
    parameters: list[dict]              # [{"name": "...", "value": "..."}]
    severity: str                       # "CRITICAL" | "WARNING"
    reasoning: str
    confidence: str                     # "HIGH" | "MEDIUM" | "LOW"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a senior data quality engineer with deep expertise in data profiling 
and test design. Your job is to analyze a table's column profiles and suggest 
the most appropriate data quality tests.

You think carefully about:
- Column names and what they imply (email, id, amount, date, status, etc.)
- Data types and their constraints
- Statistical profiles (null rates, uniqueness, value ranges)
- Business logic implied by column descriptions
- Which tests will catch real data issues vs. noisy false positives

You always respond with valid JSON only. No preamble, no markdown fences, 
no explanation outside the JSON structure.
""".strip()


def _build_user_prompt(
    table: TableProfile,
    definitions: list[TestDefinition],
    existing_tests: list[ExistingTest],
) -> str:
    # Summarize existing tests so LLM skips them
    existing_summary = [
        {"column": t.column_name or "TABLE", "test": t.test_definition_name}
        for t in existing_tests
    ]

    # Serialize column profiles compactly
    columns_data = []
    for col in table.columns:
        columns_data.append({
            "name": col.name,
            "data_type": col.data_type,
            "description": col.description or "",
            "nullable": col.nullable,
            "null_proportion": round(col.null_proportion, 4),
            "unique_proportion": round(col.unique_proportion, 4),
            "distinct_count": col.distinct_count,
            "min_value": col.min_value,
            "max_value": col.max_value,
            "mean": col.mean,
        })

    # Summarize available test definitions
    test_defs_summary = []
    for d in definitions:
        params = [
            {"name": p["name"], "required": p.get("required", False),
             "type": p.get("dataType", "string")}
            for p in d.parameter_definition
        ]
        test_defs_summary.append({
            "name": d.name,
            "display_name": d.display_name,
            "entity_type": d.entity_type,
            "description": d.description,
            "supported_data_types": d.supported_data_types,
            "parameters": params,
        })

    prompt = f"""
Analyze this table and recommend data quality tests.

## Table
- FQN: {table.fqn}
- Description: {table.description or "No description provided"}
- Row count: {table.row_count:,}
- Column count: {table.column_count}

## Column Profiles
{json.dumps(columns_data, indent=2)}

## Available Test Definitions
{json.dumps(test_defs_summary, indent=2)}

## Already Existing Tests (DO NOT re-suggest these)
{json.dumps(existing_summary, indent=2)}

## Instructions
For each column (and the table itself if applicable), suggest the most 
valuable data quality tests. For every recommendation provide:

1. Whether it's a column-level or table-level test
2. The exact test definition name from the available list
3. Concrete parameter values (use actual numbers from the profile, not placeholders)
4. Severity: CRITICAL (data pipeline breaks or PII risk) or WARNING (data drift)
5. Plain-English reasoning (2-3 sentences max) that a human reviewer can quickly scan
6. Confidence: HIGH / MEDIUM / LOW

Focus on tests that will catch REAL issues. Do not suggest a test for every 
column — only where there is a clear signal or business risk.

Respond ONLY with this JSON structure:
{{
  "table_fqn": "{table.fqn}",
  "recommendations": [
    {{
      "column_name": "column_name_or_null_for_table_level",
      "test_definition_name": "exactTestName",
      "display_name": "Human readable name",
      "parameters": [
        {{"name": "param_name", "value": "param_value"}}
      ],
      "severity": "CRITICAL",
      "reasoning": "Why this test matters for this specific column.",
      "confidence": "HIGH"
    }}
  ],
  "summary": "2-3 sentence overall assessment of this table's data quality risk."
}}
""".strip()

    return prompt


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_response(raw: str, definitions: list[TestDefinition]) -> list[TestRecommendation]:
    """Parse and validate the LLM JSON response into TestRecommendation objects."""

    # Strip accidental markdown fences if model adds them
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e

    # Build a lookup for quick validation
    valid_test_names = {d.name for d in definitions}

    recommendations = []
    for item in data.get("recommendations", []):
        test_name = item.get("test_definition_name", "")

        if test_name not in valid_test_names:
            logger.warning("LLM suggested unknown test '%s' — skipping", test_name)
            continue

        recommendations.append(TestRecommendation(
            column_name=item.get("column_name"),        # None = table-level
            test_definition_name=test_name,
            display_name=item.get("display_name", test_name),
            parameters=item.get("parameters", []),
            severity=item.get("severity", "WARNING").upper(),
            reasoning=item.get("reasoning", ""),
            confidence=item.get("confidence", "MEDIUM").upper(),
        ))

    return recommendations


# ---------------------------------------------------------------------------
# Main recommender class
# ---------------------------------------------------------------------------

class DQRecommender:
    """
    Uses Claude to analyze a TableProfile and return TestRecommendations.

    Usage:
        recommender = DQRecommender.from_env()
        recommendations = recommender.recommend(table_profile, test_definitions, existing_tests)
    """

    def __init__(self, api_key: str, model: str = CLAUDE_MODEL, max_tokens: int = 4096):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    @classmethod
    def from_env(cls) -> "DQRecommender":
        api_key = os.environ["ANTHROPIC_API_KEY"]
        model = os.environ.get("CLAUDE_MODEL", CLAUDE_MODEL)
        return cls(api_key=api_key, model=model)

    def recommend(
        self,
        table: TableProfile,
        definitions: list[TestDefinition],
        existing_tests: list[ExistingTest],
    ) -> tuple[list[TestRecommendation], str]:
        """
        Generate test recommendations for a table.

        Returns:
            (recommendations, summary_text)
        """
        if not table.columns:
            logger.warning("Table %s has no columns — nothing to recommend", table.fqn)
            return [], "No columns found in table profile."

        prompt = _build_user_prompt(table, definitions, existing_tests)

        logger.info("Sending profile for %s to Claude (%d columns)...",
                    table.fqn, len(table.columns))

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_response = message.content[0].text
        logger.debug("Raw LLM response:\n%s", raw_response)

        recommendations = _parse_response(raw_response, definitions)

        # Extract summary from JSON
        try:
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_response.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            summary = json.loads(cleaned).get("summary", "")
        except Exception:
            summary = ""

        logger.info("Got %d recommendations for %s", len(recommendations), table.fqn)
        return recommendations, summary

    def recommend_batch(
        self,
        tables: list[TableProfile],
        definitions: list[TestDefinition],
        existing_tests_map: dict[str, list[ExistingTest]],
    ) -> dict[str, tuple[list[TestRecommendation], str]]:
        """
        Run recommendations for multiple tables.

        Returns:
            dict mapping fqn → (recommendations, summary)
        """
        results = {}
        for table in tables:
            existing = existing_tests_map.get(table.fqn, [])
            try:
                recs, summary = self.recommend(table, definitions, existing)
                results[table.fqn] = (recs, summary)
            except Exception as e:
                logger.error("Failed to get recommendations for %s: %s", table.fqn, e)
                results[table.fqn] = ([], f"Error: {e}")
        return results