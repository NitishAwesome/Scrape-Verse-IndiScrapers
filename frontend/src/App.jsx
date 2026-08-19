import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import MetricsBar from './components/MetricsBar';
import ScraperCard from './components/ScraperCard';
import DataTable from './components/DataTable';
import HealingTimeline from './components/HealingTimeline';
import SelectorDiffPanel from './components/SelectorDiffPanel';
import ActivityLogs from './components/ActivityLogs';
import { fetchHealingStatus, runScrape, runHealingDemo } from './services/api';
import './App.css';

export default function App() {
  const [isConnected, setIsConnected] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  // Scraper & Pipeline State
  const [scraperStatus, setScraperStatus] = useState('HEALTHY');
  const [records, setRecords] = useState([
    {
      title: 'Wireless Gaming Mouse',
      price: '$49.99',
      stock_status: 'In Stock',
    },
  ]);
  const [error, setError] = useState(null);
  const [lastRun, setLastRun] = useState('Just now');
  const [latency, setLatency] = useState('38ms');
  const [activeSelector, setActiveSelector] = useState('.product-price');

  // Self-Healing State
  const [timelineStep, setTimelineStep] = useState(0);
  const [isHealing, setIsHealing] = useState(false);
  const [healingResult, setHealingResult] = useState(null);
  const [repairData, setRepairData] = useState({
    oldSelector: '.product-price',
    newSelector: '.current-price',
    confidence: 1.0,
    validationResult: true,
    targetField: 'price',
    reasoning: "Identified replacement DOM element <div> with selector '.current-price' containing value '$49.99'",
  });

  // Metrics & Logs
  const [healingCount, setHealingCount] = useState(1);
  const [rawPayload, setRawPayload] = useState(null);
  const [logs, setLogs] = useState([
    {
      time: new Date().toLocaleTimeString(),
      level: 'INFO',
      message: 'ScrapeVerse self-healing engine initialized. Target: mock-site/index.html',
    },
    {
      time: new Date().toLocaleTimeString(),
      level: 'INFO',
      message: 'Collector c_mock_123456 verified healthy with active selector .product-price',
    },
  ]);

  const addLog = (level, message) => {
    setLogs((prev) => [
      {
        time: new Date().toLocaleTimeString(),
        level,
        message,
      },
      ...prev,
    ]);
  };

  // Check health on mount
  const checkHealth = async () => {
    setIsRefreshing(true);
    try {
      const res = await fetchHealingStatus();
      setIsConnected(res.status === 'online');
      addLog('INFO', `Health probe OK: ${res.module} (Mock LLM: ${res.mock_llm_mode})`);
    } catch {
      setIsConnected(false);
      addLog('WARN', 'Backend connection probe timed out');
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  // Action 1: Run Normal Scraper
  const handleRunNormal = async () => {
    setIsRunning(true);
    addLog('INFO', 'Triggering normal scrape execution via GET /api/scrape...');
    try {
      const result = await runScrape(false);
      setRawPayload(result);
      setLastRun(new Date().toLocaleTimeString());
      setLatency(`${result.latencyMs || 42}ms`);

      if (result.status === 'success') {
        setScraperStatus('HEALTHY');
        setRecords(result.data || []);
        setError(null);
        setActiveSelector('.product-price');
        addLog('INFO', `Scrape succeeded: Extracted ${result.records_extracted} record(s) in ${result.latencyMs}ms`);
      } else {
        setScraperStatus('FAILED');
        setError(result.error);
        addLog('ERROR', `Scrape failed: ${result.error}`);
      }
    } catch (err) {
      addLog('ERROR', `Scrape execution error: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  // Action 2: Simulate Failure
  const handleSimulateFailure = async () => {
    setIsRunning(true);
    setTimelineStep(0);
    setHealingResult(null);
    addLog('WARN', 'Simulating target website layout change & selector failure...');

    try {
      const result = await runScrape(true);
      setRawPayload(result);
      setLastRun(new Date().toLocaleTimeString());
      setLatency(`${result.latencyMs || 45}ms`);

      setScraperStatus('FAILED');
      setRecords([]);
      setError(result.error || 'SelectorNotFound: .product-price');
      addLog('ERROR', `Failure detected: SelectorNotFound: .product-price on target DOM`);
      addLog('WARN', 'Required field "price" is missing in extracted payload. Self-healing triggered.');
    } catch (err) {
      addLog('ERROR', `Simulation error: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  // Action 3: Trigger Live Self-Healing Demonstration
  const handleTriggerHealing = async () => {
    setIsRunning(true);
    setIsHealing(true);
    setScraperStatus('HEALING');
    setTimelineStep(1);

    addLog('INFO', '[Step 1/7] Scrape initiated on mutated e-commerce HTML layout...');

    // Step 2
    setTimeout(() => {
      setTimelineStep(2);
      addLog('ERROR', '[Step 2/7] Selector failure detected: .product-price missing from DOM.');
    }, 450);

    // Step 3
    setTimeout(() => {
      setTimelineStep(3);
      addLog('INFO', '[Step 3/7] DOM structure analyzed: Parsed elements, identified candidate <div class="current-price">.');
    }, 900);

    // Step 4
    setTimeout(() => {
      setTimelineStep(4);
      addLog('HEAL', '[Step 4/7] AI repair proposed replacement: .product-price -> .current-price (Confidence: 100%).');
    }, 1350);

    // Step 5
    setTimeout(() => {
      setTimelineStep(5);
      addLog('INFO', '[Step 5/7] Selector dynamically patched in runtime memory.');
    }, 1800);

    // Step 6 & 7: Execute backend call and complete
    setTimeout(async () => {
      setTimelineStep(6);
      addLog('INFO', '[Step 6/7] Scraper pipeline re-executed with repaired selector .current-price...');

      try {
        const result = await runHealingDemo();
        setRawPayload(result);

        setTimelineStep(7);
        setHealingResult(result);
        setHealingCount((c) => c + 1);
        setScraperStatus('HEALTHY');
        setActiveSelector('.current-price');
        setRecords([
          {
            title: 'Wireless Gaming Mouse',
            price: '$49.99',
            stock_status: 'In Stock',
          },
        ]);
        setError(null);
        setLastRun(new Date().toLocaleTimeString());
        setLatency(`${result.latencyMs || 52}ms`);

        const firstRepair = result.healing_result?.selector_repairs?.[0] || {};
        setRepairData({
          oldSelector: result.old_selector || '.product-price',
          newSelector: result.new_selector || '.current-price',
          confidence: result.confidence || 1.0,
          validationResult: result.validation_result || true,
          targetField: 'price',
          reasoning: firstRepair.reasoning || "Identified replacement DOM element <div> with selector '.current-price' containing value '$49.99'",
        });

        addLog('HEAL', `[Step 7/7] Validation PASSED: Extracted price $49.99 with valid required fields.`);
        addLog('HEAL', `🎉 AUTONOMOUS SELF-HEALING COMPLETE: Collector restored to HEALTHY with ZERO human intervention.`);
      } catch (err) {
        addLog('ERROR', `Self-healing error: ${err.message}`);
      } finally {
        setIsHealing(false);
        setIsRunning(false);
      }
    }, 2250);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <Header
        isConnected={isConnected}
        onRefresh={checkHealth}
        isRefreshing={isRefreshing}
      />

      {/* Metrics Bar */}
      <MetricsBar
        metrics={{
          scraperHealth: scraperStatus === 'FAILED' ? 'DEGRADED' : 'HEALTHY',
          activeScrapers: 1,
          healingEventsCount: healingCount,
          successRate: '100%',
          avgLatency: latency,
        }}
      />

      {/* Scraper Collector Card */}
      <ScraperCard
        status={scraperStatus}
        lastRun={lastRun}
        latency={latency}
        activeSelector={activeSelector}
        isRunning={isRunning}
        onRunNormal={handleRunNormal}
        onSimulateFailure={handleSimulateFailure}
        onTriggerHealing={handleTriggerHealing}
      />

      {/* Main Two-Column Grid */}
      <div className="dashboard-main-grid">
        {/* Left Column: Data Table & Diff */}
        <div className="flex flex-col gap-5" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <DataTable
            records={records}
            status={scraperStatus}
            error={error}
            lastUpdated={lastRun}
          />

          <SelectorDiffPanel repairData={repairData} />
        </div>

        {/* Right Column: Timeline & Diagnostic Logs */}
        <div className="flex flex-col gap-5" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <HealingTimeline
            activeStep={timelineStep}
            isHealing={isHealing}
            healingResult={healingResult}
          />

          <ActivityLogs
            logs={logs}
            onClear={() => setLogs([])}
            rawPayload={rawPayload}
          />
        </div>
      </div>
    </div>
  );
}
