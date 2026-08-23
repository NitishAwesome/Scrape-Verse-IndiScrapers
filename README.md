# 🛡️ ScrapeGuard — Self-Healing Web Scraping

<div align="center">

[![Scrape-Verse Hackathon](https://img.shields.io/badge/Scrape--Verse-Hackathon-red?style=for-the-badge)](https://wemakedevs.org/hackathons/scrape-verse)
[![WeMakeDevs](https://img.shields.io/badge/WeMakeDevs-Community-blue?style=for-the-badge)](https://wemakedevs.org)
[![Bright Data](https://img.shields.io/badge/Bright%20Data-Powered-orange?style=for-the-badge)](https://brightdata.com)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-Vite-61DAFB?style=for-the-badge&logo=react)](https://react.dev/)

**A self-healing web scraping system that detects broken extraction rules, analyzes website changes, repairs them automatically, and verifies the recovered data.**

[ GitHub Repository](https://github.com/NitishAwesome/Scrape-Verse-IndiScrapers)

</div>

---

##  What is ScrapeGuard?

ScrapeGuard is a resilient web scraping system built for the **Into the Scrape-Verse Hackathon**.

Traditional scrapers can stop working when a website changes its HTML structure. ScrapeGuard is designed to detect those failures, analyze the changed page structure, find safer replacement selectors, retry the extraction, and verify that the recovered data is actually valid.

The important principle is:

> **Repair is not success until the recovered data is verified.**

ScrapeGuard can also safely refuse to repair when there is not enough evidence instead of guessing and producing incorrect data.

---

##  Demo Video

[![ScrapeGuard Demo](https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=for-the-badge&logo=youtube)](https://youtu.be/8IvPIBiVpgo?si=rvZHz_Q3yKRs-Zwu)
---

## 1. The Problem

Traditional web scrapers depend on static CSS selectors and rigid DOM assumptions:
- **Websites evolve continuously**: Class names get renamed, layout hierarchies shift, and markup tags change during frontend updates.
- **Silent pipeline failures**: When selectors stop matching, scrapers often return empty arrays or truncated records without triggering HTTP errors.
- **Downstream corruption**: Incomplete or misaligned records enter production databases undetected.
- **High maintenance burden**: Engineering teams spend valuable hours diagnosing HTML changes, updating selectors, and backfilling lost data.

---

## 2. Our Solution

ScrapeGuard wraps web data collection in an automated reliability loop that detects structural breakage, synthesizes replacement rules, and verifies data integrity.

```text
Target Website
      ↓
Bright Data Scraper Studio Collector
      ↓
Extraction Health Check
      ↓
Failure Detection (Missing / Invalid Fields)
      ↓
Dynamic DOM Analysis & Heuristic Scoring
      ↓
Candidate Selector Ranking & Safety Gating (≥ 0.75)
      ↓
Extraction Retry
      ↓
Pydantic v2 Schema Contract Validation
      ↓
Verified Recovered Dataset OR Safe Failure
```

### Core Integrity Rules

- **"Repaired" does not automatically mean successful**: A discovered selector is only a hypothesis. ScrapeGuard re-executes extraction and validates the recovered dataset against strict schema rules before marking the pipeline healed.
- **Safe failure over guessing**: When DOM evidence is ambiguous, contradictory, or below the $0.75$ confidence threshold, ScrapeGuard **never invents selectors**. It halts safely and returns a structured `SAFE_FAILURE` state to prevent corrupt data ingestion.

---

## 3. Key Features

- **Live Bright Data Scraping**: Scrapes real-world target websites via Bright Data Scraper Studio infrastructure (`c_mt3d61eq4viqmv3f4`).
- **Dynamic DOM Telemetry**: Inspects live HTML trees, element tags, class semantics, currency symbols, and text structure without site-specific hardcoding.
- **Multi-Field Selector Recovery**: Repairs multiple broken extraction rules (e.g. title, price, stock status) simultaneously in a unified recovery cycle.
- **Partial Failure Isolation**: Preserves functioning selectors while isolating and repairing only broken extraction rules.
- **Ranked Replacement Candidates**: Evaluates and ranks candidate selectors with transparent confidence scores and heuristic reasoning.
- **Confidence Safety Gate ($\ge 0.75$)**: Enforces a strict evidence floor, rejecting low-confidence guesses.
- **Schema Contract Validation**: Verifies 100% of extracted records against strict Pydantic v2 data models (`ProductRecord`).
- **Before → Healing → After Summary**: Provides a full telemetry audit comparing baseline breakage, healing actions, and verified post-recovery results.
- **Failure Classification**: Classifies failures into standard tiers (`SelectorNotFound`, `ValidationError`, `EmptyResponse`, `DOMChanged`, `LowConfidence`, `UnsupportedStructure`).
- **Deterministic Data Quality Metrics**: Computes field completeness and valid record ratios directly from raw extracted records.
- **Controlled Failure Simulation**: Built-in deterministic fault injection for repeatable local testing (*not used as proof of live adaptability*).
- **Audit Dashboard**: Real-time interactive UI built with React, Vite, and modern CSS.

---

## 4. How Self-Healing Works

ScrapeGuard executes a 10-step autonomous resilience cycle:

1. **Scrape Target**: Fetches web data from the target website using the configured collector.
2. **Detect Failure**: Inspects extracted records for missing required fields, schema validation errors, or empty datasets.
3. **Acquire Target DOM**: Fetches the live HTML content of the target URL.
4. **Parse DOM Structure**: Evaluates element hierarchy, tags, attributes (`data-testid`, IDs, classes), and text content.
5. **Score Candidates**: Applies multi-factor semantic heuristics (tag type, class keywords, currency patterns, stock keywords, text length) to score candidate elements from $0.0$ to $1.0$.
6. **Rank & Gate Candidates**: Ranks candidate selectors per field and selects only candidates meeting the **$\ge 0.75$ confidence safety threshold**.
7. **Retry Extraction**: Re-executes extraction against the target DOM using the synthesized replacement selectors.
8. **Validate Contract**: Passes the recovered records through Pydantic v2 schema validation (`ProductRecord`).
9. **Verify Recovery**: If schema validation passes, patches runtime selector state, marks the recovery **`VERIFIED`**, and delivers the dataset downstream.
10. **Safe Failure**: If candidates score $< 0.75$ or validation fails, halts recovery and logs an explicit `SAFE_FAILURE` state.

---

## 5. Bright Data Integration

Bright Data provides the data collection infrastructure for ScrapeGuard.

- **Bright Data Scraper Studio**: Used as the external web scraping engine with Collector ID **`c_mt3d61eq4viqmv3f4`**.
- **Data Collector API**: ScrapeGuard interacts with Bright Data via asynchronous trigger (`/dca/trigger_immediate` & `/dca/trigger`) and result polling (`/dca/get_result`).
- **Bright Data Web Unlocker**: Leveraged for automated proxy rotation, CAPTCHA bypass, and anti-bot navigation on target websites.

### Clear Separation of Responsibilities

| Layer | Component | Responsibility |
|---|---|---|
| **Collection Infrastructure** | **Bright Data** | Manages rotating proxies, headless browsers, anti-bot bypass, and raw payload delivery from target URLs. |
| **Resilience & Orchestration** | **ScrapeGuard** | Normalizes data, monitors extraction health, detects failures, inspects DOMs, derives replacement selectors, enforces safety gates, validates schema contracts, and manages the dashboard. |

---

## 6. Demo

### A. Live Extraction (Healthy Baseline)
- **Target URL**: `https://books.toscrape.com/catalogue/category/books/travel_2/index.html`
- Click **"Run Scraper (Live)"**.
- Scrapes live via Bright Data Scraper Studio collector `c_mt3d61eq4viqmv3f4`.
- Extracted: **11 live records** with 100% Contract Quality Score on required fields.

### B. Live Self-Healing Recovery
- Trigger recovery against target DOM:
  1. Detects broken extraction rules.
  2. Parses live target DOM and ranks candidates.
  3. Discovers replacement selectors dynamically (`h3 a`, `.price_color`, `.instock.availability` at **98% confidence**).
  4. Retries extraction and validates all **11 product records**.
  5. Displays Before ($0$) $\rightarrow$ Healing ($98\%$ Conf) $\rightarrow$ After ($11$ Records Verified).
- Subsequent **"Run Scraper"** executions operate normally with the healed configuration.

### C. Controlled Failure Simulation
- Click **"Simulate Failure (Controlled Demo)"** to inject a controlled fault into active extraction selectors.
- *Note: This mode is a deterministic local testbed designed for repeatable demonstrations and is not presented as proof of live adaptability.*

---

## 7. Verified Results

Latest verified results from the test suite and live system:

- **Automated Tests**: **82 collected | 81 passed | 1 skipped | 0 failed**
- **Frontend Build**: Production bundle compiled in **7.14s with 0 errors**
- **Live Extraction**: **11 valid records** extracted from Books to Scrape travel catalog
- **Live Recovery Verification**: `verified = True`, `repaired = True`, `overall_status = "FULLY HEALED"`
- **Recovery Confidence**: **0.98 (98%)** in live dynamic verification
- **Contract Quality Score**: **100%** on required fields (`title`, `price`, `stock_status`)
- **Safe Failure Enforcement**: Verified on non-e-commerce and ambiguous DOM fixtures
- **Security Check**: 0 hardcoded tokens or secrets in source code or git history

---

## 8. Data Integrity & Contract Specifications

ScrapeGuard maintains a strict separation between required contract fields and optional metadata:

| Field | Contract Requirement | Behavior When Present | Behavior When Missing |
|---|---|---|---|
| **`title`** | **Required** | Normalized product title string | Triggers validation failure & self-healing |
| **`price`** | **Required** | Normalized price string (e.g. `$45.17`) | Triggers validation failure & self-healing |
| **`stock_status`** | **Required** | Normalized stock label (e.g. `'In Stock'`) | Triggers validation failure & self-healing |
| **`rating`** | *Optional* | Extracted float/string review score | Displays `'—'` cleanly |
| **`category`** | *Optional* | Extracted from DOM breadcrumbs/heading | Displays `'—'` (never fabricates `'General'`) |
| **`product_id`** | *Optional* | Extracted from SKU attributes/link slug | Displays `'—'` (never fabricates `'rec_N'`) |
| **`product_url`** | *Optional* | Canonical product link | Displays `'—'` |

---

## 9. Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Dashboard                       │
│           React 18 + Vite + Vanilla CSS System              │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP REST API
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend Engine                    │
│   • ScraperService (Execution & State Management)           │
│   • Normalizer (Canonical ProductRecord Normalization)      │
│   • Validator (Pydantic v2 Schema Enforcement)              │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐┌─────────────────────────────┐
│    Bright Data Client        ││    Self-Healing Engine      │
│  • Scraper Studio DCA        ││  • FailureDetector          │
│  • Web Unlocker Fetcher      ││  • DOMAnalyzer (Heuristics) │
│  • Token Sanitization        ││  • SelectorRepair (Gate)    │
└──────────────┬───────────────┘│  • HealingValidator         │
               │                └─────────────────────────────┘
               ▼
┌──────────────────────────────┐
│        Target Website        │
│   (e.g. Books to Scrape)     │
└──────────────────────────────┘
```

---

## 10. Tech Stack

- **Backend**: Python 3.11, FastAPI, Pydantic v2, HTTPX, BeautifulSoup4, Uvicorn
- **Frontend**: React 18, Vite, Lucide React, Vanilla CSS Design System
- **Scraping Infrastructure**: Bright Data Scraper Studio (`c_mt3d61eq4viqmv3f4`), Bright Data Web Unlocker
- **Testing**: Pytest, Pytest-AnyIO, Unittest
- **Tooling**: Git, Node.js, npm

---

## 11. Project Structure

```text
Scrape-Verse-IndiScrapers/
├── backend/
│   ├── automation/            # Self-healing orchestration module
│   │   ├── dom_analyzer.py    # Structural DOM inspection & candidate scoring
│   │   ├── failure_detector.py # Extraction failure & schema violation detection
│   │   ├── healing_manager.py # Multi-field recovery loop & quality metrics
│   │   ├── models.py          # Healing telemetry & candidate data models
│   │   ├── router.py          # FastAPI endpoints for recovery & simulation
│   │   ├── selector_repair.py # Candidate ranking & confidence safety gate
│   │   └── validator.py       # Post-healing validation engine
│   ├── scraper/               # Data collection & normalization module
│   │   ├── brightdata_client.py # Bright Data Scraper Studio & Web Unlocker client
│   │   ├── config.py          # Pydantic settings & environment configuration
│   │   ├── dom_fetcher.py     # Live DOM acquisition with token masking
│   │   ├── mock_client.py     # Local 42-record mock catalog client
│   │   ├── models.py          # ProductRecord and ScrapeResult schemas
│   │   ├── normalizer.py      # Field normalization & cleaning
│   │   ├── service.py         # Primary scraper interface
│   │   ├── state.py           # Runtime extraction configuration state
│   │   └── validator.py       # Pydantic schema validation
│   └── main.py                # FastAPI application entry point
├── frontend/                  # React + Vite dashboard
│   ├── src/
│   │   ├── components/        # UI components (ScraperCard, UnifiedDataRepairPanel, etc.)
│   │   ├── services/          # API client service
│   │   ├── App.jsx            # Main dashboard controller
│   │   └── App.css            # Custom Vanilla CSS styling
│   ├── index.html             # Application HTML shell
│   └── package.json           # Frontend dependencies
├── mock-site/                 # Offline 42-product catalog fixture
│   └── index.html
├── tests/                     # Automated test suite (82 test cases)
│   ├── test_automation.py     # Dynamic DOM analysis & attack suite tests
│   ├── test_dom_fetcher.py    # DOM acquisition & token masking tests
│   ├── test_live_brightdata.py# Optional live Bright Data integration test
│   └── test_scraper.py        # Normalizer, validator, and edge-case tests
├── requirements.txt           # Python dependencies
└── README.md                  # Project documentation
```

---

## 12. Getting Started

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: 18.0 or higher with npm

### 1. Clone Repository & Setup Backend
```bash
# Clone the repository
git clone https://github.com/NitishAwesome/Scrape-Verse-IndiScrapers.git
cd Scrape-Verse-IndiScrapers

# Install Python dependencies
pip install -r requirements.txt

# Start FastAPI backend (port 8000)
python -m uvicorn backend.main:app --port 8000 --reload
```

### 2. Setup & Launch Frontend Dashboard
```bash
# In a separate terminal window:
cd frontend
npm install
npm run dev
```

Open **`http://localhost:5173`** in your browser.

### 3. Environment Variables (Optional for Live Bright Data)
Create a `.env` file in the project root to configure live Bright Data extraction:
```bash
# .env configuration
SCRAPER_MODE=brightdata                  # 'brightdata' or 'mock'
BRIGHTDATA_API_TOKEN=your_token_here     # API token (kept private, never committed)
BRIGHTDATA_COLLECTOR_ID=c_mt3d61eq4viqmv3f4
BRIGHTDATA_TIMEOUT_SECONDS=90.0
MAX_HEALING_ATTEMPTS=10
CONFIDENCE_THRESHOLD=0.75
```
*If `BRIGHTDATA_API_TOKEN` is not provided, set `SCRAPER_MODE=mock` to run offline against the local 42-product catalog fixture.*

---

## 13. Testing

Execute the complete automated test suite covering unseen DOMs, attack scenarios, schema validation, and token isolation:

```bash
python -m pytest -v
```

### Test Suite Coverage (82 Test Cases)
- **Unseen DOM Structures**: Heuristic candidate discovery across novel markup with 0 prior selectors.
- **Partial & Multi-Field Failures**: Simultaneous repair across titles, prices, and stock statuses.
- **Ambiguous & Empty DOMs**: Enforces safe failure on low-confidence or non-catalog pages.
- **Malformed & Wrong Data Types**: Rejects non-numeric prices and invalid stock labels.
- **Table-Based Layouts**: Extracts and heals tabular product catalogs.
- **Retry Boundaries**: Verifies bounded loop ceiling (`MAX_HEALING_ATTEMPTS=10`).
- **Token Masking & Security**: Ensures API tokens are never leaked in logs or error traces.
- **Data Integrity**: Proves missing optional metadata remains `None` without fabricated defaults.

---

## 14. Safety & Failure Handling

ScrapeGuard enforces explicit reliability boundaries:

- **Low-Confidence Rejection**: If candidate selectors score $< 0.75$, the engine triggers a `SAFE_FAILURE` state rather than guessing.
- **Unsupported Structures**: Non-conforming HTML structures (e.g. blog posts or error pages) are classified as `unsupported`.
- **Bounded Retries**: Healing attempts are strictly bounded by `MAX_HEALING_ATTEMPTS` to prevent infinite loops.
- **Credential Protection**: `BRIGHTDATA_API_TOKEN` is masked in all logs (`c748...f0f8`) and excluded from API responses.

### Known Limitations
- **Canvas / WebGL / Shadow DOM**: Elements rendered strictly within HTML5 Canvas or closed Shadow DOMs cannot be resolved via standard CSS traversal.
- **Authentication & Paywalls**: Pages requiring multi-step OAuth or session logins require upstream credential injection.
- **Insufficient Semantic Context**: Obfuscated single-letter classes without structural headings or nearby currency regexes trigger the safe failure gate.

---

## 15. Controlled Demo vs. Live System

| Mode | Purpose | Target Source | Selectors Used |
|---|---|---|---|
| **Live Extraction** | Real public website extraction | `https://books.toscrape.com/...` | Live Bright Data Collector |
| **Live Self-Healing** | Real dynamic recovery pipeline | Target HTML via Web Unlocker / HTTP | Dynamically discovered via DOM heuristics |
| **Controlled Fault Simulation** | Deterministic local testing | `mock-site/index.html` fixture | Controlled fault injection testbed |

---

## 16. AI & Development Resources Used

In accordance with the hackathon guidelines, AI coding assistance was leveraged transparently during the development of ScrapeGuard:

* **Google Antigravity**: Used as the primary AI coding assistant for project scaffolding, test generation, edge-case analysis, architectural review, and documentation formatting.
* **ChatGPT**: Utilized for brainstorming project concepts, drafting and refining public build logs (LinkedIn updates), and shaping user-facing documentation and video script outlines.
* **Development Workflow**: All AI-suggested implementations, DOM heuristics, test suites, and frontend components were reviewed, debugged, and verified through automated tests (`pytest`, `npm run build`) and live browser sessions.

*All system architecture, safety gating logic, Pydantic contracts, and Bright Data integration were designed, tested, and validated as part of the development process.*

---

## 17. Resources & References

- **Hackathon**: [Into the Scrape-Verse — WeMakeDevs](https://www.wemakedevs.org/hackathons/scrape-verse)
- **Bright Data**: [Bright Data Scraper Studio Documentation](https://docs.brightdata.com/)
- **Bright Data Web Unlocker**: [Web Unlocker API Guide](https://brightdata.com/products/web-unlocker)
- **Backend Framework**: [FastAPI Documentation](https://fastapi.tiangolo.com/)
- **Validation**: [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- **Frontend Tooling**: [Vite Documentation](https://vitejs.dev/) & [React Documentation](https://react.dev/)

---

## 18. Learnings

- **Self-healing requires evidence, not guessing**: An automated repair system must have a strict safety gate ($\ge 0.75$) to halt safely when evidence is weak.
- **"Repaired" is not "Verified"**: Selector discovery is merely a hypothesis until downstream extraction passes strict schema validation.
- **Deterministic tests prevent regressions**: Building attack test suites against unseen DOMs ensures resilience against unexpected real-world mutations.
- **Real data integrity matters**: The UI must display genuine extracted attributes without substituting missing fields with fabricated placeholders.

---

## 19. Limitations & Future Improvements

- **JavaScript SPA Pre-rendering**: Expand upstream rendering hooks for complex multi-step single-page applications.
- **Extended Field Schemas**: Broaden heuristic coverage to support additional e-commerce attributes (e.g. author, ISBN, dimensions).
- **Scheduled Health Checks**: Introduce cron-based periodic extraction monitoring with automated webhook notifications.
- **Persistent Repair History**: Store selector repair audits in a durable database for long-term telemetry trends.

---

## 20. Hackathon Information

- **Event**: Into the Scrape-Verse Hackathon
- **Organized by**: [WeMakeDevs](https://wemakedevs.org/)
- **Sponsored by**: [Bright Data](https://brightdata.com/)
- **Dates**: August 17–23, 2026

---

## 21. Author

**Nitish Gupta**  
*Built independently for the Into the Scrape-Verse Hackathon.*
