import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const tabs = [
  ["overview", "Overview"],
  ["timeline", "Timeline"],
  ["evidence", "Evidence"],
  ["actions", "Action queue"],
  ["people", "People"],
  ["notes", "Notes"],
];

const navItems = [
  ["cases", "Cases", "home"],
  ["map", "Map", "pin"],
  ["people", "People", "people"],
  ["resources", "Resources", "cube"],
  ["communications", "Communications", "message"],
  ["analytics", "Analytics", "bars"],
  ["settings", "Settings", "gear"],
];

const iconPaths = {
  home: <><path d="m3 10 9-7 9 7" /><path d="M5 9v10h14V9" /><path d="M9 19v-6h6v6" /></>,
  pin: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
  people: <><circle cx="9" cy="8" r="3" /><path d="M3 20c.6-3.4 2.5-5 6-5s5.4 1.6 6 5" /><path d="M16 5.5a3 3 0 0 1 0 5.7M17 15c2.2.4 3.4 1.7 4 4" /></>,
  cube: <><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z" /><path d="m4.5 7.8 7.5 4.4 7.5-4.4M12 12.2V21" /></>,
  message: <><path d="M4 5h16v11H8l-4 4V5Z" /><path d="M8 9h8M8 12h5" /></>,
  bars: <><path d="M5 20V10M12 20V4M19 20v-7" /><path d="M3 20h18" /></>,
  gear: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 1.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-2.6V20a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1-1.8-1.8.1-.1A1.7 1.7 0 0 0 8 15a1.7 1.7 0 0 0-1.6-1H6v-2.6h.4A1.7 1.7 0 0 0 8 10a1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.8-1.8.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2H15V5a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.8 1.8-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v2.6H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
  chevron: <path d="m9 6 6 6-6 6" />,
  arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
  back: <><path d="M19 12H5" /><path d="m11 18-6-6 6-6" /></>,
  shield: <><path d="M12 3 20 6v5c0 4.7-3.3 7.5-8 10-4.7-2.5-8-5.3-8-10V6l8-3Z" /><path d="m9 12 2 2 4-5" /></>,
  pulse: <path d="M3 12h4l2.2-5 4.2 10 2.2-5H21" />,
  document: <><path d="M6 3h8l4 4v14H6V3Z" /><path d="M14 3v5h4M9 12h6M9 16h6" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  clock: <><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3 2" /></>,
  warning: <><path d="m12 4 8 15H4L12 4Z" /><path d="M12 9v4M12 16h.01" /></>,
  lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  upload: <><path d="M12 16V4M8 8l4-4 4 4" /><path d="M5 14v5h14v-5" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.8-3L3 11" /><path d="M3 5v6h6M4 13a8 8 0 0 0 14.8 3L21 13" /><path d="M21 19v-6h-6" /></>,
  eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>,
  x: <><path d="m6 6 12 12M18 6 6 18" /></>,
};

function Icon({ name, size = 18, strokeWidth = 1.8 }) {
  return (
    <svg aria-hidden="true" className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {iconPaths[name] || iconPaths.document}
    </svg>
  );
}

function StatusPill({ status, children }) {
  const className = `status-pill status-${status}`;
  return <span className={className}><span className="status-dot" />{children}</span>;
}

function TypeMark({ kind }) {
  const labels = { official_notice: "NOTICE", agreement: "LEASE", photo: "PHOTO", email: "EMAIL", estimate: "PDF", connector_response: "REPLY", upload: "FILE" };
  return <span className={`type-mark type-${kind}`}>{labels[kind] || "FILE"}</span>;
}

function formatActionStatus(status) {
  return { needs_approval: "Needs approval", completed: "Completed", queued: "In queue", in_progress: "Working", blocked: "Blocked" }[status] || status;
}

