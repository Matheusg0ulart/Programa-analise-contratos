/**
 * Sistema Multi-Agente Corporativo - Frontend Logic
 * WebSocket Streaming, Reatividade e Renderização de Relatório
 */

let currentSessionId = null;
let currentSocket = null;
let pollInterval = null;

// Elementos do DOM
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const btnSampleContract = document.getElementById('btnSampleContract');
const btnClearCache = document.getElementById('btnClearCache');
const btnNewAudit = document.getElementById('btnNewAudit');
const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const progressPct = document.getElementById('progressPct');
const currentStatusText = document.getElementById('currentStatusText');
const terminalBody = document.getElementById('terminalBody');
const btnClearTerminal = document.getElementById('btnClearTerminal');
const reportSection = document.getElementById('reportSection');
const wsBadge = document.getElementById('wsBadge');
const wsDot = document.getElementById('wsDot');
const wsText = document.getElementById('wsText');
const llmBadge = document.getElementById('llmBadge');
const cacheBadge = document.getElementById('cacheBadge');

// Cards dos Agentes
const cards = {
  extractor: document.getElementById('agentCardExtractor'),
  researcher: document.getElementById('agentCardResearcher'),
  compliance: document.getElementById('agentCardCompliance'),
  auditor: document.getElementById('agentCardAuditor')
};

const statuses = {
  extractor: document.getElementById('agentStatusExtractor'),
  researcher: document.getElementById('agentStatusResearcher'),
  compliance: document.getElementById('agentStatusCompliance'),
  auditor: document.getElementById('agentStatusAuditor')
};

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
  fetchHealth();
  setupEventListeners();
});

async function fetchHealth() {
  try {
    const res = await fetch('/api/v1/health');
    const data = await res.json();
    llmBadge.textContent = (data.llm_provider || 'Mock').toUpperCase();
    cacheBadge.textContent = data.cache?.backend === 'redis' ? 'Redis (Ativo)' : 'In-Memory/Fakeredis';
  } catch (err) {
    console.warn('Erro ao checar status de saúde:', err);
  }
}

function setupEventListeners() {
  // Upload por clique e Drag & Drop
  dropZone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) handleFileUpload(e.target.files[0]);
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-cyan-400');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('border-cyan-400');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-cyan-400');
    if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]);
  });

  // Botão de Demonstração Rápida
  btnSampleContract.addEventListener('click', async () => {
    resetUI();
    logTerminal('orchestrator', 'Solicitando contrato corporativo de demonstração...');
    try {
      const res = await fetch('/api/v1/audit/sample', { method: 'POST' });
      const data = await res.json();
      currentSessionId = data.session_id;
      logTerminal('orchestrator', `Sessão iniciada: ${currentSessionId} (${data.document_name})`);
      startWebSocket(currentSessionId);
      startPolling(currentSessionId);
    } catch (err) {
      logTerminal('error', `Falha ao iniciar demo: ${err.message}`);
    }
  });

  // Limpar Cache
  btnClearCache.addEventListener('click', async () => {
    try {
      await fetch('/api/v1/cache/clear', { method: 'POST' });
      logTerminal('cache', 'Cache semântico limpo com sucesso.');
      alert('Cache semântico do Redis limpo com sucesso.');
    } catch (err) {
      alert('Erro ao limpar cache: ' + err.message);
    }
  });

  // Novo Audit / Reset
  btnNewAudit.addEventListener('click', () => {
    resetUI();
    logTerminal('orchestrator', 'Painel reinicializado para nova auditoria.');
  });

  btnClearTerminal.addEventListener('click', () => {
    terminalBody.innerHTML = '';
  });

  // Download e Cópia do Relatório
  document.getElementById('btnDownloadMd')?.addEventListener('click', () => {
    if (currentSessionId) {
      window.open(`/api/v1/audit/${currentSessionId}/markdown`, '_blank');
    }
  });

  document.getElementById('btnCopySummary')?.addEventListener('click', () => {
    const summary = document.getElementById('reportSummary')?.textContent;
    if (summary) {
      navigator.clipboard.writeText(summary);
      alert('Resumo executivo copiado para a área de transferência!');
    }
  });
}

