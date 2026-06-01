(function () {
  'use strict';

  // ============================================
  // STATE
  // ============================================
  let currentUser = null;
  let currentAnalysis = null;
  let readingsFilter = 'all';
  let selectedFile = null;
  let loadingInterval = null;

  // ============================================
  // DOM REFERENCES
  // ============================================
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => ctx.querySelectorAll(sel);

  // Views
  const authView = $('#auth-view');
  const dashboardView = $('#dashboard-view');
  const loadingView = $('#loading-view');
  const resultsView = $('#results-view');
  const allViews = [authView, dashboardView, loadingView, resultsView];

  // Auth
  const tabLogin = $('#tab-login');
  const tabSignup = $('#tab-signup');
  const loginForm = $('#login-form');
  const signupForm = $('#signup-form');
  const authError = $('#auth-error');

  // Dashboard
  const usernameDisplay = $('#username-display');
  const logoutBtn = $('#logout-btn');
  const dropZone = $('#drop-zone');
  const fileInput = $('#file-input');
  const fileInfo = $('#file-info');
  const fileName = $('#file-name');
  const fileSize = $('#file-size');
  const clearFileBtn = $('#clear-file');
  const historyList = $('#history-list');
  const historyEmpty = $('#history-empty');
  const analysisError = $('#analysis-error');
  const analysisErrorMessage = $('#analysis-error-message');
  const closeAnalysisErrorBtn = $('#close-analysis-error');

  // Loading
  const loadingStatus = $('#loading-status');

  // Results
  const backBtn = $('#back-to-dashboard');
  const patientInfoGrid = $('#patient-info-grid');
  const summaryText = $('#summary-text');
  const readingsCount = $('#readings-count');
  const readingsTbody = $('#readings-tbody');
  const readingsFilter$ = $('#readings-filter');
  const abnormalSection = $('#abnormal-section');
  const abnormalCount = $('#abnormal-count');
  const abnormalCards = $('#abnormal-cards');
  const recommendationsGrid = $('#recommendations-grid');

  // Toast
  const toastContainer = $('#toast-container');

  // ============================================
  // INITIALIZATION
  // ============================================
  document.addEventListener('DOMContentLoaded', init);

  function init() {
    checkAuth();
    setupEventListeners();
    setupDragDrop();
  }

  // ============================================
  // EVENT LISTENERS
  // ============================================
  function setupEventListeners() {
    // Auth tabs
    tabLogin.addEventListener('click', () => switchAuthTab('login'));
    tabSignup.addEventListener('click', () => switchAuthTab('signup'));

    // Auth forms
    loginForm.addEventListener('submit', handleLogin);
    signupForm.addEventListener('submit', handleSignup);

    // Logout
    logoutBtn.addEventListener('click', handleLogout);

    // File input
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
      }
    });
    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length) handleFileSelect(e.target.files[0]);
    });
    clearFileBtn.addEventListener('click', clearFile);
    closeAnalysisErrorBtn.addEventListener('click', () => {
      analysisError.style.display = 'none';
    });

    // Results
    backBtn.addEventListener('click', () => {
      showView('dashboard');
      loadHistory();
    });

    // Filter tabs
    readingsFilter$.addEventListener('click', (e) => {
      if (e.target.classList.contains('filter-tab')) {
        filterReadings(e.target.dataset.filter);
      }
    });
  }

  // ============================================
  // VIEW MANAGEMENT
  // ============================================
  function showView(viewName) {
    allViews.forEach((v) => {
      v.classList.remove('active');
      v.hidden = true;
    });

    let target;
    switch (viewName) {
      case 'auth':
        target = authView;
        break;
      case 'dashboard':
        target = dashboardView;
        break;
      case 'loading':
        target = loadingView;
        break;
      case 'results':
        target = resultsView;
        break;
    }

    if (target) {
      target.hidden = false;
      target.classList.add('active');
    }
  }

  // ============================================
  // AUTH TAB TOGGLE
  // ============================================
  function switchAuthTab(tab) {
    hideAuthError();

    if (tab === 'login') {
      tabLogin.classList.add('active');
      tabLogin.setAttribute('aria-selected', 'true');
      tabSignup.classList.remove('active');
      tabSignup.setAttribute('aria-selected', 'false');
      loginForm.hidden = false;
      signupForm.hidden = true;
    } else {
      tabSignup.classList.add('active');
      tabSignup.setAttribute('aria-selected', 'true');
      tabLogin.classList.remove('active');
      tabLogin.setAttribute('aria-selected', 'false');
      signupForm.hidden = false;
      loginForm.hidden = true;
    }
  }

  // ============================================
  // AUTH — LOGIN
  // ============================================
  async function handleLogin(e) {
    e.preventDefault();
    hideAuthError();

    const username = $('#login-username').value.trim();
    const password = $('#login-password').value;

    if (!username || !password) {
      showAuthError('Please fill in all fields.');
      return;
    }

    const btn = $('#login-submit');
    setButtonLoading(btn, true);

    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        showAuthError(data.error || data.message || 'Login failed.');
        return;
      }

      currentUser = data.username;
      usernameDisplay.textContent = currentUser;
      loginForm.reset();
      showView('dashboard');
      loadHistory();
      showToast('Welcome back, ' + escapeHtml(currentUser) + '!', 'success');
    } catch (err) {
      showAuthError('Network error. Please try again.');
    } finally {
      setButtonLoading(btn, false);
    }
  }

  // ============================================
  // AUTH — SIGNUP
  // ============================================
  async function handleSignup(e) {
    e.preventDefault();
    hideAuthError();

    const username = $('#signup-username').value.trim();
    const email = $('#signup-email').value.trim();
    const password = $('#signup-password').value;
    const confirm = $('#signup-confirm').value;

    if (!username || !email || !password || !confirm) {
      showAuthError('Please fill in all fields.');
      return;
    }

    if (password !== confirm) {
      showAuthError('Passwords do not match.');
      return;
    }

    if (password.length < 6) {
      showAuthError('Password must be at least 6 characters.');
      return;
    }

    const btn = $('#signup-submit');
    setButtonLoading(btn, true);

    try {
      const res = await fetch('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        showAuthError(data.error || data.message || 'Signup failed.');
        return;
      }

      currentUser = data.username;
      usernameDisplay.textContent = currentUser;
      signupForm.reset();
      showView('dashboard');
      loadHistory();
      showToast('Account created successfully! Welcome, ' + escapeHtml(currentUser) + '.', 'success');
    } catch (err) {
      showAuthError('Network error. Please try again.');
    } finally {
      setButtonLoading(btn, false);
    }
  }

  // ============================================
  // AUTH — LOGOUT
  // ============================================
  async function handleLogout() {
    try {
      await fetch('/api/logout', { method: 'POST' });
    } catch (_) {
      // Ignore
    }

    currentUser = null;
    currentAnalysis = null;
    selectedFile = null;
    showView('auth');
    showToast('Logged out successfully.', 'info');
  }

  // ============================================
  // AUTH — CHECK STATUS
  // ============================================
  async function checkAuth() {
    try {
      const res = await fetch('/api/me');
      const data = await res.json();

      if (data.logged_in) {
        currentUser = data.username;
        usernameDisplay.textContent = currentUser;
        showView('dashboard');
        loadHistory();
      } else {
        showView('auth');
      }
    } catch (_) {
      showView('auth');
    }
  }

  // ============================================
  // AUTH — HELPERS
  // ============================================
  function showAuthError(msg) {
    authError.textContent = msg;
    authError.hidden = false;
  }

  function hideAuthError() {
    authError.textContent = '';
    authError.hidden = true;
  }

  function setButtonLoading(btn, loading) {
    const text = btn.querySelector('.btn__text');
    const loader = btn.querySelector('.btn__loader');

    if (loading) {
      btn.disabled = true;
      if (text) text.hidden = true;
      if (loader) loader.hidden = false;
    } else {
      btn.disabled = false;
      if (text) text.hidden = false;
      if (loader) loader.hidden = true;
    }
  }

  // ============================================
  // DRAG & DROP
  // ============================================
  function setupDragDrop() {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((evt) => {
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    dropZone.addEventListener('dragenter', () => dropZone.classList.add('drag-over'));
    dropZone.addEventListener('dragover', () => dropZone.classList.add('drag-over'));
    dropZone.addEventListener('dragleave', (e) => {
      // Only remove if leaving the drop zone itself
      if (!dropZone.contains(e.relatedTarget)) {
        dropZone.classList.remove('drag-over');
      }
    });

    dropZone.addEventListener('drop', (e) => {
      dropZone.classList.remove('drag-over');
      const files = e.dataTransfer.files;
      if (files.length) handleFileSelect(files[0]);
    });
  }

  // ============================================
  // FILE HANDLING
  // ============================================
  function handleFileSelect(file) {
    // Validate type
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      showToast('Please select a PDF file.', 'error');
      return;
    }

    // Validate size (16 MB)
    const maxSize = 16 * 1024 * 1024;
    if (file.size > maxSize) {
      showToast('File is too large. Maximum size is 16 MB.', 'error');
      return;
    }

    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    fileInfo.hidden = false;

    // Auto-trigger analysis
    analyzeReport(file);
  }

  function clearFile() {
    selectedFile = null;
    fileInput.value = '';
    fileInfo.hidden = true;
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  }

  // ============================================
  // ANALYZE REPORT
  // ============================================
  // ============================================
  // ANALYZE REPORT
  // ============================================
  async function analyzeReport(file) {
    // Hide any previous errors
    analysisError.style.display = 'none';
    analysisErrorMessage.innerHTML = '';

    // Show loading view
    showView('loading');
    startLoadingMessages();

    const formData = new FormData();
    formData.append('file', file);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s timeout

      const res = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || data.message || 'Analysis failed.');
      }

      currentAnalysis = data.analysis;
      stopLoadingMessages();
      renderAnalysis(currentAnalysis);
      showView('results');
      clearFile();
      showToast('Report analyzed successfully!', 'success');
    } catch (err) {
      stopLoadingMessages();

      const errMsg = err.message || 'Failed to analyze report.';
      console.error('[ERROR] Analysis failed:', errMsg);

      // Show persistent troubleshooting alert box
      analysisErrorMessage.innerHTML = formatAnalysisError(errMsg);
      analysisError.style.display = 'block';

      if (err.name === 'AbortError') {
        showToast('Analysis timed out. Please try again.', 'error');
      } else {
        showToast('Analysis failed. Please check the error instructions.', 'error');
      }

      showView('dashboard');
      clearFile();
      
      // Scroll to error box
      analysisError.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // ============================================
  // ANALYSIS ERROR FORMATTER
  // ============================================
  function formatAnalysisError(msg) {
    const lower = msg.toLowerCase();
    
    if (msg.includes("NO_API_KEY") || lower.includes("no_api_key") || lower.includes("api key is required") || lower.includes("configure an open-source")) {
      return `
        <p style="margin-bottom: 12px; font-weight: 600; color: #ff4b4b; font-size: 15px;">No Open-Source API Key Configured</p>
        <p style="margin-bottom: 10px;">To run medical report analysis using free, high-performance open-source models, please set up at least one API key in your <strong>.env</strong> file:</p>
        <ol style="margin-left: 20px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 10px; padding-left: 0; list-style-position: inside;">
          <li style="margin-bottom: 6px;">
            <strong>SambaNova Key (Recommended - 100% Free, Super Fast, Huge Limits)</strong>:<br>
            1. Go to <a href="https://cloud.sambanova.ai/" target="_blank" style="color: #58a6ff; text-decoration: underline; font-weight: 600;">cloud.sambanova.ai</a> and create an account.<br>
            2. Generate a free API key and copy it.<br>
            3. Add it to your <strong>.env</strong> file:<br>
            <code style="display: inline-block; background: rgba(255,255,255,0.08); padding: 4px 8px; border-radius: 6px; font-size: 13px; font-family: monospace; margin-top: 4px; border: 1px solid rgba(255,255,255,0.1); color: #e6edf3;">SAMBANOVA_API_KEY=your_sambanova_api_key_here</code>
          </li>
          <li style="margin-bottom: 6px;">
            <strong>Groq Key (Free open-source alternative)</strong>:<br>
            1. Go to <a href="https://console.groq.com/" target="_blank" style="color: #58a6ff; text-decoration: underline; font-weight: 600;">console.groq.com</a>.<br>
            2. Generate a free API key, copy it, and add to <strong>.env</strong>:<br>
            <code style="display: inline-block; background: rgba(255,255,255,0.08); padding: 4px 8px; border-radius: 6px; font-size: 13px; font-family: monospace; margin-top: 4px; border: 1px solid rgba(255,255,255,0.1); color: #e6edf3;">GROQ_API_KEY=your_groq_api_key_here</code>
          </li>
          <li>
            <strong>OpenRouter Key (Completely free models)</strong>:<br>
            1. Go to <a href="https://openrouter.ai/" target="_blank" style="color: #58a6ff; text-decoration: underline; font-weight: 600;">openrouter.ai</a>.<br>
            2. Generate a free API key and add to <strong>.env</strong>:<br>
            <code style="display: inline-block; background: rgba(255,255,255,0.08); padding: 4px 8px; border-radius: 6px; font-size: 13px; font-family: monospace; margin-top: 4px; border: 1px solid rgba(255,255,255,0.1); color: #e6edf3;">OPENROUTER_API_KEY=your_openrouter_api_key_here</code>
          </li>
        </ol>
        <p style="font-size: 13px; color: var(--text-muted); margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px;">
          💡 <strong>Note:</strong> After updating the <strong>.env</strong> file, make sure to <strong>restart your Flask server</strong> (<code style="background: rgba(255,255,255,0.08); padding: 2px 4px; border-radius: 4px; font-family: monospace;">python app.py</code>) for the new keys to take effect!
        </p>
      `;
    }
    
    if (msg.includes("AUTH_ERROR") || msg.includes("FORBIDDEN") || lower.includes("auth_error") || lower.includes("unauthorized") || lower.includes("forbidden")) {
      return `
        <p style="margin-bottom: 8px; font-weight: 600; color: #ff4b4b; font-size: 15px;">Invalid or Rejected API Key</p>
        <p style="margin-bottom: 10px;">The API key configured in your <strong>.env</strong> file was rejected by the provider server. This can happen if the key was mistyped, deleted, or suspended.</p>
        <p style="margin-bottom: 8px;"><strong>Please check:</strong></p>
        <ul style="margin-left: 20px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 6px; padding-left: 0; list-style-position: inside;">
          <li>Verify your active key matches the one on your developer dashboard exactly.</li>
          <li>Make sure you didn't leave any spaces or quotes around the key in <strong>.env</strong>.</li>
          <li>Links to manage keys:
            <a href="https://cloud.sambanova.ai/" target="_blank" style="color: #58a6ff; text-decoration: underline; margin-left: 5px;">SambaNova</a> |
            <a href="https://console.groq.com/" target="_blank" style="color: #58a6ff; text-decoration: underline; margin-left: 5px;">Groq</a> |
            <a href="https://openrouter.ai/" target="_blank" style="color: #58a6ff; text-decoration: underline; margin-left: 5px;">OpenRouter</a>
          </li>
        </ul>
        <p style="font-size: 13px; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px; margin-top: 10px;">
          💡 <strong>Tip:</strong> Restart your Flask server after modifying the <strong>.env</strong> file.
        </p>
      `;
    }
    
    if (msg.includes("RATE_LIMIT") || lower.includes("rate_limit") || lower.includes("too many requests") || lower.includes("quota exceeded")) {
      return `
        <p style="margin-bottom: 8px; font-weight: 600; color: #ff4b4b; font-size: 15px;">Rate Limit or Quota Reached</p>
        <p style="margin-bottom: 10px;">You have hit the free tier rate limit or daily request quota for your active open-source provider.</p>
        <p style="margin-bottom: 8px;"><strong>How to resolve:</strong></p>
        <ol style="margin-left: 20px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 8px; padding-left: 0; list-style-position: inside;">
          <li><strong>Switch to SambaNova (Highly Recommended)</strong>: SambaNova offers extremely high free tier limits (1,000 requests/day, 10 RPM) and is completely free without credit card constraints. Sign up at <a href="https://cloud.sambanova.ai/" target="_blank" style="color: #58a6ff; text-decoration: underline; font-weight: 600;">cloud.sambanova.ai</a>.</li>
          <li><strong>Add multiple keys in .env</strong>: The backend automatically falls back to other keys. If SambaNova, Groq, or OpenRouter are all configured, the app will try them in order!</li>
        </ol>
      `;
    }
    
    if (msg.includes("CONNECTION_ERROR") || lower.includes("connection_error") || lower.includes("failed to connect") || lower.includes("getaddrinfo failed")) {
      return `
        <p style="margin-bottom: 8px; font-weight: 600; color: #ff4b4b; font-size: 15px;">API Connection Failed</p>
        <p style="margin-bottom: 0;">The application was unable to reach the API server. This might be due to a lack of active internet connection, local firewall settings blocking outgoing HTTPS requests, or provider downtime. Please check your network and try again.</p>
      `;
    }
    
    return `
      <p style="margin-bottom: 8px; font-weight: 600; color: #ff4b4b; font-size: 15px;">Analysis Failed</p>
      <p style="margin-bottom: 0; font-family: monospace; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 6px; font-size: 13px; color: #f0f6fc; border: 1px solid rgba(255,255,255,0.05);">${escapeHtml(msg)}</p>
    `;
  }

  // ============================================
  // LOADING MESSAGES ROTATION
  // ============================================
  const loadingMessages = [
    'Reading test values...',
    'Identifying abnormalities...',
    'Evaluating severity levels...',
    'Cross-referencing normal ranges...',
    'Generating recommendations...',
    'Preparing your health summary...',
    'Analyzing dietary implications...',
    'Reviewing lifestyle factors...',
  ];

  function startLoadingMessages() {
    let idx = 0;
    loadingStatus.textContent = loadingMessages[0];

    loadingInterval = setInterval(() => {
      idx = (idx + 1) % loadingMessages.length;
      loadingStatus.style.opacity = '0';

      setTimeout(() => {
        loadingStatus.textContent = loadingMessages[idx];
        loadingStatus.style.opacity = '1';
      }, 300);
    }, 3000);
  }

  function stopLoadingMessages() {
    if (loadingInterval) {
      clearInterval(loadingInterval);
      loadingInterval = null;
    }
  }

  // ============================================
  // RESULTS RENDERING — MAIN
  // ============================================
  function renderAnalysis(analysis) {
    if (!analysis) return;

    renderPatientInfo(analysis.patient_info);
    renderSummary(analysis.summary);
    renderReadingsTable(analysis.readings);
    renderAbnormalReadings(analysis.abnormal_readings);
    renderRecommendations(analysis.recommendations);

    // Reset filter
    readingsFilter = 'all';
    $$('.filter-tab', readingsFilter$).forEach((t) => {
      t.classList.toggle('active', t.dataset.filter === 'all');
      t.setAttribute('aria-selected', t.dataset.filter === 'all' ? 'true' : 'false');
    });

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ============================================
  // RENDER — PATIENT INFO
  // ============================================
  function renderPatientInfo(info) {
    if (!info) {
      patientInfoGrid.innerHTML = '<p class="text-muted">No patient information available.</p>';
      return;
    }

    const fields = [
      { label: 'Name', value: info.name },
      { label: 'Age', value: info.age },
      { label: 'Gender', value: info.gender },
      { label: 'Date', value: info.date },
      { label: 'Lab', value: info.lab_name },
      { label: 'Report ID', value: info.report_id },
    ];

    patientInfoGrid.innerHTML = fields
      .map(
        (f) => `
        <div class="patient-field">
          <span class="patient-field__label">${escapeHtml(f.label)}</span>
          <span class="patient-field__value">${escapeHtml(f.value || '—')}</span>
        </div>`
      )
      .join('');
  }

  // ============================================
  // RENDER — SUMMARY
  // ============================================
  function renderSummary(summary) {
    summaryText.textContent = summary || 'No summary available.';
  }

  // ============================================
  // RENDER — READINGS TABLE
  // ============================================
  function renderReadingsTable(readings) {
    if (!readings || !readings.length) {
      readingsCount.textContent = '0';
      readingsTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">No readings found.</td></tr>';
      return;
    }

    readingsCount.textContent = readings.length;

    // Group by category
    const grouped = {};
    readings.forEach((r) => {
      const cat = r.category || 'Other';
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(r);
    });

    let html = '';
    for (const [category, items] of Object.entries(grouped)) {
      // Category header
      html += `<tr class="category-header-row"><td colspan="5">${escapeHtml(category)}</td></tr>`;

      items.forEach((r) => {
        const isAbnormal = r.status === 'Abnormal';
        const flagClass = getFlagClass(r.flag);
        const rowClass = isAbnormal ? 'abnormal-row' : '';

        html += `
          <tr class="${rowClass}" data-status="${isAbnormal ? 'abnormal' : 'normal'}">
            <td class="test-name">${escapeHtml(r.test_name || '')}</td>
            <td class="category-cell">${escapeHtml(r.category || '')}</td>
            <td>${escapeHtml(r.value || '')} ${escapeHtml(r.unit || '')}</td>
            <td>${escapeHtml(r.normal_range || '')}</td>
            <td>
              <span class="badge ${flagClass}">
                ${escapeHtml(r.flag || r.status || '')}
              </span>
            </td>
          </tr>`;
      });
    }

    readingsTbody.innerHTML = html;
  }

  function getFlagClass(flag) {
    if (!flag) return 'badge--normal';
    const lower = flag.toLowerCase();
    if (lower.includes('critical')) return 'badge--critical';
    if (lower.includes('high')) return 'badge--high';
    if (lower.includes('low')) return 'badge--low';
    if (lower === 'normal') return 'badge--normal';
    return 'badge--abnormal';
  }

  // ============================================
  // FILTER READINGS
  // ============================================
  function filterReadings(filter) {
    readingsFilter = filter;

    // Update tabs
    $$('.filter-tab', readingsFilter$).forEach((t) => {
      t.classList.toggle('active', t.dataset.filter === filter);
      t.setAttribute('aria-selected', t.dataset.filter === filter ? 'true' : 'false');
    });

    // Filter rows
    const rows = $$('#readings-tbody tr');
    rows.forEach((row) => {
      if (row.classList.contains('category-header-row')) {
        // Show/hide category headers based on visible children
        row.style.display = '';
        return;
      }

      const status = row.dataset.status;
      if (filter === 'all') {
        row.style.display = '';
      } else if (filter === 'normal') {
        row.style.display = status === 'normal' ? '' : 'none';
      } else if (filter === 'abnormal') {
        row.style.display = status === 'abnormal' ? '' : 'none';
      }
    });

    // Hide category headers with no visible children
    const catHeaders = $$('#readings-tbody .category-header-row');
    catHeaders.forEach((header) => {
      let next = header.nextElementSibling;
      let hasVisible = false;

      while (next && !next.classList.contains('category-header-row')) {
        if (next.style.display !== 'none') {
          hasVisible = true;
          break;
        }
        next = next.nextElementSibling;
      }

      header.style.display = hasVisible ? '' : 'none';
    });
  }

  // ============================================
  // RENDER — ABNORMAL READINGS
  // ============================================
  function renderAbnormalReadings(abnormals) {
    if (!abnormals || !abnormals.length) {
      abnormalSection.hidden = true;
      return;
    }

    abnormalSection.hidden = false;
    abnormalCount.textContent = abnormals.length;

    abnormalCards.innerHTML = abnormals
      .map((a) => {
        const severityClass = getSeverityClass(a.severity);
        const rangeBar = buildRangeBar(a.value, a.normal_range);

        return `
          <div class="abnormal-card abnormal-card--${(a.severity || 'mild').toLowerCase()}">
            <div class="abnormal-card__header">
              <span class="abnormal-card__name">${escapeHtml(a.test_name || '')}</span>
              <span class="severity-badge severity-badge--${(a.severity || 'mild').toLowerCase()}">${escapeHtml(a.severity || 'Unknown')}</span>
            </div>
            <div class="abnormal-card__values">
              <div class="abnormal-card__current">
                <span class="abnormal-card__current-label">Current Value</span>
                <span class="abnormal-card__current-value">${escapeHtml(a.value || '')} ${escapeHtml(a.unit || '')}</span>
              </div>
              <span class="abnormal-card__vs">vs</span>
              <div class="abnormal-card__range">
                <span class="abnormal-card__range-label">Normal Range</span>
                <span class="abnormal-card__range-value">${escapeHtml(a.normal_range || '')}</span>
              </div>
            </div>
            ${rangeBar}
            ${a.explanation ? `<p class="abnormal-card__explanation">${escapeHtml(a.explanation)}</p>` : ''}
          </div>`;
      })
      .join('');
  }

  function getSeverityClass(severity) {
    if (!severity) return 'mild';
    return severity.toLowerCase();
  }

  function buildRangeBar(value, normalRange) {
    // Parse normal range like "70-100", "< 200", "4.0 - 6.0"
    const numVal = parseFloat(String(value).replace(/[^0-9.\-]/g, ''));
    if (isNaN(numVal) || !normalRange) return '';

    const rangeMatch = String(normalRange).match(/([\d.]+)\s*[-–—]\s*([\d.]+)/);
    if (!rangeMatch) return '';

    const low = parseFloat(rangeMatch[1]);
    const high = parseFloat(rangeMatch[2]);

    if (isNaN(low) || isNaN(high) || low >= high) return '';

    // Calculate positions as percentages
    const rangeSpan = high - low;
    const padding = rangeSpan * 0.3; // 30% padding on each side
    const totalMin = low - padding;
    const totalMax = high + padding;
    const totalSpan = totalMax - totalMin;

    const normalStart = ((low - totalMin) / totalSpan) * 100;
    const normalWidth = (rangeSpan / totalSpan) * 100;

    let markerPos = ((numVal - totalMin) / totalSpan) * 100;
    markerPos = Math.max(2, Math.min(98, markerPos)); // Clamp

    return `
      <div class="range-bar">
        <div class="range-bar__normal" style="left: ${normalStart}%; width: ${normalWidth}%;"></div>
        <div class="range-bar__marker" style="left: ${markerPos}%;"></div>
      </div>`;
  }

  // ============================================
  // RENDER — RECOMMENDATIONS
  // ============================================
  function renderRecommendations(recs) {
    if (!recs) {
      recommendationsGrid.innerHTML = '<p class="rec-card__empty">No recommendations available.</p>';
      return;
    }

    const categories = [
      { key: 'diet', emoji: '🥗', title: 'Diet Recommendations' },
      { key: 'exercise', emoji: '🏃', title: 'Exercise Recommendations' },
      { key: 'lifestyle', emoji: '🌙', title: 'Lifestyle Recommendations' },
      { key: 'medical_followup', emoji: '🏥', title: 'Medical Follow-up' },
    ];

    recommendationsGrid.innerHTML = categories
      .map((cat) => {
        const items = recs[cat.key] || [];

        const itemsHtml = items.length
          ? items
              .map(
                (item) => `
                <div class="rec-item">
                  <p class="rec-item__title">${escapeHtml(item.title || '')}</p>
                  <p class="rec-item__desc">${escapeHtml(item.description || '')}</p>
                  ${item.related_to ? `<p class="rec-item__related">Related to: ${escapeHtml(item.related_to)}</p>` : ''}
                </div>`
              )
              .join('')
          : '<p class="rec-card__empty">No specific recommendations</p>';

        return `
          <div class="rec-card">
            <div class="rec-card__header">
              <span class="rec-card__emoji">${cat.emoji}</span>
              <span class="rec-card__title">${cat.title}</span>
            </div>
            <div class="rec-card__list">
              ${itemsHtml}
            </div>
          </div>`;
      })
      .join('');
  }

  // ============================================
  // HISTORY
  // ============================================
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();

      if (Array.isArray(data) && data.length > 0) {
        renderHistory(data);
        historyEmpty.hidden = true;
        historyList.hidden = false;
      } else {
        historyList.hidden = true;
        historyList.innerHTML = '';
        historyEmpty.hidden = false;
      }
    } catch (_) {
      historyList.hidden = true;
      historyList.innerHTML = '';
      historyEmpty.hidden = false;
    }
  }

  function renderHistory(analyses) {
    historyList.innerHTML = analyses
      .map(
        (a) => `
        <div class="history-item" data-id="${a.id}">
          <div class="history-item__info">
            <span class="history-item__name">${escapeHtml(a.filename || 'Untitled Report')}</span>
            <span class="history-item__date">${formatDate(a.created_at)}</span>
          </div>
          <div class="history-item__actions">
            <button class="btn btn--secondary btn--sm" onclick="window.__medscan.viewAnalysis(${a.id})" aria-label="View analysis for ${escapeHtml(a.filename || '')}">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              View
            </button>
            <button class="btn btn--danger btn--sm" onclick="window.__medscan.deleteAnalysis(${a.id})" aria-label="Delete analysis for ${escapeHtml(a.filename || '')}">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="3,6 5,6 21,6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              Delete
            </button>
          </div>
        </div>`
      )
      .join('');
  }

  async function viewAnalysis(id) {
    showView('loading');
    startLoadingMessages();

    try {
      const res = await fetch(`/api/history/${id}`);

      if (!res.ok) throw new Error('Failed to load analysis.');

      const data = await res.json();

      stopLoadingMessages();

      currentAnalysis = data.analysis || data;
      renderAnalysis(currentAnalysis);
      showView('results');
    } catch (err) {
      stopLoadingMessages();
      showToast(err.message || 'Failed to load analysis.', 'error');
      showView('dashboard');
    }
  }

  async function deleteAnalysis(id) {
    if (!confirm('Are you sure you want to delete this analysis? This action cannot be undone.')) {
      return;
    }

    try {
      const res = await fetch(`/api/history/${id}`, { method: 'DELETE' });

      if (!res.ok) throw new Error('Failed to delete analysis.');

      showToast('Analysis deleted.', 'success');
      loadHistory();
    } catch (err) {
      showToast(err.message || 'Failed to delete analysis.', 'error');
    }
  }

  // Expose history functions to onclick handlers
  window.__medscan = {
    viewAnalysis,
    deleteAnalysis,
  };

  // ============================================
  // TOAST NOTIFICATIONS
  // ============================================
  function showToast(message, type = 'info') {
    const icons = {
      success: '✓',
      error: '✕',
      info: 'ℹ',
    };

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.innerHTML = `
      <span class="toast__icon">${icons[type] || icons.info}</span>
      <span>${escapeHtml(message)}</span>
    `;

    toastContainer.appendChild(toast);

    // Auto-remove after 4s
    setTimeout(() => {
      toast.classList.add('removing');
      toast.addEventListener('animationend', () => toast.remove());
    }, 4000);
  }

  // ============================================
  // UTILITIES
  // ============================================
  function formatDate(dateStr) {
    if (!dateStr) return '';

    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;

      return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (_) {
      return dateStr;
    }
  }

  function escapeHtml(str) {
    if (str == null) return '';
    const s = String(str);
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }
})();
