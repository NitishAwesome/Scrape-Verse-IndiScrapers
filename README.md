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

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service health and engine status |
| `GET` | `/api/scrape` | Execute scraper pipeline (returns 42 normalized records) |
| `GET` | `/api/scrape?fail=true` | Trigger simulated failure for telemetry inspection |
| `GET` | `/api/healing/status` | System status, mock mode, and retry limit (`MAX_HEALING_ATTEMPTS`) |
| `POST` | `/api/healing/recover` | Execute unified multi-field self-healing & return recovered dataset |
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

Run the complete automated test suite (43 unit & integration tests):
```bash
python -m pytest
```

### Test Suite Coverage:
1. Multi-product mock extraction (42 items)
2. Complete dataset extraction & contract validation
3. Data normalization (`normalize_price`, `normalize_title`, `normalize_stock_status`, `normalize_rating`)
4. Pydantic schema validation & required fields enforcement
5. Bright Data payload response envelopes
6. Bright Data asynchronous trigger & exponential backoff polling
7. Failure detection across single and multi-record datasets
8. Multiple simultaneous selector failures
9. Multi-field selector repair proposals & confidence scoring
10. Bounded retry limit enforcement (`MAX_HEALING_ATTEMPTS`)
11. Successful multi-field dataset recovery
12. Failed recovery handling on unrecoverable markup
13. FastAPI REST API endpoints
14. Frontend / Backend data contract integrity

---

## Demonstration Procedure

1. **Launch Platform**: Start FastAPI backend and Vite frontend. Open `http://localhost:5173`.
2. **Inspect Pipeline Banner**: View the top 5-stage pipeline: `TARGET WEBSITE` $\rightarrow$ `SCRAPING` $\rightarrow$ `EXTRACTED DATA` $\rightarrow$ `VALIDATION` $\rightarrow$ `HEALTH STATUS`.
3. **Run Healthy Scrape**: Click **"Run Normal Scraper"**. All 42 products are extracted, normalized, validated, and rendered in the searchable catalog. Status is **HEALTHY**.
4. **Simulate Website Mutation**: Click **"Simulate Failure"**. The scraper detects 3 broken extraction rules, 0 records extracted, and marks status as **SELECTOR BROKEN**.
5. **Execute Unified Self-Healing**: Click **"Self-Healing Recovery"**. Watch the 7-step visual timeline:
   - DOM structure analyzed
   - Multi-field repair matrix generated (`.product-title` $\rightarrow$ `.product-name`, `.product-price` $\rightarrow$ `.current-price`, `.product-status` $\rightarrow$ `.availability`)
   - Scraper retried with repaired selectors
   - Complete 42-product dataset restored and validated
   - Health status returned to **HEALTHY**
6. **Inspect Audit Telemetry**: Click **"Inspect JSON"** or switch to the **"Repair Matrix"** tab to review the complete diagnostic payload and AI confidence scores.