async function handleFileUpload(file) {
  resetUI();
  logTerminal('orchestrator', `Enviando arquivo: ${file.name} (${(file.size / 1024).toFixed(1)} KB)...`);

  const formData = new FormData();
  formData.append('file', file);
  formData.append('auto_start', 'true');

  try {
    const res = await fetch('/api/v1/audit/upload', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    currentSessionId = data.session_id;
    logTerminal('orchestrator', `Upload concluído. Sessão: ${currentSessionId}`);
    startWebSocket(currentSessionId);
    startPolling(currentSessionId);
  } catch (err) {
    logTerminal('error', `Erro ao fazer upload: ${err.message}`);
  }
}

function startWebSocket(sessionId) {
  if (currentSocket) {
    currentSocket.close();
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/audit/${sessionId}`;

  currentSocket = new WebSocket(wsUrl);

  currentSocket.onopen = () => {
    wsBadge.className = 'flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800';
    wsDot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-ping';
    wsText.textContent = 'WebSocket Conectado';
    logTerminal('websocket', `Streaming em tempo real ativado para sessão ${sessionId.substring(0, 8)}...`);
  };

  currentSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleWebSocketEvent(data);
    } catch (e) {
      console.error('Erro ao processar mensagem do websocket:', e);
    }
  };

  currentSocket.onclose = () => {
    wsBadge.className = 'flex items-center gap-1.5 px-3 py-1 rounded-full bg-gray-800 text-gray-400 border border-gray-700';
    wsDot.className = 'w-2 h-2 rounded-full bg-gray-500';
    wsText.textContent = 'WebSocket Encerrado';
  };

  currentSocket.onerror = (err) => {
    console.warn('Erro de conexão WebSocket:', err);
  };
}

function handleWebSocketEvent(data) {
  const agent = data.agent_name || 'orchestrator';
  const progress = data.progress || 0;
  const message = data.message || '';
  const payload = data.payload || {};

  updateProgress(progress, message);
  highlightActiveAgent(agent);
  logTerminal(agent, message);

  // Atualiza métricas parciais nos cards
  if (agent === 'extractor' && payload.total_chunks) {
    document.getElementById('extractorChunkCount').textContent = payload.total_chunks;
    document.getElementById('extractorOcrStatus').textContent = payload.ocr ? 'Sim' : 'Digital';
  } else if (agent === 'researcher' && payload.total_retrieved) {
    document.getElementById('researcherHits').textContent = payload.total_retrieved;
    document.getElementById('researcherCacheHits').textContent = payload.cached_hits || 0;
  } else if (agent === 'compliance' && payload.risk_score !== undefined) {
    document.getElementById('complianceRiskScore').textContent = `${payload.risk_score}/100`;
    document.getElementById('complianceFindingsCount').textContent = payload.findings_count || 0;
  } else if (agent === 'auditor') {
    if (payload.cycle) document.getElementById('auditorCycles').textContent = `${payload.cycle}/2`;
    if (payload.audit_score) document.getElementById('auditorScore').textContent = `${payload.audit_score}/100`;
  }

  if (progress >= 100) {
    fetchAndRenderReport(currentSessionId);
  }
}

function startPolling(sessionId) {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/v1/audit/${sessionId}/status`);
      if (!res.ok) return;
      const data = await res.json();

      if (data.status === 'completed') {
        clearInterval(pollInterval);
        fetchAndRenderReport(sessionId);
      } else if (data.status === 'error') {
        clearInterval(pollInterval);
        logTerminal('error', `A auditoria foi interrompida com erro.`);
      }
    } catch (e) {
      console.warn('Erro no polling:', e);
    }
  }, 2000);
}

function updateProgress(pct, msg) {
  progressSection.classList.remove('hidden');
  progressBar.style.width = `${pct}%`;
  progressPct.textContent = `${pct}%`;
  currentStatusText.textContent = msg;
}

function highlightActiveAgent(agentName) {
  Object.keys(cards).forEach((k) => {
    if (k === agentName) {
      cards[k].classList.add('agent-active');
      statuses[k].textContent = 'Em Execução';
      statuses[k].className = 'text-[11px] px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800';
    } else {
      cards[k].classList.remove('agent-active');
    }
  });
}

function markAllAgentsCompleted() {
  Object.keys(cards).forEach((k) => {
    cards[k].classList.remove('agent-active');
    statuses[k].textContent = 'Concluído';
    statuses[k].className = 'text-[11px] px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800';
  });
}

function logTerminal(agent, message) {
  const time = new Date().toLocaleTimeString();
  const p = document.createElement('p');

  let color = 'text-gray-400';
  let badge = `[${agent.toUpperCase()}]`;

  if (agent === 'extractor') color = 'text-blue-400';
  else if (agent === 'researcher') color = 'text-purple-400';
  else if (agent === 'compliance') color = 'text-amber-400';
  else if (agent === 'auditor') color = 'text-emerald-400';
  else if (agent === 'error') color = 'text-red-400';
  else if (agent === 'websocket') color = 'text-cyan-400';

  p.innerHTML = `<span class="text-gray-600">${time}</span> <span class="${color} font-bold">${badge}</span> ${escapeHtml(message)}`;
  terminalBody.appendChild(p);
  terminalBody.scrollTop = terminalBody.scrollHeight;
}

async function fetchAndRenderReport(sessionId) {
  markAllAgentsCompleted();
  try {
    const res = await fetch(`/api/v1/audit/${sessionId}/report`);
    if (!res.ok) return;
    const report = await res.json();
    renderReport(report);
  } catch (e) {
    logTerminal('error', `Falha ao carregar relatório final: ${e.message}`);
  }
}

