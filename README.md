# ScrapeVerse

> **ScrapeVerse maintains configured web extraction pipelines when target website structures change.**

An autonomous, self-healing web scraping orchestration platform powered by Bright Data collection infrastructure, automated DOM telemetry, multi-field selector repair, and schema validation.

---

## The Problem

Traditional web scrapers rely on fixed CSS selectors and static DOM assumptions. When target websites update their frontend layout, redesign product cards, or modify class names, extraction rules immediately fail. This leads to silent data pipeline failures, incomplete datasets, and hours of manual engineering time spent diagnosing DOM changes and updating code.

---

## Our Solution & Innovation

ScrapeVerse introduces a robust, resilient self-healing orchestration layer around web data collection:

1. **Collect Structured Web Data**: Connects to external collection infrastructure (Bright Data) or offline local mock scrapers.
2. **Normalize Extracted Data**: Canonicalizes fields (`ProductRecord`) including title, price, stock status, rating, category, URL, and product ID.
3. **Validate Schemas**: Verifies records against strict Pydantic v2 schemas and validation rules.
4. **Detect Failures**: Identifies broken selectors, missing fields, or empty responses across multi-record datasets.
5. **Analyze Changed DOM**: Analyzes structural HTML trees, element tags, classes, and semantic heuristics.
6. **Unified Multi-Field Selector Repair**: Repairs multiple broken extraction rules simultaneously in one unified healing cycle.
7. **Bounded Retries**: Safely retries extraction within a configurable retry limit (`MAX_HEALING_ATTEMPTS=10`).
8. **Validate Recovered Dataset**: Re-normalizes and validates 100% of recovered records before delivering them downstream.
9. **Dashboard Visualization**: Provides real-time pipeline monitoring and audit telemetry.

---

## Architectural Separation: Bright Data vs ScrapeVerse

| Component | Responsibility | Role in Pipeline |
|---|---|---|
| **Bright Data** | External Web-Data Collection Infrastructure | Accesses target websites, handles rotating proxies & anti-bot protection, navigates pages, and delivers structured JSON output via Scraper Studio / Data Collector API (`/dca/trigger` & `/dca/get_result`). |
| **ScrapeVerse** | Self-Healing Orchestration & Validation Layer | Triggers collection, normalizes records, monitors extraction health, detects failures, analyzes mutated DOMs, synthesizes multi-field selector repairs, executes bounded retries, validates recovered datasets, and visualizes the process. |

*Note: ScrapeVerse does not claim Bright Data's infrastructure as our innovation. Our innovation is the autonomous monitoring, failure detection, DOM analysis, multi-field repair, bounded retry, and validation orchestration around web data extraction.*

---

## Architecture & Data Flow

```text
Target Website / E-Commerce Catalog (42 Products)
              │
              ▼
┌────────────────────────────────────────────────────────┐
│             Data Collection Infrastructure             │
│   • Bright Data DCA Client (Async Trigger & Polling)   │
│   • Mock Scraper Client (Deterministic Local Mode)     │
└──────────────────────────┬─────────────────────────────┘
                           │ Raw Payload
                           ▼
┌────────────────────────────────────────────────────────┐
│           Normalization & Validation Layer             │
│   • Canonical ProductRecord Normalizer                 │
│   • Pydantic v2 Schema & Required Fields Validator     │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
       [Data Valid]                [Data Broken / Failures Detected]
             │                                   │
             ▼                                   ▼
┌──────────────────────────┐       ┌─────────────────────────────────────┐
│  Healthy Dataset Output  │       │  Self-Healing Orchestration Engine  │
│  (42 Valid Records)      │       │  1. FailureDetector (Map Failures)  │
└──────────────────────────┘       │  2. DOMAnalyzer (Score Candidates)  │
                                   │  3. SelectorRepair (Unified Matrix) │
                                   │  4. Bounded Retry Loop (Max 10)     │
                                   │  5. HealingValidator (Verify All)   │
                                   └──────────────────┬──────────────────┘
                                                      │
                                                      ▼
                                   ┌─────────────────────────────────────┐
                                   │  Restored Full Dataset & Matrix     │
                                   │  (42 Records Recovered & Validated) │
                                   └─────────────────────────────────────┘
```

---

## Local Mock Mode

ScrapeVerse includes a built-in mock scraper reading `mock-site/index.html` containing **42 realistic e-commerce products** across multiple categories (Mice, Keyboards, Monitors, Audio, Streaming, Storage, Accessories).

Mock mode provides:
- Deterministic offline local development
- Zero-token test execution and CI/CD validation
- Reliable demonstration without requiring live API keys
- Direct structural emulation of Bright Data's output contract

---

## Unified Multi-Field Self-Healing Demo

ScrapeVerse supports a realistic website redesign scenario affecting multiple extraction rules simultaneously:

### Original Target Selectors:
- Title: `.product-title`
- Price: `.product-price`
- Stock Status: `.product-status`

### Target Website Mutation:
- `.product-title` $\rightarrow$ `.product-name`
- `.product-price` $\rightarrow$ `.current-price`
- `.product-status` $\rightarrow$ `.availability`

```text
MULTI-FIELD REPAIR MATRIX
Field             Broken Selector      Repaired Selector    Confidence    Status
─────────────────────────────────────────────────────────────────────────────────
Product Title     .product-title   →   .product-name        100%          HEALED
Product Price     .product-price   →   .current-price       100%          HEALED
Stock Status      .product-status  →   .availability        100%          HEALED
```

### Result:
- **42 records before mutation**
- **3 extraction rules affected**
- **3 rules repaired in ONE unified healing cycle**
- **42 records recovered and validated**
- **Recovery Status: SUCCESS**

---

## Bounded Retries & Configuration

