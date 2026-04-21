# dq-pilot — Product Requirements Document

**Version:** 1.0  
**Date:** April 2026  
**Team:** Dev + DevOps  
**Hackathon:** WeMakeDevs x OpenMetadata

---

## 1. Overview

### 1.1 Problem Statement

Data engineering teams manually define data quality (DQ) tests — a slow, inconsistent process that depends heavily on individual expertise. Most tables go untested, PII columns go unvalidated, and bad data reaches production before anyone notices.

### 1.2 Solution

**dq-pilot** is an AI-powered agent that analyzes a table's column profiles in OpenMetadata and automatically recommends appropriate data quality tests — with plain-English reasoning so humans can review before enabling.

### 1.3 One-Line Pitch

> Point dq-pilot at any table and it tells you exactly which data quality tests to add, why, and with what parameters — powered by OpenMetadata and Claude AI.

---

## 2. Goals

- Reduce time to set up DQ tests from hours to minutes
- Ensure consistent test coverage across all tables in an organization
- Surface PII, nullability, and range issues proactively
- Keep humans in the loop — agent recommends, humans approve

---

## 3. Non-Goals

- dq-pilot does not execute or schedule DQ tests
- dq-pilot does not replace manual test tuning for complex business rules
- dq-pilot does not ingest or transform data
- dq-pilot is not a monitoring or alerting system

---

## 4. Users

| User | Description | Primary Need |
|---|---|---|
| Data Engineer | Builds and maintains pipelines | Fast DQ test setup for new tables |
| Data Steward | Owns data governance | Ensure PII columns are validated |
| Analytics Engineer | Writes dbt models | Catch bad data before dashboards break |
| Data Platform Lead | Oversees data quality | Consistent coverage across all domains |

---

## 5. Functional Requirements

### 5.1 Core Features (P0 — Must Have)

| ID | Feature | Description |
|---|---|---|
| F01 | Table Profile Fetch | Fetch column names, types, descriptions, null%, unique%, min/max from OpenMetadata |
| F02 | Test Definition Fetch | Retrieve all available test templates from OpenMetadata's test library |
| F03 | AI Recommendation | Send profile + templates to Claude, receive structured test recommendations |
| F04 | Recommendation Output | Each recommendation includes: test name, parameters, severity, reasoning, confidence |
| F05 | Dry Run Mode | Print recommendations to terminal without creating anything in OpenMetadata |
| F06 | Apply Mode | Create draft test cases in OpenMetadata via API for human review |
| F07 | Skip Existing Tests | Do not re-suggest tests already defined on a table/column |

### 5.2 Intelligence Features (P1 — Should Have)

| ID | Feature | Description |
|---|---|---|
| F08 | Email Column Detection | Suggest regex validator + notNull + unique for email-type columns |
| F09 | Numeric Range Detection | Suggest `columnValuesToBeBetween` using min/max from profile |
| F10 | Enum Column Detection | Detect low cardinality columns, suggest `columnValuesToBeInSet` |
| F11 | Date/Timestamp Handling | Suggest freshness and range tests for date columns |
| F12 | High Null Warning | Flag columns with >10% null proportion as WARNING severity |
| F13 | ID Column Detection | Suggest uniqueness test for ID-type columns |
| F14 | Table-Level Tests | Suggest row count range test at the table level |

### 5.3 Bonus Features (P2 — Nice to Have)

| ID | Feature | Description |
|---|---|---|
| F15 | Batch Mode | Analyze all tables in a given OpenMetadata domain |
| F16 | JSON Output | `--output json` flag for programmatic consumption |
| F17 | Web UI | Simple browser UI to pick a table and approve/reject recommendations |
| F18 | Batch Summary Report | After batch run, print X tables analyzed, Y tests recommended |

---

## 6. Non-Functional Requirements

| ID | Category | Requirement | Target |
|---|---|---|---|
| N01 | Usability | Single command to run the agent | `python main.py --table <fqn>` |
| N02 | Security | No hardcoded credentials | All config via `.env` |
| N03 | Reliability | Validate LLM JSON before use | Reject + log on parse failure |
| N04 | Error Handling | Graceful failure on missing profile/API down/LLM error | Clear error messages |
| N05 | Testability | Unit tests for recommender logic using fixtures | >80% coverage on core logic |
| N06 | Portability | Full stack runs via Docker Compose | One command setup |
| N07 | CI/CD | Lint + unit tests run on every PR | GitHub Actions pipeline |
| N08 | Documentation | Working quickstart in README | Setup in under 5 minutes |

