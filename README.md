# ScrapeVerse

An autonomous, self-healing web scraping platform powered by Bright Data, automated DOM telemetry, and AI selector repair.

---

## Problem

Traditional web scrapers break when websites update their frontend markup, change class names, or modify CSS selectors. A minor DOM modification—such as renaming a `.product-price` class—leads to silent data loss, pipeline downtime, and requires manual engineering intervention to diagnose and patch broken selectors.

---

## Solution

ScrapeVerse eliminates scraping downtime by introducing an autonomous self-healing loop. When an extraction fails or returns missing required fields, ScrapeVerse detects the anomaly, analyzes the target DOM structure, synthesizes a repaired replacement selector, retries data extraction, and validates the normalized result before delivering it to downstream pipelines.

---

## Key Innovation

**Autonomous Self-Healing Web Scraping Engine**: Real-time failure detection coupled with heuristic/LLM-assisted selector repair that diagnoses broken selectors and restores data flow without human intervention or pipeline restarts.

---

## Architecture

```text
React (Vite Dashboard)
      │
      ▼
FastAPI (REST Backend Engine)
      │
      ▼
Scraper Service (Bright Data & Local Mock Client)
      │
      ▼
Self-Healing Engine (backend/automation/)
      │
      ├─► FailureDetector (Flags missing fields / broken selectors)
      ├─► DOMAnalyzer (Inspects HTML & scores replacement candidates)
      └─► SelectorRepairEngine (AI/Heuristic selector proposal)
      │
      ▼
Retry Execution (Re-scrapes with synthesized selector)
      │
      ▼
HealingValidator (Ensures schema compliance & non-empty data)
      │
      ▼
Healed Output (Delivers normalized, verified JSON payload)
```

---

## Features

- **Bright Data Integration**: Production-ready client interface for Bright Data API collectors (`/dca/trigger` and `/dca/get_result`).
- **Mock Development Mode**: Offline local scraping parser reading `mock-site/index.html` for instant, deterministic testing without requiring live credentials.
- **Data Normalization Layer**: Standardizes prices into `$XX.XX` format, trims titles, and normalizes stock labels into `"In Stock"` / `"Out of Stock"`.
- **Data Validation**: Strict Pydantic v2 schemas and validation rules ensuring required fields (`title`, `price`, `stock_status`) are present and non-empty.
- **Failure Detection**: Identifies `SelectorNotFound`, empty datasets, missing attributes, and malformed field values.
- **DOM Analysis**: Inspects HTML trees using standard DOM parsers to score and locate candidate replacement elements.
- **Selector Repair**: Generates replacement selectors with confidence scores and reasoning (supporting deterministic `MOCK_LLM=true` mode).
- **Automatic Retry & Bounded Execution**: Automatically re-executes extraction with configurable maximum retry protection (`max_retries`) to eliminate infinite loops.
- **Post-Repair Validation**: Verifies that re-scraped payloads satisfy all required schema and content constraints.
- **Cybersecurity / DevTools Dashboard**: React + Vite UI providing real-time telemetry, visual timeline steppers, selector diffs, and health metrics.
- **Real-Time Healing Logs**: Live diagnostic event stream with a JSON inspector to monitor extraction telemetry.
- **GitHub Actions CI/CD**: Automated testing pipeline running pytest across all 36 test cases on every push and pull request.

---

## Demo Scenario

ScrapeVerse demonstrates self-healing through a controlled website mutation:

1. **Initial Baseline State**:
   - The target mock store (`mock-site/index.html`) contains: `<p class="product-price">$49.99</p>`.
   - The scraper runs with `.product-price` and extracts `$49.99` with status `SUCCESS`.

2. **Simulated Website Mutation**:
   - The website updates its layout, changing the price element to: `<div class="current-price">$49.99</div>`.
   - The scraper attempts extraction using `.product-price` and fails (`Required field "price" is missing`).

3. **Autonomous Self-Healing Sequence**:
   - **Failure Detected**: `FailureDetector` identifies that the `price` field is missing.
   - **DOM Analyzed**: `DOMAnalyzer` parses the changed HTML and flags `<div class="current-price">` as a 100% confidence candidate.
   - **Repair Proposed**: `SelectorRepairEngine` proposes `.product-price` &rarr; `.current-price`.
   - **Retry & Validation**: The scraper re-extracts `$49.99` with `.current-price`, passes `HealingValidator`, and marks the collector `HEALTHY`.

> **Note**: `mock-site/index.html` remains permanently healthy with `.product-price`. The mutation is executed in-memory during demo requests (`POST /api/healing/demo` or `POST /api/healing/test`).

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn, Pydantic v2, Pydantic-Settings, HTTPX
- **Scraping**: Bright Data API Client, Built-in HTMLParser
- **Frontend**: React 18, Vite, Vanilla CSS (DevTools Theme), Lucide Icons
- **AI / Self-Healing**: DOM Analyzer, Rule/LLM Selector Repair Engine
- **Testing & CI/CD**: Pytest, GitHub Actions

---

## Project Structure