To prevent infinite loops and runaway requests, ScrapeVerse strictly bounds all self-healing retry cycles.

- **Default Retry Limit**: `MAX_HEALING_ATTEMPTS=10`
- **Configurable via Environment Variables**:
  ```bash
  # .env configuration
  SCRAPER_MODE=mock                  # 'mock' or 'brightdata'
  MAX_HEALING_ATTEMPTS=10            # Bounded retry ceiling
  BRIGHTDATA_API_TOKEN=your_token    # Required for brightdata mode
  BRIGHTDATA_COLLECTOR_ID=c_xxx      # Required for brightdata mode
  BRIGHTDATA_TIMEOUT_SECONDS=30.0    # Async polling timeout
  ```

---

## How ScrapeVerse Self-Heals

ScrapeVerse executes a 7-step autonomous reliability cycle:

1. **Detect**: Identifies broken selectors, missing fields, or empty responses from extraction runs.
2. **Analyze**: Fetches the live or mutated target DOM and parses tag hierarchy, semantic attributes, currency symbols, and text structure.
3. **Rank**: Generates ranked candidate selectors per broken field with structured heuristic confidence scores.
4. **Repair**: Selects the highest-confidence candidate ($\ge 0.75$ safety threshold) or triggers a safe failure if DOM evidence is insufficient.
5. **Retry**: Re-executes the extraction engine with synthesized selector updates.
6. **Validate**: Verifies the recovered records against strict Pydantic data contracts (`ProductRecord`).
7. **Verify**: Computes deterministic data quality metrics (field completeness and valid record ratio) and updates the recovery audit.

---

## Evidence-Based Recovery & Safe Failure (No False Claims)

> [!IMPORTANT]
> **ScrapeVerse does NOT claim that it can heal every website.**
> True autonomous reliability requires knowing when to halt safely rather than guessing incorrect selectors.

Failures are classified into distinct tiers:
- **`recoverable`**: High-confidence replacement candidate identified ($\ge 0.75$) and validated.
- **`partially_recoverable`**: Subset of broken fields recovered; others flagged.
- **`ambiguous_unsafe`**: Candidate confidence below safety gate ($< 0.75$) — halts extraction to prevent dirty data ingestion.
- **`unsupported`**: Target DOM structure does not conform to expected e-commerce contracts.

---

## Real Architecture vs. Controlled Demo

| Feature | Real Production Flow | Controlled Demo Mode |
|---|---|---|
| **Data Collection** | Live Bright Data Scraper Studio Collector (`c_mt3d61eq4viqmv3f4`) | Mock E-Commerce Catalog (`mock-site/index.html`) |
| **DOM Fetching** | Live HTTP extraction of target URL | Local mutated HTML fixture |
| **DOM Analysis** | Live BeautifulSoup structural parsing | Deterministic multi-mutation testbed |
| **Candidate Ranking** | Semantic heuristic scoring & ranking | Evaluates candidates against mutated DOM |
| **Confidence Safety Gate** | Enforced ($0.75$ threshold) | Enforced ($0.75$ threshold) |
| **Validation** | Pydantic v2 `ProductRecord` contract | Pydantic v2 `ProductRecord` contract |
| **Trigger in UI** | Target URL + "Run Scraper" / "Self-Healing" | "Simulate Failure (Controlled Demo)" button |

---

## Judge Demo Flow

1. **Live Healthy Scrape**:
   - Target URL: `https://books.toscrape.com/catalogue/category/books/travel_2/index.html`
   - Click **"Run Scraper"** $\rightarrow$ Scrapes live via Bright Data Scraper Studio.
   - Status: **HEALTHY**, all items normalized and displayed.
2. **Simulate Controlled Failure**:
   - Click **"Simulate Failure (Controlled Demo)"**.
   - Selectors break (`.product-title` $\rightarrow$ `.product-name`, `.product-price` $\rightarrow$ `.current-price`, `.product-status` $\rightarrow$ `.availability`).
   - UI status: **FAILED**, 0 records extracted.
3. **Trigger Self-Healing Recovery**:
   - Click **"Self-Healing Recovery"**.
   - Watch the recovery timeline: Failure Detected $\rightarrow$ DOM Analysis $\rightarrow$ Ranked Candidates $\rightarrow$ Repair $\rightarrow$ Retried $\rightarrow$ Validated.
   - UI displays Before $\rightarrow$ Healing $\rightarrow$ After audit, Data Quality Breakdown, and Ranked Candidates.
4. **Live Target Recovery**:
   - Enter `https://books.toscrape.com/catalogue/category/books/travel_2/index.html` and trigger recovery endpoint:
     `POST /api/healing/recover?url=...`
   - ScrapeVerse fetches the live DOM, identifies selectors, extracts books, validates records, and returns full recovery telemetry.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service health and engine status |
| `GET` | `/api/scrape` | Execute scraper pipeline with target URL |
| `GET` | `/api/scrape?fail=true` | Trigger simulated failure for telemetry inspection |
| `GET` | `/api/healing/status` | System status, mode, and retry limit (`MAX_HEALING_ATTEMPTS`) |
| `POST` | `/api/healing/recover` | Execute autonomous self-healing & return recovered dataset |
| `POST` | `/api/healing/multi-demo` | Multi-selector self-healing demo endpoint |
| `POST` | `/api/healing/test` | Single-mutation self-healing test endpoint |

---

## Quickstart & Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 1. Backend Setup
```bash
# Clone repository
git clone https://github.com/NitishAwesome/Scrape-Verse-IndiScrapers.git
cd Scrape-Verse-IndiScrapers

# Install Python dependencies
pip install -r requirements.txt

# Start FastAPI backend (port 8000)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Dashboard Setup
```bash
# In a new terminal:
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## Running Tests

Run the complete automated test suite:
```bash
python -m pytest
```
