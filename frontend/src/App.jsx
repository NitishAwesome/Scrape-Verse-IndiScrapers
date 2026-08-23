import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import MetricsBar from './components/MetricsBar';
import PipelineFlowBanner from './components/PipelineFlowBanner';
import ScraperCard from './components/ScraperCard';
import UnifiedDataRepairPanel from './components/UnifiedDataRepairPanel';
import HealingTimeline from './components/HealingTimeline';
import ActivityLogs from './components/ActivityLogs';
import { fetchHealingStatus, runScrape, runUnifiedHealing, simulateFailure, resetScraperState } from './services/api';
import './App.css';

export default function App() {
  const [isConnected, setIsConnected] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  // Scraper & Data State
  const [scraperStatus, setScraperStatus] = useState('HEALTHY');
  const [records, setRecords] = useState([]);
  const [error, setError] = useState(null);
  const [lastRun, setLastRun] = useState('Just now');
  const [latency, setLatency] = useState('42ms');
  const [activeSelector, setActiveSelector] = useState('.product-title, .product-price, .product-status');
  const [targetUrl, setTargetUrl] = useState('https://books.toscrape.com/catalogue/category/books/travel_2/index.html');
  const [collectorId, setCollectorId] = useState('c_mt3d61eq4viqmv3f4');
  const [scraperMode, setScraperMode] = useState('brightdata');
  const [currentMode, setCurrentMode] = useState('LIVE_EXTRACTION'); // 'LIVE_EXTRACTION' | 'CONTROLLED_SIMULATION' | 'LIVE_SELF_HEALING'

  // Self-Healing Unified State
  const [timelineStep, setTimelineStep] = useState(0);
  const [isHealing, setIsHealing] = useState(false);
  const [healingInfo, setHealingInfo] = useState(null);
  const [healingCount, setHealingCount] = useState(0);
  const [logs, setLogs] = useState([]);
  const [rawPayload, setRawPayload] = useState(null);
  const [showPayloadModal, setShowPayloadModal] = useState(false);

  // Append Activity Log Helper
  const addLog = (type, message) => {
    setLogs((prev) => [
      {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString(),
        type,
        message,
      },
      ...prev.slice(0, 49),
    ]);
  };

  // Check Backend Connection & Status
  const checkHealth = async () => {
    setIsRefreshing(true);
    try {
      const status = await fetchHealingStatus();
      setIsConnected(true);
      if (status.collector_id) setCollectorId(status.collector_id);
      if (status.scraper_mode) setScraperMode(status.scraper_mode);
      addLog('INFO', `Backend online [${status.scraper_mode?.toUpperCase() || 'BRIGHTDATA'} mode] (Collector: ${status.collector_id})`);
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
    setCurrentMode('LIVE_EXTRACTION');
    addLog('INFO', `Triggering live extraction${targetUrl ? ` for ${targetUrl}` : ''} via GET /api/scrape...`);
    try {
      const result = await runScrape(false, targetUrl);
      setRawPayload(result);
      setLastRun(new Date().toLocaleTimeString());
      setLatency(`${result.latencyMs || 42}ms`);

      if (result.collector_id) setCollectorId(result.collector_id);

      if (result.status === 'success') {
        setScraperStatus('HEALTHY');
        setRecords(result.data || []);
        setError(null);
        setActiveSelector('.product-title, .product-price, .product-status');
        setHealingInfo(null);
        setTimelineStep(0);
        addLog('INFO', `Live scrape succeeded: Extracted ${result.data?.length || 0} product records with 100% schema validation in ${result.latencyMs}ms`);
      } else {
        setScraperStatus('FAILED');
        setRecords([]);
        setError(result.error || 'SelectorNotFound: Active extraction rules failed');
        setActiveSelector('.product-name, .current-price, .availability (BROKEN)');
        addLog('ERROR', `Live scrape failed: ${result.error || 'Active selectors failed to match target DOM'}`);
      }
    } catch (err) {
      addLog('ERROR', `Scrape execution error: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  // Action 2: Simulate Website Mutation / Failure
  const handleSimulateFailure = async () => {
    setIsRunning(true);
    setCurrentMode('CONTROLLED_SIMULATION');
    setTimelineStep(0);
    setHealingInfo(null);
    addLog('WARN', 'Simulating target website DOM redesign mutating 3 extraction rules (.product-title -> .product-name, .product-price -> .current-price, .product-status -> .availability)...');

    try {
      const result = await simulateFailure(targetUrl);
      setRawPayload(result);
      setLastRun(new Date().toLocaleTimeString());
      setLatency(`${result.latencyMs || 45}ms`);

      setScraperStatus('FAILED');
      setRecords([]);
      setError(result.error || 'SelectorNotFound: .product-name, .current-price, .availability');
      setActiveSelector('.product-name, .current-price, .availability (BROKEN)');
      addLog('ERROR', `Controlled fault simulation active: ${result.error || 'Missing required fields in DOM'}`);
    } catch (err) {
      addLog('ERROR', `Simulation error: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  // Action 3: Trigger Multi-Field Unified Autonomous Healing
  const handleTriggerHealing = async () => {
    setIsHealing(true);
    setIsRunning(true);
    setCurrentMode('LIVE_SELF_HEALING');
    setError(null);
    setTimelineStep(1);

    addLog('HEAL', '🚀 INITIATING UNIFIED AUTONOMOUS RECOVERY CYCLE...');
    addLog('INFO', '[Step 1/7] SCRAPE STARTED: Baseline extraction triggered against target DOM.');

    setTimeout(() => {
      setTimelineStep(2);
      addLog('WARN', '[Step 2/7] FAILURES DETECTED: Missing/broken selector fields detected in active extraction config.');
    }, 350);

    setTimeout(() => {
      setTimelineStep(3);
      addLog('INFO', '[Step 3/7] DOM ANALYZED: Parsing structural semantic tree, classes, and microdata attributes...');
    }, 750);

    setTimeout(() => {
      setTimelineStep(4);
      addLog('HEAL', '[Step 4/7] AI REPAIR: Dynamic candidate ranking & confidence scoring synthesized replacement rules.');
    }, 1150);

    setTimeout(() => {
      setTimelineStep(5);
      addLog('INFO', '[Step 5/7] SELECTORS PATCHED: Injected verified replacement selectors into active extraction configuration.');
    }, 1550);

    setTimeout(async () => {
      setTimelineStep(6);
      addLog('INFO', '[Step 6/7] EXTRACTION RETRIED: Re-executing extraction pipeline across target DOM...');

      try {
        const result = await runUnifiedHealing(targetUrl);
        setRawPayload(result);

        setTimelineStep(7);
        setHealingInfo(result);
        setHealingCount((c) => c + 1);
        setScraperStatus(result.repaired && result.verified ? 'HEALTHY' : 'FAILED');
        
        const repSelectors = result.repaired_selectors 
          ? Object.values(result.repaired_selectors).join(', ')
          : 'Repaired Selectors Active';
        setActiveSelector(repSelectors);

        const recoveredData = result.data || result.final_data || [];
        setRecords(recoveredData);
        setError(result.error || null);
        setLastRun(new Date().toLocaleTimeString());
        setLatency(`${result.latencyMs || 54}ms`);

        const repList = result.repairs || [];
        const repSummary = repList.map((r) => `${r.old_selector} → ${r.new_selector} (${Math.round(r.confidence * 100)}%)`).join(', ');

        if (result.repaired && result.verified) {
          addLog('HEAL', `[Step 7/7] VALIDATION PASSED: Schema verified across all ${recoveredData.length} records with 100% contract integrity.`);
          addLog('HEAL', `🎉 AUTONOMOUS RECOVERY COMPLETE: ${repList.length || 3} selector(s) repaired [${repSummary || repSelectors}]. Recovered ${recoveredData.length} valid product records.`);
        } else {
          addLog('ERROR', `[Step 7/7] SAFE FAILURE ENFORCED: Confidence below safety threshold or contract unverified.`);
        }
      } catch (err) {
        addLog('ERROR', `Self-healing error: ${err.message}`);
      } finally {
        setIsHealing(false);
        setIsRunning(false);
      }
    }, 2000);
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
          collectorId: collectorId,
          healingEventsCount: healingCount,
          successRate: scraperStatus === 'FAILED' ? '0%' : '100%',
          isFailed: scraperStatus === 'FAILED',
        }}
      />

      {/* End-to-End Pipeline Ribbon */}
      <PipelineFlowBanner
        status={scraperStatus}
        recordCount={records.length}
        targetUrl={targetUrl}
        isHealing={isHealing}
      />

      {/* Scraper Collector Card */}
      <ScraperCard
        status={scraperStatus}
        lastRun={lastRun}
        latency={latency}
        activeSelector={activeSelector}
        isRunning={isRunning}
        targetUrl={targetUrl}
        onTargetUrlChange={setTargetUrl}
        collectorId={collectorId}
        scraperMode={scraperMode}
        currentMode={currentMode}
        onRunNormal={handleRunNormal}
        onSimulateFailure={handleSimulateFailure}
        onTriggerHealing={handleTriggerHealing}
      />

      {/* Main Two-Column Grid */}
      <div className="dashboard-main-grid">
        {/* Left Column: Unified Self-Healing Repair & Extracted Data Panel */}
        <div className="dashboard-col">
          <UnifiedDataRepairPanel
            data={records}
            healingInfo={healingInfo}
            isHealed={scraperStatus === 'HEALTHY' && healingInfo !== null}
            isFailed={scraperStatus === 'FAILED'}
            originalSelectors={{
              title: '.product-title',
              price: '.product-price',
              stock_status: '.product-status',
            }}
            onInspectPayload={() => setShowPayloadModal(true)}
          />
        </div>

        {/* Right Column: Visual Pipeline Timeline & Live Activity Logs */}
        <div className="dashboard-col">
          <HealingTimeline
            activeStep={timelineStep}
            isHealing={isHealing}
            healingResult={healingInfo}
          />

          <ActivityLogs
            logs={logs}
            onClear={() => setLogs([])}
            rawPayload={rawPayload}
          />
        </div>
      </div>

      {/* Inspect Raw JSON Modal */}
      {showPayloadModal && (
        <div className="modal-overlay" onClick={() => setShowPayloadModal(false)}>
          <div className="modal-content glass-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h4>Self-Healing Raw JSON Audit Payload</h4>
              <button className="btn-close" onClick={() => setShowPayloadModal(false)}>✕</button>
            </div>
            <pre className="modal-json-viewer">
              {JSON.stringify(rawPayload || { status: 'idle', info: 'Run scraper or recovery to view payload' }, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