```text
Scrape-Verse-IndiScrapers/
├── .github/
│   └── workflows/
│       └── tests.yml               # Automated CI test runner
├── backend/
│   ├── main.py                     # FastAPI application entry point
│   ├── scraper/                    # Scraping Layer (Person 1)
│   │   ├── __init__.py             # Public scraper facade
│   │   ├── base.py                 # Abstract ScraperClient interface
│   │   ├── brightdata_client.py    # Production Bright Data API client
│   │   ├── mock_client.py          # Local offline HTML parser client
│   │   ├── mock_scraper.py         # Backward-compatibility helper
│   │   ├── service.py              # Scraper pipeline orchestrator
│   │   ├── normalizer.py           # Price, title, and stock normalization
│   │   ├── validator.py            # Required field validation logic
│   │   ├── models.py               # Pydantic product & scrape schemas
│   │   ├── config.py               # Environment configuration settings
│   │   └── exceptions.py           # Custom exception hierarchy
│   └── automation/                 # Self-Healing Layer (Person 2)
│       ├── __init__.py             # Public automation exports
│       ├── models.py               # HealingEvent, ScrapeFailure, SelectorRepair
│       ├── failure_detector.py     # Anomaly and selector failure detector
│       ├── dom_analyzer.py         # DOM candidate identification & scoring
│       ├── selector_repair.py      # Selector proposal & repair engine
│       ├── validator.py            # Post-repair validation engine
│       ├── healing_manager.py      # Self-healing orchestrator with retry bounds
│       └── router.py               # FastAPI APIRouter for healing endpoints
├── frontend/                       # Dashboard (Person 3)
│   ├── package.json                # Frontend package manifest
│   ├── vite.config.js              # Vite bundler & API proxy configuration
│   ├── index.html                  # HTML entry point
│   └── src/
│       ├── main.jsx                # React root mount
│       ├── App.jsx                 # Dashboard state & orchestration
│       ├── index.css               # Design system & dark theme tokens
│       ├── App.css                 # Component layouts, diffs & timeline styles
│       ├── services/
│       │   └── api.js              # API service client for FastAPI backend
│       └── components/
│           ├── Header.jsx          # Header, engine status & live clock
│           ├── MetricsBar.jsx      # Scraper health & incident statistics
│           ├── ScraperCard.jsx     # Scraper controls (Run, Fail, Heal)
│           ├── DataTable.jsx       # Extracted product records table
│           ├── HealingTimeline.jsx # Visual 7-step self-healing stepper
│           ├── SelectorDiffPanel.jsx # Old vs New selector diff & AI telemetry
│           └── ActivityLogs.jsx    # Real-time event log & JSON inspector
├── mock-site/
│   └── index.html                  # Local baseline e-commerce store
├── tests/
│   ├── test_scraper.py             # 18 unit tests for scraping & normalization
│   └── test_automation.py          # 18 unit tests for self-healing & API routes
├── .env.example                    # Environment variable template
├── requirements.txt                # Python backend dependencies
└── README.md                       # Project documentation
```

---

## Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 1. Backend Setup
```bash
# Clone the repository
git clone https://github.com/NitishAwesome/Scrape-Verse-IndiScrapers.git
cd Scrape-Verse-IndiScrapers

# Install Python dependencies
pip install -r requirements.txt

# (Optional) Configure environment variables
cp .env.example .env

# Start the FastAPI server
python -m uvicorn backend.main:app --reload
```
The backend will be live at `http://localhost:8000`. Interactive Swagger API docs are available at `http://localhost:8000/docs`.

### 2. Frontend Setup
```bash
# Open a new terminal in the repository root
cd frontend

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
The dashboard will open at `http://localhost:5173`.

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Engine health check (`{"status": "online"}`). |
| `GET` | `/api/scrape` | Executes the standard scraper against `mock-site/index.html`. |
| `GET` | `/api/scrape?fail=true` | Simulates a broken selector execution error. |
| `GET` | `/api/healing/status` | Returns self-healing configuration, mock mode status, and supported failure types. |
| `POST` | `/api/healing/test` | Runs the full controlled self-healing sequence and returns structured healing results. |
| `POST` | `/api/healing/demo` | Alias for self-healing demonstration endpoint. |

---

## Testing

Run the comprehensive 36-test suite covering scraping, normalization, validation, failure detection, DOM analysis, selector repair, and API routes:

```bash
python -m pytest
```

**Test Coverage Summary**:
- `tests/test_scraper.py` (18 tests): Tests mock parser, Bright Data client format handling, price normalization, title sanitization, stock status mapping, and validator constraints.
- `tests/test_automation.py` (18 tests): Tests empty response detection, missing required field detection, DOM candidate extraction, selector repair proposals, bounded retry protection, mutation recovery (`.product-price` &rarr; `.current-price`), and FastAPI endpoints.

---

## Team

- **Nitish Gupta** ([@NitishAwesome](https://github.com/NitishAwesome)) — Full-Stack & Systems Development (Scraper Integration, Self-Healing Engine, FastAPI Backend, React Dashboard, Testing & CI/CD).

*Note: Developed and consolidated for the hackathon submission.*

---

## License

This project is licensed under the [MIT License](LICENSE).