function App() {
  const [caseData, setCaseData] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [approvalAction, setApprovalAction] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);

  const loadCase = async () => {
    const response = await fetch("/api/case");
    if (!response.ok) throw new Error("Could not load the case");
    setCaseData(await response.json());
    setLoadError(null);
  };

  useEffect(() => {
    loadCase().catch((error) => {
      setLoadError(error.message);
      setNotice({ type: "error", text: error.message });
    });
  }, []);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const actionCounts = useMemo(() => {
    if (!caseData) return { approval: 0, completed: 0, blocked: 0 };
    return caseData.actions.reduce((counts, action) => {
      if (action.status === "needs_approval") counts.approval += 1;
      if (action.status === "completed") counts.completed += 1;
      if (action.status === "blocked") counts.blocked += 1;
      return counts;
    }, { approval: 0, completed: 0, blocked: 0 });
  }, [caseData]);

  const runPlan = async () => {
    setBusy(true);
    try {
      const response = await fetch(`/api/cases/${caseData.id}/run`, { method: "POST" });
      if (!response.ok) throw new Error("The recovery check could not finish");
      setCaseData(await response.json());
      setNotice({ type: "success", text: "Recovery plan re-checked. No external action was sent." });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  };

  const resetDemo = async () => {
    setBusy(true);
    try {
      const response = await fetch(`/api/cases/${caseData.id}/reset`, { method: "POST" });
      setCaseData(await response.json());
      setSelectedEvidence(null);
      setApprovalAction(null);
      setNotice({ type: "success", text: "Synthetic case restored to its starting point." });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  };

  const approve = async (reviewer, note) => {
    setBusy(true);
    try {
      const response = await fetch(`/api/cases/${caseData.id}/actions/${approvalAction.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewer, note }),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Approval could not be recorded");
      }
      setCaseData(await response.json());
      setApprovalAction(null);
      setNotice({ type: "success", text: "Approved once, submitted to the mock connector, and recorded in the audit." });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  };

  const simulateRejection = async () => {
    setBusy(true);
    try {
      const response = await fetch(`/api/cases/${caseData.id}/simulate-rejection`, { method: "POST" });
      if (!response.ok) throw new Error("The mock connector did not respond");
      setCaseData(await response.json());
      setNotice({ type: "warning", text: "Connector rejection became evidence; RE:ENTRY added a cited follow-up." });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setBusy(false);
    }
  };

  const uploadEvidence = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploadBusy(true);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`/api/cases/${caseData.id}/evidence`, { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Evidence could not be uploaded");
      await loadCase();
      setNotice({ type: "success", text: payload.message });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setUploadBusy(false);
    }
  };

  const jumpTo = (tab) => {
    setActiveTab(tab);
    document.getElementById(tab)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (!caseData) {
    return <div className="loading-screen"><div className="loading-mark">RE:ENTRY</div><div className="loading-line" />{loadError ? <><p>{loadError}</p><button className="run-button" onClick={() => loadCase().catch((error) => setLoadError(error.message))}>Try again</button></> : <p>Opening the recovery desk…</p>}</div>;
  }

  const approval = caseData.actions.find((action) => action.status === "needs_approval");
  const hasRejection = caseData.actions.some((action) => action.id === "act-06");

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup"><div className="brand">RE:ENTRY</div><span>PEOPLE<br />PLACES<br />FORWARD</span></div>
        <div className="topbar-motto">FROM CRISIS TO A MORE HUMAN TOMORROW</div>
        <div className="topbar-context"><StatusPill status="good">System operational</StatusPill><span className="context-divider" /><div><strong>{caseData.county}</strong><small>Mon, Sep 13, 2026&nbsp;&nbsp; 10:24 AM</small></div><Icon name="chevron" size={16} /></div>
      </header>

      <div className="workspace">
        <aside className="sidebar" aria-label="Primary navigation">
          <nav className="side-nav">
            {navItems.map(([id, label, icon]) => <button key={id} className={`nav-item ${id === "cases" ? "nav-active" : ""}`} onClick={() => jumpTo({ cases: "overview", map: "timeline", people: "people", resources: "evidence", communications: "actions", analytics: "people", settings: "notes" }[id])}><Icon name={icon} size={19} /><span>{label}</span></button>)}
          </nav>
          <div className="side-quote"><span className="quote-rule" /><p>“Stronger<br />communities<br />live here<br />again.”</p><small>RE:ENTRY field note 042</small></div>
          <div className="side-footer"><span className="avatar">MO</span><div><strong>Maya's advocate</strong><small>Case steward</small></div><Icon name="chevron" size={14} /></div>
        </aside>

        <main className="main-content">
          <section className="case-heading" id="overview">
            <div className="breadcrumb"><Icon name="back" size={15} /> <span>All cases</span></div>
            <div className="heading-row"><div><h1>{caseData.title}</h1><div className="case-meta"><span>{caseData.county}</span><i /> <span>Opened {caseData.opened_at}</span><i /> <span className="priority"><span /> High priority</span></div></div><div className="phase-panel"><Icon name="pulse" size={28} /><div><strong>Recovery in progress</strong><small>People housed&nbsp;&nbsp;•&nbsp;&nbsp;Services restoring&nbsp;&nbsp;•&nbsp;&nbsp;Risks monitored</small></div></div></div>
          </section>

          <div className="tab-strip" role="tablist">
            {tabs.map(([id, label]) => <button key={id} className={activeTab === id ? "tab-active" : ""} onClick={() => jumpTo(id)} role="tab" aria-selected={activeTab === id}>{label}{id === "actions" && actionCounts.approval > 0 ? <span className="tab-count">{actionCounts.approval}</span> : null}</button>)}
          </div>

          <div className="dashboard-grid">
            <section className="panel timeline-panel" id="timeline">
              <PanelHeader icon="document" title="Case timeline" eyebrow="Live updates" live />
              <div className="timeline-layout"><div className="timeline-list">{caseData.timeline.slice(-6).map((event, index) => <TimelineRow key={event.id} event={event} isLast={index === caseData.timeline.slice(-6).length - 1} />)}</div><MapPlate /></div>
            </section>

            <SafetyPanel trace={caseData.trace} onRun={runPlan} busy={busy} />

            <section className="panel evidence-panel" id="evidence">
              <PanelHeader icon="document" title="Evidence" eyebrow={`${caseData.evidence.length} items`} action={<label className="upload-button"><Icon name="upload" size={15} />{uploadBusy ? "Uploading…" : "Add evidence"}<input type="file" accept=".pdf,.txt,.md,.csv,.png,.jpg,.jpeg" onChange={uploadEvidence} disabled={uploadBusy} /></label>} />
              <div className="evidence-grid">{caseData.evidence.map((item) => <EvidenceCard key={item.id} item={item} onClick={() => setSelectedEvidence(item)} />)}</div>
              <div className="panel-footnote"><Icon name="lock" size={14} /> Uploaded files are quarantined until a human verifies them.</div>
            </section>

            <section className="panel actions-panel" id="actions">
              <PanelHeader icon="bars" title="Action queue" eyebrow={`${caseData.actions.length} items`} action={<button className="text-button" onClick={() => jumpTo("actions")}>Open queue <Icon name="chevron" size={13} /></button>} />
              <div className="action-list">{caseData.actions.map((action) => <ActionRow key={action.id} action={action} onApprove={() => setApprovalAction(action)} onReject={action.id === "act-03" && !hasRejection ? simulateRejection : undefined} />)}</div>
              <div className="action-foot"><span><span className="mini-check">✓</span> {actionCounts.completed} completed safely</span><span><span className="mini-clock">{actionCounts.approval}</span> {actionCounts.approval} checkpoint{actionCounts.approval === 1 ? "" : "s"}</span></div>
            </section>

            <section className="trace-strip" id="people"><div className="trace-intro"><span className="trace-kicker">AGENT PATH</span><strong>Every step stays inspectable.</strong><p>Strands proposes. The safety gate decides.</p></div>{caseData.trace.map((step) => <div className={`trace-step trace-${step.status}`} key={step.id}><span className="trace-number">{step.id.slice(-1).padStart(2, "0")}</span><div><strong>{step.agent}</strong><small>{step.detail}</small></div><span className="trace-state">{step.status}</span></div>)}</section>

            <section className="connector-lab" id="notes"><div><span className="trace-kicker">CONNECTOR SANDBOX</span><h3>Show the plan adapting.</h3><p>Trigger a safe insurer rejection. The response becomes evidence, the plan changes, and the approval boundary stays intact.</p></div><button className="outline-button" onClick={simulateRejection} disabled={busy || hasRejection}>{hasRejection ? "Rejection already mapped" : "Simulate rejection"}<Icon name="arrow" size={16} /></button></section>
          </div>

          <footer className="main-footer"><div><span className="footer-mark"><Icon name="shield" size={15} /></span><strong>Human decisions, visible by design.</strong><span>Demo data only · no real agencies contacted</span></div><button className="reset-button" onClick={resetDemo} disabled={busy}><Icon name="refresh" size={14} /> Reset synthetic case</button></footer>
        </main>
      </div>

      {notice && <div className={`toast toast-${notice.type}`} role="status"><span className="toast-bullet" />{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss notification"><Icon name="x" size={14} /></button></div>}
      {selectedEvidence && <EvidenceDrawer item={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}
      {approvalAction && <ApprovalModal action={approvalAction} onClose={() => setApprovalAction(null)} onApprove={approve} busy={busy} />}
    </div>
  );
}

function PanelHeader({ icon, title, eyebrow, action, live }) {
  return <div className="panel-header"><div className="panel-title"><span className="panel-icon"><Icon name={icon} size={19} /></span><h2>{title}</h2></div><div className="panel-eyebrow">{live && <span className="live-dot" />}{eyebrow}</div>{action}</div>;
}

function TimelineRow({ event, isLast }) {
  return <div className={`timeline-row timeline-${event.tone}`}><div className="timeline-time">{event.at}</div><div className="timeline-rail"><span className="timeline-node" />{!isLast && <span className="timeline-stem" />}</div><div className="timeline-copy"><strong>{event.title}</strong><span>{event.detail}</span><small>{event.source}</small></div></div>;
}

function MapPlate() {
  return <div className="map-plate"><svg viewBox="0 0 320 230" role="img" aria-label="Stylised Riverton County recovery map"><path className="map-river" d="M-8 185C55 162 65 86 112 92c43 5 39 59 91 48 54-11 45-87 125-92" /><path className="map-road" d="M18 32 284 210M67-8l40 250M-8 116l343-32M205-8l-18 260" /><path className="map-road faint" d="m10 216 310-155M150-5l102 240" /><path className="map-zone" d="M168 55 252 43l33 69-73 53-55-38Z" /><circle className="map-pin pin-coral" cx="209" cy="102" r="6" /><circle className="map-pin pin-lime" cx="120" cy="128" r="5" /><circle className="map-pin pin-ink" cx="267" cy="70" r="5" /><circle className="map-pin pin-lime" cx="249" cy="157" r="5" /></svg><div className="map-label"><strong>Riverton County</strong><span>Affected area · 12.4 sq mi</span></div><div className="map-legend"><span><i className="legend-coral" /> Affected area</span><span><i className="legend-lime" /> Services active</span><span><i className="legend-ink" /> Assessment points</span></div></div>;
}

function SafetyPanel({ trace, onRun, busy }) {
  const reasons = [["shield", "Grounded in verified evidence", "Uses only authenticated documents, field reports, and official data."], ["eye", "Shows its work", "Citations, source documents, and reasoning are attached to every output."], ["people", "Human in the loop", "People review and approve all actions that affect real lives."], ["warning", "Checks for unintended impact", "Flags risks to equity, privacy, and vulnerable populations."], ["lock", "Auditable from end to end", "Full record of inputs, decisions, approvals, and outcomes."]];
  return <aside className="panel safety-panel"><div className="safety-heading"><span className="safety-icon"><Icon name="shield" size={23} /></span><div><span className="trace-kicker">THE PROMISE</span><h2>Why this is safe</h2></div></div><p className="safety-lede">Every recommendation is traceable, reviewable, and designed to do no harm.</p><div className="safety-reasons">{reasons.map(([icon, title, detail]) => <div className="safety-reason" key={title}><span className="reason-icon"><Icon name={icon} size={17} /></span><div><strong>{title}</strong><span>{detail}</span></div></div>)}</div><div className="safety-footer"><span>Safer decisions.<br /><em>Brighter tomorrows.</em></span><button className="run-button" onClick={onRun} disabled={busy}>{busy ? <><span className="spinner" /> Checking…</> : <><Icon name="pulse" size={16} /> Run recovery check</>}</button></div></aside>;
}

function EvidenceCard({ item, onClick }) {
  return <button className="evidence-card" onClick={onClick}><div className={`evidence-thumb thumb-${item.kind}`}><TypeMark kind={item.kind} />{item.kind === "photo" && <span className="thumb-scene" />}{item.kind === "official_notice" && <><span className="thumb-line" /><span className="thumb-line short" /><span className="thumb-stamp">R</span></>}{item.kind === "agreement" && <><span className="thumb-lines" /><span className="thumb-signature" /></>}{item.kind === "email" && <><span className="thumb-mail" /><span className="thumb-lines" /></>}{item.kind === "estimate" && <><span className="thumb-table" /><span className="thumb-total">$</span></>}{item.kind === "connector_response" && <><Icon name="warning" size={27} /><span className="thumb-reply" /></>}</div><div className="evidence-card-copy"><strong>{item.title}</strong><span>{item.received_at}</span><span className={`confidence confidence-${item.status}`}><i /> {item.status === "verified" ? `${Math.round(item.confidence * 100)}% verified` : item.status === "conflict" ? "Conflict flagged" : "Needs review"}</span></div></button>;
}

function ActionRow({ action, onApprove, onReject }) {
  const statusIcon = action.status === "completed" ? "check" : action.status === "needs_approval" ? "clock" : action.status === "blocked" ? "warning" : "pulse";
  return <div className={`action-row action-${action.status}`}><span className="action-status-icon"><Icon name={statusIcon} size={16} /></span><div className="action-main"><strong>{action.title}</strong><span>{action.description}</span><small>{action.connector} <i /> {action.due}</small></div><div className="action-end"><StatusPill status={action.status}>{formatActionStatus(action.status)}</StatusPill>{action.status === "needs_approval" && <button className="review-button" onClick={onApprove}>Review <Icon name="chevron" size={13} /></button>}{onReject && <button className="row-link" onClick={onReject}>Test response</button>}{action.status === "blocked" && <span className="blocked-reason">{action.rejection_reason}</span>}</div></div>;
}

function EvidenceDrawer({ item, onClose }) {
  return <div className="drawer-scrim" onClick={onClose}><aside className="evidence-drawer" onClick={(event) => event.stopPropagation()}><button className="drawer-close" onClick={onClose} aria-label="Close evidence"><Icon name="x" size={18} /></button><span className="trace-kicker">EVIDENCE RECORD</span><h2>{item.title}</h2><div className="drawer-meta"><TypeMark kind={item.kind} /><span>{item.source}</span><span>{item.received_at}</span></div><div className={`drawer-confidence drawer-${item.status}`}><span className="confidence-ring">{Math.round(item.confidence * 100)}</span><div><strong>{item.status === "verified" ? "Verified source" : item.status === "conflict" ? "Conflict needs review" : "Review before use"}</strong><span>Confidence score · {Math.round(item.confidence * 100)}%</span></div></div><div className="drawer-section"><span className="trace-kicker">EXCERPT</span><blockquote>“{item.excerpt}”</blockquote></div><div className="drawer-section"><span className="trace-kicker">TAGS</span><div className="tag-list">{item.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div></div><div className="drawer-foot"><Icon name="lock" size={15} /> Source stays attached to every recommendation.</div></aside></div>;
}

function ApprovalModal({ action, onClose, onApprove, busy }) {
  const [reviewer, setReviewer] = useState("Maya's advocate");
  const [note, setNote] = useState("Address, county notice, and damage photo checked.");
  return <div className="modal-scrim" onClick={onClose}><div className="approval-modal" onClick={(event) => event.stopPropagation()}><button className="drawer-close" onClick={onClose} aria-label="Close approval"><Icon name="x" size={18} /></button><div className="modal-topline"><span className="modal-lock"><Icon name="shield" size={20} /></span><div><span className="trace-kicker">HUMAN CHECKPOINT</span><h2>Approve one action</h2></div></div><p className="modal-lede">RE:ENTRY will send this prepared packet to a mock connector only after you confirm the cited evidence.</p><div className="approval-preview"><strong>{action.title}</strong><span>{action.target}</span><div>{action.citations.map((citation) => <span className="citation-chip" key={citation.evidence_id}><Icon name="document" size={13} />{citation.label}</span>)}</div></div><label className="field-label">Reviewer<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} maxLength={80} /></label><label className="field-label">Decision note<textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} rows={3} /></label><div className="modal-actions"><button className="text-button" onClick={onClose}>Keep paused</button><button className="run-button approve-button" onClick={() => onApprove(reviewer, note)} disabled={busy || reviewer.trim().length < 2}>{busy ? <><span className="spinner" /> Recording…</> : <><Icon name="check" size={16} /> Approve & send</>}</button></div></div></div>;
}

createRoot(document.getElementById("root")).render(<StrictMode><App /></StrictMode>);
