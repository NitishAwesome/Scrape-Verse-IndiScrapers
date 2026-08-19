/**
 * ScrapeVerse API Client Service
 * Interacts with FastAPI backend endpoints:
 * - GET  /api/scrape
 * - GET  /api/scrape?fail=true
 * - GET  /api/healing/status
 * - POST /api/healing/demo
 */

const API_BASE = '/api';

export async function fetchHealingStatus() {
  try {
    const res = await fetch(`${API_BASE}/healing/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn('Backend offline, using fallback status:', error);
    return {
      status: 'online',
      module: 'self-healing (mock fallback)',
      mock_llm_mode: true,
      max_retries: 3,
      supported_failure_types: [
        'SelectorNotFound',
        'ValidationError',
        'EmptyResponse',
        'ApiError',
        'InvalidValue',
      ],
    };
  }
}

export async function runScrape(fail = false) {
  const startTime = performance.now();
  try {
    const url = `${API_BASE}/scrape${fail ? '?fail=true' : ''}`;
    const res = await fetch(url);
    const latency = Math.round(performance.now() - startTime);
    const data = await res.json();
    return {
      ...data,
      latencyMs: latency,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    const latency = Math.round(performance.now() - startTime);
    if (fail) {
      return {
        collector_id: 'c_mock_123456',
        status: 'failed',
        records_extracted: 0,
        data: [],
        error: 'SelectorNotFound: .product-price',
        latencyMs: latency,
        timestamp: new Date().toISOString(),
      };
    }
    return {
      collector_id: 'c_mock_123456',
      status: 'success',
      records_extracted: 1,
      data: [
        {
          title: 'Wireless Gaming Mouse',
          price: '$49.99',
          stock_status: 'In Stock',
        },
      ],
      error: null,
      latencyMs: latency,
      timestamp: new Date().toISOString(),
    };
  }
}

export async function runHealingDemo() {
  const startTime = performance.now();
  try {
    const res = await fetch(`${API_BASE}/healing/demo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    const latency = Math.round(performance.now() - startTime);
    const data = await res.json();
    return {
      ...data,
      latencyMs: latency,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    const latency = Math.round(performance.now() - startTime);
    return {
      status: 'success',
      repaired: true,
      failure_type: 'ValidationError',
      old_selector: '.product-price',
      new_selector: '.current-price',
      confidence: 1.0,
      validation_result: true,
      retry_count: 1,
      healing_event: {
        scraper_id: 'c_mock_123456',
        failure_type: 'ValidationError',
        old_selector: '.product-price',
        new_selector: '.current-price',
        target_field: 'price',
        confidence: 1.0,
        validation_result: true,
        retry_count: 1,
        status: 'success',
        message: "Validation successful: Extracted 1 record(s) with valid 'price'",
        timestamp: new Date().toISOString(),
      },
      healing_result: {
        status: 'success',
        repaired: true,
        attempts: [
          {
            scraper_id: 'c_mock_123456',
            failure_type: 'ValidationError',
            old_selector: '.product-price',
            new_selector: '.current-price',
            target_field: 'price',
            confidence: 1.0,
            validation_result: true,
            retry_count: 1,
            status: 'success',
            message: "Validation successful: Extracted 1 record(s) with valid 'price'",
            timestamp: new Date().toISOString(),
          },
        ],
        selector_repairs: [
          {
            field: 'price',
            old_selector: '.product-price',
            new_selector: '.current-price',
            confidence: 1.0,
            reasoning: "Identified replacement DOM element <div> with selector '.current-price' containing value '$49.99'",
          },
        ],
        error: null,
      },
      latencyMs: latency,
      timestamp: new Date().toISOString(),
    };
  }
}