---

## 7. Technical Architecture

```
User
  │
  ▼
main.py (CLI)
  │
  ├── om_client.py          → OpenMetadata REST API
  │     ├── get_table_profile(fqn)
  │     ├── get_test_definitions()
  │     ├── get_existing_tests(fqn)
  │     └── create_test_case(...)
  │
  ├── recommender.py        → Claude API (LLM reasoning)
  │     ├── build_prompt(profile, definitions)
  │     ├── call_claude()
  │     └── parse_recommendations()
  │
  ├── test_creator.py       → Apply recommendations to OpenMetadata
  │     ├── dry_run()
  │     └── apply()
  │
  └── formatter.py          → CLI output formatting
        └── print_recommendations()

External Services:
  OpenMetadata (localhost:8585)
  Anthropic Claude API
```

---

## 8. Repository Structure

```
dq-pilot/
├── backend/
│   ├── main.py
│   ├── om_client.py
│   ├── recommender.py
│   ├── test_creator.py
│   ├── formatter.py
│   └── fixtures/
│       ├── email_column.json
│       ├── amount_column.json
│       ├── date_column.json
│       └── enum_column.json
├── tests/
│   ├── test_recommender.py
│   └── test_om_client.py
├── docker/
│   └── docker-compose.yml
├── scripts/
│   ├── setup.sh
│   ├── health_check.sh
│   └── run_agent.sh
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── demo.yml
├── prompts/
│   └── recommend.txt
├── .env.example
├── requirements.txt
└── README.md
```

---

## 9. Team Responsibilities

### Dev
- `backend/` — all agent logic
- `tests/` — unit tests
- `fixtures/` — sample column profiles
- `prompts/` — LLM prompt templates

### DevOps
- `docker/` — OpenMetadata stack
- `scripts/` — setup and run scripts
- `.github/workflows/` — CI/CD pipelines
- `README.md` — documentation
- `.env.example` — environment config

---

## 10. Development Timeline

| Day | Dev | DevOps |
|---|---|---|
| 1 | `om_client.py` — fetch table profile | Docker Compose up, verify OM running |
| 2 | `recommender.py` — LLM prompt + JSON parse | CI pipeline + `.env` config |
| 3 | `test_creator.py` — dry-run + apply modes | Setup scripts + health check |
| 4 | `formatter.py` + edge cases + unit tests | README + demo environment |
| 5 | Bug fixes + fixture JSON | Demo video + submission |

---

## 11. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OM_BASE_URL` | Yes | OpenMetadata server URL (e.g. `http://localhost:8585`) |
| `OM_JWT_TOKEN` | Yes | JWT token from OpenMetadata ingestion bot |
| `ANTHROPIC_API_KEY` | Yes | Claude API key from Anthropic console |
| `CLAUDE_MODEL` | No | Claude model to use (default: `claude-sonnet-4-20250514`) |
| `OM_TIMEOUT` | No | API timeout in seconds (default: `30`) |

---

## 12. Key OpenMetadata APIs Used

| API | Purpose |
|---|---|
| `GET /api/v1/tables/name/{fqn}` | Fetch table metadata + columns |
| `GET /api/v1/tables/{id}/tableProfile/latest` | Fetch column statistics |
| `GET /api/v1/dataQuality/testDefinitions` | List all test templates |
| `GET /api/v1/dataQuality/testCases` | Fetch existing test cases |
| `POST /api/v1/dataQuality/testCases` | Create new test case |

---

## 13. Demo Script (Hackathon Presentation)

1. Run: `python main.py --table sample_data.ecommerce_db.customers --dry-run`
2. Show agent fetching column profiles from OpenMetadata
3. Show LLM reasoning — column by column with severity and explanation
4. Run with `--apply` flag
5. Open OpenMetadata UI → show draft test cases created and ready to enable

**Total demo time: ~60 seconds**

---

## 14. Success Criteria

- [ ] Agent runs end-to-end on a real OpenMetadata table
- [ ] At least 5 column types handled intelligently (email, numeric, date, enum, ID)
- [ ] Dry-run and apply modes both working
- [ ] Unit tests passing in CI
- [ ] README quickstart works in under 5 minutes
- [ ] Demo video recorded and submitted