function renderReport(report) {
  reportSection.classList.remove('hidden');

  document.getElementById('reportDocName').textContent = report.document_name;
  document.getElementById('reportSummary').textContent = report.executive_summary;

  // Scores
  const riskCircle = document.getElementById('riskScoreCircle');
  riskCircle.textContent = report.overall_risk_score;
  document.getElementById('auditScoreCircle').textContent = report.audit_quality_score;

  // Veredito
  const verdictBadge = document.getElementById('verdictBadge');
  verdictBadge.textContent = report.final_verdict;

  if (report.overall_risk_score > 60) {
    riskCircle.className = 'w-16 h-16 rounded-2xl bg-red-950/60 border border-red-700/60 flex items-center justify-center font-bold text-xl text-red-400 shadow-lg shadow-red-950/50';
    verdictBadge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-red-950 text-red-400 border border-red-800';
  } else if (report.overall_risk_score > 30) {
    riskCircle.className = 'w-16 h-16 rounded-2xl bg-amber-950/60 border border-amber-700/60 flex items-center justify-center font-bold text-xl text-amber-400 shadow-lg shadow-amber-950/50';
    verdictBadge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-950 text-amber-400 border border-amber-800';
  } else {
    riskCircle.className = 'w-16 h-16 rounded-2xl bg-emerald-950/60 border border-emerald-700/60 flex items-center justify-center font-bold text-xl text-emerald-400 shadow-lg shadow-emerald-950/50';
    verdictBadge.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-950 text-emerald-400 border border-emerald-800';
  }

  // Contadores
  let crit = 0, alt = 0, med = 0, baix = 0;
  report.compliance_findings.forEach(f => {
    if (f.risk_level === 'Crítico') crit++;
    else if (f.risk_level === 'Alto') alt++;
    else if (f.risk_level === 'Médio') med++;
    else baix++;
  });

  document.getElementById('badgeCritico').textContent = crit;
  document.getElementById('badgeAlto').textContent = alt;
  document.getElementById('badgeMedio').textContent = med;
  document.getElementById('badgeBaixo').textContent = baix;

  // Renderizar Achados
  const container = document.getElementById('findingsContainer');
  container.innerHTML = '';

  report.compliance_findings.forEach((finding, idx) => {
    const card = document.createElement('div');
    card.className = 'bg-gray-950 border border-gray-800 rounded-xl p-4 flex flex-col gap-3';

    let badgeColor = 'bg-gray-800 text-gray-300 border-gray-700';
    if (finding.risk_level === 'Crítico') badgeColor = 'bg-red-950 text-red-400 border-red-800';
    else if (finding.risk_level === 'Alto') badgeColor = 'bg-amber-950 text-amber-400 border-amber-800';
    else if (finding.risk_level === 'Médio') badgeColor = 'bg-yellow-950 text-yellow-400 border-yellow-800';

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-xs font-mono text-gray-500">#${idx + 1}</span>
          <h4 class="text-sm font-bold text-white">${escapeHtml(finding.clause_title)}</h4>
        </div>
        <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${badgeColor}">${finding.risk_level}</span>
      </div>
      
      <div class="bg-gray-900/80 border-l-2 border-red-500 rounded p-2.5 text-xs text-gray-300 italic">
        "${escapeHtml(finding.offending_text)}"
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div>
          <span class="text-gray-500 block mb-0.5 font-semibold">Análise de Risco:</span>
          <p class="text-gray-300">${escapeHtml(finding.risk_description)}</p>
        </div>
        <div>
          <span class="text-cyan-400 block mb-0.5 font-semibold">Recomendação Mitigatória:</span>
          <p class="text-gray-300">${escapeHtml(finding.mitigation_recommendation)}</p>
        </div>
      </div>

      <div class="text-[11px] text-gray-500 pt-2 border-t border-gray-900 flex justify-between">
        <span>Base Legal: <strong>${escapeHtml(finding.legal_basis)}</strong></span>
        <span>Página: <strong>${finding.page_number}</strong></span>
      </div>
    `;
    container.appendChild(card);
  });

  // Recomendações
  const recList = document.getElementById('recommendationsList');
  recList.innerHTML = '';
  report.recommendations.forEach(r => {
    const li = document.createElement('li');
    li.textContent = r;
    recList.appendChild(li);
  });

  // Scroll suave até o relatório
  reportSection.scrollIntoView({ behavior: 'smooth' });
}

function resetUI() {
  if (pollInterval) clearInterval(pollInterval);
  if (currentSocket) currentSocket.close();

  reportSection.classList.add('hidden');
  progressSection.classList.add('hidden');
  progressBar.style.width = '0%';
  progressPct.textContent = '0%';

  Object.keys(cards).forEach((k) => {
    cards[k].classList.remove('agent-active');
    statuses[k].textContent = 'Aguardando';
    statuses[k].className = 'text-[11px] px-2 py-0.5 rounded-full bg-gray-800 text-gray-400';
  });

  document.getElementById('extractorChunkCount').textContent = '-';
  document.getElementById('extractorOcrStatus').textContent = '-';
  document.getElementById('researcherHits').textContent = '-';
  document.getElementById('researcherCacheHits').textContent = '-';
  document.getElementById('complianceRiskScore').textContent = '-';
  document.getElementById('complianceFindingsCount').textContent = '-';
  document.getElementById('auditorCycles').textContent = '0/2';
  document.getElementById('auditorScore').textContent = '-';
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
