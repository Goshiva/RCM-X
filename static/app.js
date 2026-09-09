// Insurance Risk Adjustment Tool - Frontend Logic

let currentReport = null;
let coderValidationTimer = null;
let accessToken = sessionStorage.getItem('access_token') || '';
let currentUser = JSON.parse(sessionStorage.getItem('current_user') || 'null');
let claimedCodes = [];
let auditL1Codes = [];
let auditWrongCodes = [];
let auditDecisions = {};
let dashboardSnapshot = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    if (!accessToken || !currentUser) {
        window.location.replace('/login');
        return;
    }
    refreshCurrentUser().then(() => initializeWorkspace());
});

async function refreshCurrentUser() {
    const response = await fetch('/api/auth/me', {headers: authenticatedHeaders()});
    if (!response.ok) {
        logoutUser();
        return;
    }
    const data = await response.json();
    if (!data.success || !data.user) {
        logoutUser();
        return;
    }
    currentUser = data.user;
    sessionStorage.setItem('current_user', JSON.stringify(currentUser));
}

function initializeWorkspace() {
    setupTabNavigation();
    setupFileUpload();
    loadUploadConfig();
    setupCoderValidation();
    loadHCCReference();
    updateDashboard();
    updateSessionUI();
    restoreCoderChart();
    loadWipCount();
    setupQueueControls();
    if (['supervisor', 'manager', 'admin', 'master_admin'].includes(currentUser.role)) loadTeamQuality();
    const requestedTab = new URLSearchParams(window.location.search).get('tab');
    if (requestedTab) {
        const tabButton = document.querySelector(`.nav-tab[data-tab="${requestedTab}"]`);
        if (tabButton) tabButton.click();
    }
}

function authenticatedHeaders(json = false) {
    const headers = {};
    if (json) headers['Content-Type'] = 'application/json';
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    return headers;
}

async function loginUser() {
    const feedback = document.getElementById('login-feedback');
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: document.getElementById('login-username').value,
                password: document.getElementById('login-password').value
            })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Login failed');
        accessToken = data.access_token;
        currentUser = data.user;
        sessionStorage.setItem('access_token', accessToken);
        sessionStorage.setItem('current_user', JSON.stringify(currentUser));
        feedback.textContent = `Signed in as ${currentUser.username} (${currentUser.role})`;
        window.location.replace('/');
    } catch (error) {
        feedback.textContent = error.message;
        feedback.className = 'feedback error';
    }
}

async function registerUser() {
    const feedback = document.getElementById('register-feedback');
    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: document.getElementById('register-username').value.trim(),
                email: document.getElementById('register-email').value.trim(),
                password: document.getElementById('register-password').value
            })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Registration failed');
        feedback.textContent = 'Account created. Sign in above.';
        feedback.className = 'feedback success';
        document.getElementById('login-username').value = document.getElementById('register-username').value.trim();
        document.getElementById('login-password').value = document.getElementById('register-password').value;
    } catch (error) {
        feedback.textContent = error.message;
        feedback.className = 'feedback error';
    }
}

function updateSessionUI() {
    const authenticated = Boolean(accessToken && currentUser);
    const sessionUser = document.getElementById('session-user');
    if (sessionUser) {
        sessionUser.textContent = authenticated ? `Signed in: ${currentUser.username} (${currentUser.role})` : 'Not signed in';
    }
    const managementRoles = ['manager', 'supervisor', 'admin', 'master_admin'];
    const coderRoles = ['coder', 'coder_l1', 'coder_l2'];
    document.querySelectorAll('.role-supervisor').forEach(element => {
        element.style.display = authenticated && managementRoles.includes(currentUser.role) ? '' : 'none';
    });
    document.querySelectorAll('.role-coder').forEach(element => {
        element.style.display = authenticated && coderRoles.includes(currentUser.role) ? '' : 'none';
    });
    document.querySelectorAll('.role-calculator').forEach(element => {
        element.style.display = authenticated && !coderRoles.includes(currentUser.role) ? '' : 'none';
    });
}

function logoutUser() {
    accessToken = '';
    currentUser = null;
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('current_user');
    window.location.replace('/login');
}

async function downloadCodingExport() {
    try {
        const response = await fetch('/api/dashboard/export.xlsx', {headers: authenticatedHeaders()});
        if (!response.ok) throw new Error('Export failed. Supervisor or admin access is required.');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'coding_results.xlsx';
        link.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        alert(error.message);
    }
}

async function loadTeamQuality() {
        const response = await fetch('/api/dashboard/team-quality', {headers: authenticatedHeaders()});
        const data = await response.json();
        if (!response.ok || !data.success) return;
        const select = document.getElementById('team-coder-select');
        const table = document.getElementById('team-quality-table');
        if (!select || !table) return;
        const roleSelect = document.getElementById('new-user-role');
        if (roleSelect) {
            const roles = currentUser.role === 'supervisor' ? ['coder_l1', 'coder_l2']
                : currentUser.role === 'manager' ? ['supervisor']
                : ['manager', 'supervisor', 'coder_l1', 'coder_l2', 'admin'];
            roleSelect.innerHTML = roles.map(role => `<option value="${role}">${role}</option>`).join('');
        }
        select.innerHTML = '<option value="">Select coder</option>' + data.users.map(user =>
            `<option value="${user.user_id}">${escapeHTML(user.username)} · ${escapeHTML(user.role)}</option>`).join('');
        table.innerHTML = data.users.length
            ? `<table><thead><tr><th>Coder</th><th>Role</th><th>Production %</th><th>Charts</th><th>WIP</th><th>Audited</th><th>Quality</th></tr></thead><tbody>${data.users.map(user =>
                `<tr><td>${escapeHTML(user.username)}</td><td>${escapeHTML(user.role)}</td><td>${user.production_percent}%</td><td>${user.production_charts}</td><td>${user.wip_charts}</td><td>${user.audited_charts}</td><td>${user.quality_percent === null ? 'Pending' : `${user.quality_percent}%`}</td></tr>`).join('')}</tbody></table>`
            : '<p class="feedback muted">No coder performance records available.</p>';
}

async function createManagedUser() {
        const feedback = document.getElementById('user-management-feedback');
        const response = await fetch('/api/auth/users', {
            method: 'POST',
            headers: authenticatedHeaders(true),
            body: JSON.stringify({
                username: document.getElementById('new-user-name').value.trim(),
                email: document.getElementById('new-user-email').value.trim(),
                password: document.getElementById('new-user-password').value,
                role: document.getElementById('new-user-role').value
            })
        });
        const data = await response.json();
        feedback.textContent = response.ok ? `Created ${data.user.username} (${data.user.role}).` : (data.error || 'Account creation failed.');
        feedback.className = `feedback ${response.ok ? 'success' : 'error'}`;
        if (response.ok) loadTeamQuality();
}

async function downloadSelectedCoderReport() {
        const userId = document.getElementById('team-coder-select').value;
        if (!userId) return;
        const response = await fetch(`/api/dashboard/activity-log.xlsx?user_id=${encodeURIComponent(userId)}`, {
            headers: authenticatedHeaders()
        });
        if (!response.ok) return;
        const blob = await response.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `coding_activity_${userId}.xlsx`;
        link.click();
        URL.revokeObjectURL(link.href);
}

// Tab Navigation
function setupTabNavigation() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all nav tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabName).classList.add('active');
    
    // Add active class to clicked nav tab
    const activeTab = document.querySelector(`.nav-tab[data-tab="${tabName}"]`);
    if (activeTab) activeTab.classList.add('active');
    if (tabName === 'audit' && currentUser && ['manager', 'supervisor', 'admin', 'master_admin'].includes(currentUser.role)) {
        loadAuditBucket();
    }
}

// File Upload Setup
function setupFileUpload() {
    const uploadArea = document.getElementById('upload-area');
    const pdfInput = document.getElementById('pdf-input');
    
    uploadArea.addEventListener('click', () => pdfInput.click());
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#0066cc';
        uploadArea.style.backgroundColor = '#f0f7ff';
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = '#dee2e6';
        uploadArea.style.backgroundColor = '#f8f9ff';
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#dee2e6';
        if (e.dataTransfer.files.length > 0) {
            processFile(e.dataTransfer.files[0]);
        }

    });
    
    pdfInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            processFile(e.target.files[0]);
        }
    });
}

async function loadUploadConfig() {
    const pathElement = document.getElementById('upload-folder-path');
    if (!pathElement || !currentUser) return;
    try {
        const response = await fetch('/api/charts/upload-config', {headers: authenticatedHeaders()});
        const data = await response.json();
        if (response.ok && data.success) pathElement.textContent = data.upload_folder;
    } catch (error) {
        pathElement.textContent = 'Configured on the server';
    }
}

function processFile(file) {
    if (file.type !== 'application/pdf') {
        alert('Please select a PDF file');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    // Show progress
    document.getElementById('upload-area').style.display = 'none';
    document.getElementById('upload-progress').style.display = 'block';
    document.getElementById('progress-text').textContent = 'Uploading PDF...';
    
    const useWorkflowUpload = currentUser && ['supervisor', 'admin', 'master_admin'].includes(currentUser.role);
    fetch(useWorkflowUpload ? '/api/charts/upload' : '/api/upload-pdf', {
        method: 'POST',
        headers: authenticatedHeaders(),
        body: formData
    })
    .then(async response => ({status: response.status, data: await response.json()}))
    .then(({status, data}) => {
        if (data.success) {
            if (data.chart) {
                displayQueuedChart(data.chart);
            } else {
                displayOCRResults(data);
            }
        } else {
            const message = status === 403
                ? 'Upload requires a supervisor or admin account. Sign out and sign in as supervisor.'
                : 'Error: ' + (data.error || 'Upload failed');
            alert(message);
        }
        resetUploadArea();
    })
    .catch(error => {
        alert('Upload failed: ' + error);
        resetUploadArea();
    });
}

function displayQueuedChart(chart) {
    document.getElementById('ocr-results').style.display = 'block';
    document.getElementById('doc-type').textContent = 'QUEUED FOR NLP PROCESSING';
    document.getElementById('entities-list').innerHTML = `<li>Chart ${chart.chart_id} is queued for coder review.</li>`;
    document.getElementById('ocr-preview').textContent = chart.original_filename;
}

function resetUploadArea() {
    document.getElementById('upload-progress').style.display = 'none';
    document.getElementById('upload-area').style.display = 'block';
    document.getElementById('pdf-input').value = '';
}

function displayOCRResults(data) {
    document.getElementById('doc-type').textContent = data.document_type.toUpperCase();
    
    const entitiesList = document.getElementById('entities-list');
    entitiesList.innerHTML = '';
    const entities = data.entities;
    
    if (entities.person_names && entities.person_names.length > 0) {
        entitiesList.innerHTML += `<li><strong>Names:</strong> ${entities.person_names.join(', ')}</li>`;
    }
    if (entities.organizations && entities.organizations.length > 0) {
        entitiesList.innerHTML += `<li><strong>Organizations:</strong> ${entities.organizations.join(', ')}</li>`;
    }
    if (entities.email_addresses && entities.email_addresses.length > 0) {
        entitiesList.innerHTML += `<li><strong>Emails:</strong> ${entities.email_addresses.join(', ')}</li>`;
    }
    if (entities.identifiers && entities.identifiers.employee_id) {
        entitiesList.innerHTML += `<li><strong>Employee ID:</strong> ${entities.identifiers.employee_id}</li>`;
    }
    if (entities.identifiers && entities.identifiers.pan) {
        entitiesList.innerHTML += `<li><strong>PAN:</strong> ${entities.identifiers.pan}</li>`;
    }
    
    document.getElementById('ocr-preview').textContent = data.ocr_text;
    document.getElementById('ocr-results').style.display = 'block';
}

// Risk Calculation
function calculateRisk() {
    const patientId = document.getElementById('patient-id').value || 'PAT_' + Date.now();
    const age = parseInt(document.getElementById('age').value);
    const gender = document.getElementById('gender').value;
    const insuranceModel = document.getElementById('insurance-model').value;
    const icd10Input = document.getElementById('icd10-codes').value;
    const icd10Codes = icd10Input.split(',').map(c => c.trim()).filter(c => c.length > 0);
    
    if (icd10Codes.length === 0) {
        alert('Please enter at least one ICD-10 code');
        return;
    }
    
    const payload = {
        patient_id: patientId,
        age: age,
        gender: gender,
        insurance_model: insuranceModel,
        icd10_codes: icd10Codes
    };
    
    fetch('/api/calculate-risk', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            currentReport = data.report;
            displayRiskResults(data.report);
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => alert('Calculation failed: ' + error));
}

function displayRiskResults(report) {
    const raf = report.raf_calculation;
    const premium = report.premium_calculation;
    
    document.getElementById('raf-score').textContent = raf.raf_score.toFixed(3);
    document.getElementById('risk-level').textContent = report.risk_level;
    document.getElementById('annual-premium').textContent = '$' + premium.adjusted_premium.toLocaleString('en-US', {maximumFractionDigits: 2});
    document.getElementById('monthly-premium').textContent = '$' + premium.monthly_premium.toLocaleString('en-US', {maximumFractionDigits: 2});
    
    // HCC Mappings Table
    const mappingsTable = document.getElementById('hcc-mappings');
    mappingsTable.innerHTML = '';
    raf.hcc_mappings.forEach(mapping => {
        const row = `
            <tr>
                <td>${mapping.icd10}</td>
                <td>${mapping.hcc_id}</td>
                <td>${mapping.hcc_name}</td>
                <td>${mapping.raf_value.toFixed(3)}</td>
            </tr>
        `;
        mappingsTable.innerHTML += row;
    });
    
    // Recommendations
    const recommendationsList = document.getElementById('recommendations');
    recommendationsList.innerHTML = '';
    report.recommendations.forEach(rec => {
        recommendationsList.innerHTML += `<li>${rec}</li>`;
    });
    
    document.getElementById('risk-results').style.display = 'block';
}

function generateReport(format) {
    if (!currentReport) {
        alert('No report to generate');
        return;
    }
    
    const payload = {
        report: currentReport,
        format: format
    };
    
    fetch('/api/generate-report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = data.download_url;
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => alert('Report generation failed: ' + error));
}

// Audit Trail
function searchAuditTrail() {
    const patientId = document.getElementById('audit-patient-id').value;
    
    if (!patientId) {
        alert('Please enter a patient ID');
        return;
    }
    
    fetch(`/api/audit-trail/${patientId}`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayAuditTrail(data.events);
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => alert('Audit search failed: ' + error));
}

function displayAuditTrail(events) {
    const eventsTable = document.getElementById('audit-events');
    eventsTable.innerHTML = '';
    
    if (events.length === 0) {
        eventsTable.innerHTML = '<tr><td colspan="4">No events found</td></tr>';
    } else {
        events.forEach(event => {
            const timestamp = new Date(event.timestamp).toLocaleString();
            const details = JSON.stringify(event).substring(0, 100) + '...';
            const row = `
                <tr>
                    <td>${timestamp}</td>
                    <td>${event.event_type}</td>
                    <td>${details}</td>
                    <td>${event.status || 'recorded'}</td>
                </tr>
            `;
            eventsTable.innerHTML += row;
        });
    }
    
    document.getElementById('audit-results').style.display = 'block';
}

function loadComplianceSummary() {
    fetch('/api/compliance-summary')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayComplianceSummary(data.summary);
        } else {
            alert('Error: ' + data.error);
        }

    })
    .catch(error => alert('Failed to load compliance summary: ' + error));
}

async function downloadActivityLog() {
    await downloadActivityFile('/api/dashboard/activity-log', 'coding_activity.jsonl');
}

async function downloadActivityLogExcel() {
    await downloadActivityFile('/api/dashboard/activity-log.xlsx', 'coding_activity.xlsx');
}

async function downloadActivityFile(endpoint, filename) {
    try {
        const response = await fetch(endpoint, {headers: authenticatedHeaders()});
        if (!response.ok) throw new Error('Activity log export is unavailable.');
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        alert(error.message);
    }
}

function displayComplianceSummary(summary) {
    const summaryDiv = document.getElementById('compliance-summary');
    summaryDiv.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
            <div style="background: #e8f5e9; padding: 15px; border-radius: 4px;">
                <div style="font-weight: bold; color: #1b5e20;">Total Calculations</div>
                <div style="font-size: 2em; color: #2e7d32;">${summary.total_calculations}</div>
            </div>
            <div style="background: #e3f2fd; padding: 15px; border-radius: 4px;">
                <div style="font-weight: bold; color: #0d47a1;">Unique Patients</div>
                <div style="font-size: 2em; color: #1565c0;">${summary.unique_patients}</div>
            </div>
            <div style="background: #fff3e0; padding: 15px; border-radius: 4px;">
                <div style="font-weight: bold; color: #e65100;">Code Modifications</div>
                <div style="font-size: 2em; color: #f57c00;">${summary.code_modifications}</div>
            </div>
            <div style="background: #fce4ec; padding: 15px; border-radius: 4px;">
                <div style="font-weight: bold; color: #880e4f;">Hierarchy Issues</div>
                <div style="font-size: 2em; color: #c2185b;">${summary.hierarchy_issues_resolved}</div>
            </div>
        </div>
    `;
    summaryDiv.style.display = 'block';
}

// HCC Reference
function loadHCCReference() {
    searchHCC();
}

let hccSearchTimer = null;

function displayHCCReference(results, query = '') {
    const table = document.getElementById('hcc-reference-table');
    const status = document.getElementById('icd-reference-status');
    table.innerHTML = '';
    if (!results.length) {
        table.innerHTML = '<tr><td colspan="3">Enter an ICD-10 code or diagnosis description to search.</td></tr>';
        if (status) status.textContent = query ? 'No matching diagnoses found.' : 'Search the official ICD-10 diagnosis workbook.';
        return;
    }
    results.forEach(item => {
        const row = `
            <tr>
                <td><strong>${escapeHTML(item.code)}</strong></td>
                <td>${escapeHTML(item.short_description)}</td>
                <td>${escapeHTML(item.description)}</td>
            </tr>
        `;
        table.innerHTML += row;
    });
    if (status) status.textContent = `${results.length} matching diagnosis${results.length === 1 ? '' : 'es'} shown${query ? ` for "${query}"` : ''}.`;
}

function searchHCC() {
    const query = document.getElementById('search-hcc').value.trim();
    clearTimeout(hccSearchTimer);
    if (!query) {
        displayHCCReference([]);
        return;
    }
    hccSearchTimer = setTimeout(async () => {
        try {
            const response = await fetch(`/api/icd-reference/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error('Search failed');
            displayHCCReference(data.results, query);
        } catch (error) {
            document.getElementById('icd-reference-status').textContent = 'ICD workbook search is unavailable.';
        }
    }, 250);
}

// Dashboard Updates
function updateDashboard() {
    if (!currentUser || !accessToken) return;
    const isCoder = ['coder', 'coder_l1', 'coder_l2'].includes(currentUser.role);
    const dashboardEndpoint = isCoder
        ? '/api/dashboard/coder'
        : '/api/dashboard/supervisor';
    Promise.all([
        fetch('/api/compliance-summary', {headers: authenticatedHeaders()}).then(response => response.json()),
        fetch(dashboardEndpoint, {headers: authenticatedHeaders()}).then(response => response.json())
    ]).then(([compliance, workflow]) => {
        if (!compliance.success || !workflow.success) throw new Error('Dashboard data unavailable');
        dashboardSnapshot = {compliance, workflow, isCoder};
        renderRoleDashboard(dashboardSnapshot);
    }).catch(error => {
        const status = document.getElementById('dashboard-refresh-status');
        if (status) {
            status.textContent = 'Unable to refresh';
            status.className = 'feedback error';
        }
        console.error('Failed to update dashboard:', error);
    });
}

function renderRoleDashboard(snapshot) {
    const {compliance, workflow, isCoder} = snapshot;
    const role = currentUser.role;
    const roleNames = {
        manager: 'Manager operations dashboard',
        supervisor: 'Supervisor operations dashboard',
        admin: 'Administration dashboard',
        master_admin: 'Administration dashboard',
        coder_l1: 'L1 coder workbench',
        coder: 'L1 coder workbench',
        coder_l2: 'L2 audit workbench'
    };
    const roleCopy = {
        manager: ['Manage throughput and quality', 'Prioritize queues, monitor production, and keep audit capacity moving.'],
        supervisor: ['Run today’s coding operation', 'Balance intake, coding output, and audit readiness from one view.'],
        admin: ['Keep the program healthy', 'Manage intake and monitor the full chart lifecycle across teams.'],
        master_admin: ['Keep the program healthy', 'Manage intake and monitor the full chart lifecycle across teams.'],
        coder_l1: ['Code with evidence', 'Claim the next chart, validate diagnoses, and submit a defensible coding record.'],
        coder: ['Code with evidence', 'Claim the next chart, validate diagnoses, and submit a defensible coding record.'],
        coder_l2: ['Audit with consistency', 'Review submitted records, confirm evidence, and move accurate charts to completion.']
    };
    const summary = compliance.summary || {};
    const title = roleNames[role] || 'HCC operations dashboard';
    const guidance = roleCopy[role] || ['Your role workspace', 'Your dashboard is scoped to the work you are allowed to perform.'];
    document.getElementById('dashboard-title').textContent = title;
    document.getElementById('dashboard-subtitle').textContent = `Signed in as ${currentUser.username} · ${guidance[0]}`;
    document.getElementById('header-role-context').textContent = guidance[1];
    document.getElementById('total-patients').textContent = isCoder
        ? (workflow.assigned_chart_ids || []).length
        : (summary.unique_patients || 0);
    document.getElementById('total-calculations').textContent = summary.total_calculations || 0;
    document.getElementById('kpi-one-label').textContent = isCoder ? 'My assigned charts' : 'Patients analyzed';
    if (isCoder && workflow.quality && typeof workflow.quality.accuracy === 'number') {
        document.getElementById('total-calculations').textContent = `${Math.round(workflow.quality.accuracy * 100)}%`;
        document.getElementById('kpi-two-label').textContent = 'L1 audit accuracy';
    } else if (isCoder) {
        document.getElementById('kpi-two-label').textContent = 'L1 audit accuracy';
        document.getElementById('total-calculations').textContent = '—';
    } else {
        document.getElementById('kpi-two-label').textContent = 'Coding submissions';
    }
    renderCoderQuality(workflow, isCoder);

    const attention = isCoder
        ? (workflow.assigned_chart_ids || []).length
        : (workflow.buckets ? workflow.buckets.bucket_1 + workflow.buckets.bucket_2 : 0);
    document.getElementById('dashboard-attention').textContent = attention;
    document.getElementById('dashboard-attention-meta').textContent = isCoder
        ? (attention ? 'Claimed work in your queue' : 'No claimed work right now')
        : 'Charts in active coding or audit';

    document.getElementById('workflow-card-title').textContent = isCoder ? 'My work queue' : 'Team workflow';
    const stage = isCoder ? (workflow.workflow_stage === 'l2' ? 'L2 audit' : 'L1 coding') : 'Operations';
    const badge = document.getElementById('workflow-stage-badge');
    badge.textContent = stage;
    badge.className = `status-badge ${workflow.workflow_stage === 'l2' ? 'status-audit' : 'status-active'}`;
    document.getElementById('workflow-summary').innerHTML = isCoder
        ? `<strong>${attention}</strong> chart${attention === 1 ? '' : 's'} assigned to you.<span>${attention ? 'Continue your current assignment or claim the next available chart.' : 'Claim a chart to start your shift.'}</span>`
        : `<strong>${workflow.buckets.bucket_1 + workflow.buckets.bucket_2 + workflow.buckets.bucket_3}</strong> charts in the pipeline.<span>${workflow.buckets.bucket_1} coding · ${workflow.buckets.bucket_2} audit · ${workflow.buckets.bucket_3} completed</span>`;
    document.getElementById('dashboard-primary-action').textContent = isCoder ? 'Open coder review' : 'Open intake & queue';
    document.getElementById('queue-count').textContent = isCoder ? `${attention} assigned` : `${workflow.queue.length} total`;
    renderQueue(snapshot);
    renderRoleGuidance(role, guidance);
    const status = document.getElementById('dashboard-refresh-status');
    status.textContent = `Updated ${new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`;
    status.className = 'feedback success';
}

function renderCoderQuality(workflow, isCoder) {
    const card = document.getElementById('coder-quality-card');
    if (!card) return;
    card.style.display = isCoder ? 'block' : 'none';
    const quality = workflow.quality || {};
    const score = document.getElementById('coder-quality-score');
    const summary = document.getElementById('coder-quality-summary');
    const records = document.getElementById('coder-quality-records');
    if (!isCoder) return;
    if (currentUser.role === 'coder_l2') {
        score.textContent = `${quality.audited_charts || 0} audited`;
        summary.innerHTML = `<span><strong>${quality.l1_errors_identified || 0}</strong> L1 errors identified</span><span><strong>${quality.changes_without_l1_error || 0}</strong> L2 changes without L1 error</span><span><strong>${quality.disputes_reversed || 0}</strong> errors reversed</span>`;
        document.getElementById('coder-quality-title').textContent = 'My audit quality';
        records.innerHTML = '';
        return;
    }
    score.textContent = quality.accuracy === null || quality.accuracy === undefined ? 'Pending' : `${Math.round(quality.accuracy * 100)}%`;
    document.getElementById('coder-quality-title').textContent = 'My coding quality';
    summary.innerHTML = `<span><strong>${quality.total_errors || 0}</strong> confirmed error${quality.total_errors === 1 ? '' : 's'}</span><span><strong>${quality.disputes_reversed || 0}</strong> error${quality.disputes_reversed === 1 ? '' : 's'} reversed</span><span><strong>${quality.audited_charts || 0}</strong> audited chart${quality.audited_charts === 1 ? '' : 's'}</span>`;
    records.innerHTML = (workflow.quality_records || []).flatMap(record =>
        [...new Set([...(record.wrong_codes || []), ...(record.missed_codes || [])])].map(code => `<div class="quality-record"><span>Chart #${record.chart_id} · ${escapeHTML(code)} marked as L1 error</span><button class="btn-link" type="button" onclick="disputeQualityError(${record.chart_id}, '${escapeHTML(code)}')">Revert error</button></div>`)
    ).join('') || '<p class="queue-note">No disputed quality errors.</p>';
}

async function disputeQualityError(chartId, code) {
    try {
        const response = await fetch('/api/dashboard/quality-dispute', {
            method: 'POST',
            headers: authenticatedHeaders(true),
            body: JSON.stringify({chart_id: chartId, code})
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Unable to reverse quality error');
        setCodeFeedback(`Quality error for ${code} was reverted.`, 'success');
        updateDashboard();
    } catch (error) {
        alert(error.message);
    }
}

function setupQueueControls() {
    ['queue-search', 'queue-status-filter'].forEach(id => {
        const control = document.getElementById(id);
        if (control) control.addEventListener('input', () => {
            if (dashboardSnapshot) renderQueue(dashboardSnapshot);
        });
    });
}

function renderQueue({workflow, isCoder}) {
    const breakdown = document.getElementById('queue-breakdown');
    const tableWrap = document.getElementById('queue-table-wrap');
    if (isCoder) {
        breakdown.innerHTML = `<div class="queue-stat"><strong>${workflow.assigned_chart_ids.length}</strong><span>assigned to you</span></div><div class="queue-stat"><strong>${workflow.claim_bucket === 2 ? 'L2' : 'L1'}</strong><span>active bucket</span></div>`;
        tableWrap.innerHTML = workflow.assigned_chart_ids.length
            ? `<p class="queue-note">Chart IDs ${workflow.assigned_chart_ids.map(id => `#${id}`).join(', ')} are assigned to your workspace.</p>`
            : '<p class="queue-note">No assigned charts. Open Coder Review to claim the next available chart.</p>';
        return;
    }
    const buckets = workflow.buckets;
    breakdown.innerHTML = [
        ['Bucket 1', buckets.bucket_1, 'coding'],
        ['Bucket 2', buckets.bucket_2, 'audit'],
        ['Bucket 3', buckets.bucket_3, 'complete']
    ].map(item => `<div class="queue-stat"><strong>${item[1]}</strong><span>${item[0]} · ${item[2]}</span></div>`).join('');
    const query = (document.getElementById('queue-search')?.value || '').trim().toLowerCase();
    const status = document.getElementById('queue-status-filter')?.value || 'all';
    const filteredQueue = workflow.queue.filter(chart => {
        const matchesQuery = !query || String(chart.chart_id).includes(query) || chart.original_filename.toLowerCase().includes(query);
        return matchesQuery && (status === 'all' || chart.status === status);
    });
    const rows = filteredQueue.slice(0, 8).map(chart => `<tr><td>#${chart.chart_id}</td><td>${escapeHTML(chart.original_filename)}</td><td><span class="status-badge status-${chart.status}">${chart.status.replace('_', ' ')}</span></td></tr>`).join('');
    tableWrap.innerHTML = rows ? `<table class="mini-queue-table"><thead><tr><th>Chart</th><th>File</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>` : '<p class="queue-note">No charts match the current filters.</p>';
}

async function loadAuditBucket() {
    const card = document.getElementById('audit-bucket-card');
    const table = document.getElementById('audit-bucket-table');
    if (!card || !table) return;
    card.style.display = 'block';
    table.innerHTML = '<p class="queue-note">Loading audited records...</p>';
    try {
        const response = await fetch('/api/dashboard/audit-bucket', {headers: authenticatedHeaders()});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Audit bucket unavailable');
        document.getElementById('audit-bucket-count').textContent = `${data.count} records`;
        const rows = data.records.map(record => `<tr><td>#${record.chart_id}</td><td>${escapeHTML(record.category || 'Uncategorized')}</td><td>${escapeHTML((record.codes || []).join(', ') || 'No codes')}</td><td>${record.audited_at ? new Date(record.audited_at).toLocaleDateString() : '-'}</td></tr>`).join('');
        table.innerHTML = rows
            ? `<table class="mini-queue-table"><thead><tr><th>Chart</th><th>Category</th><th>ICD-10</th><th>Audited</th></tr></thead><tbody>${rows}</tbody></table>`
            : '<p class="queue-note">No audited records are available yet.</p>';
    } catch (error) {
        table.innerHTML = `<p class="feedback error">${escapeHTML(error.message)}</p>`;
    }
}

function renderRoleGuidance(role, guidance) {
    document.getElementById('role-guidance-title').textContent = guidance[0];
    document.getElementById('role-guidance-copy').textContent = guidance[1];
    const items = ['Keep evidence attached to every accepted diagnosis.', 'Use the HCC Reference for code context before submission.', 'Leave a clear audit trail for every exception.'];
    if (role === 'coder_l2') items[0] = 'Verify MEAT evidence and page references before approving.';
    if (['manager', 'supervisor', 'admin', 'master_admin'].includes(role)) items[0] = 'Watch Bucket 2 closely so completed coding does not stall in audit.';
    document.getElementById('role-guidance-list').innerHTML = items.map(item => `<span>✓ ${item}</span>`).join('');
}

function openPrimaryDashboardAction() {
    switchTab(['coder', 'coder_l1', 'coder_l2'].includes(currentUser.role) ? 'coder' : 'upload');
}

// Auto-update dashboard every 30 seconds
setInterval(updateDashboard, 30000);

// Coder review validation and suggestions
function setupCoderValidation() {
    const input = document.getElementById('new-code-input');
    const suggestions = document.getElementById('icd-suggestions');
    const feedback = document.getElementById('code-feedback');

    if (!input || !suggestions || !feedback) {
        return;
    }

    input.addEventListener('input', () => {
        const code = input.value.trim();
        if (!code) {
            suggestions.style.display = 'none';
            suggestions.innerHTML = '';
            setCodeFeedback('', 'muted');
            return;
        }

        clearTimeout(coderValidationTimer);
        coderValidationTimer = setTimeout(() => validateCodeInput(code), 250);
    });

    suggestions.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-code]');
        if (!button) {
            return;
        }
        input.value = button.dataset.code;
        suggestions.style.display = 'none';
        suggestions.innerHTML = '';
        validateCodeInput(input.value.trim());
    });
}

async function validateCodeInput(code) {
    const input = document.getElementById('new-code-input');
    const suggestions = document.getElementById('icd-suggestions');
    const feedback = document.getElementById('code-feedback');

    if (!input || !suggestions || !feedback) {
        return { valid: false, suggestions: [] };
    }

    if (!code) {
        setCodeFeedback('', 'muted');
        suggestions.style.display = 'none';
        suggestions.innerHTML = '';
        return { valid: false, suggestions: [] };
    }

    try {
        const response = await fetch('/api/charts/validate-code', {
            method: 'POST',
            headers: authenticatedHeaders(true),
            body: JSON.stringify({ code })
        });
        const data = await response.json();

        if (!data.success) {
            setCodeFeedback('Unable to validate code right now.', 'error');
            return { valid: false, suggestions: [] };
        }

        if (data.valid) {
            setCodeFeedback('Valid ICD-10 format.', 'success');
        } else {
            setCodeFeedback('Use a standard ICD-10 format like E11.9 or I10.', 'error');
        }

        if (data.suggestions && data.suggestions.length > 0) {
            suggestions.innerHTML = data.suggestions.map(item => `<button type="button" data-code="${item}">${item}</button>`).join('');
            suggestions.style.display = 'block';
        } else {
            suggestions.style.display = 'none';
            suggestions.innerHTML = '';
        }

        return { valid: data.valid, suggestions: data.suggestions || [] };
    } catch (error) {
        setCodeFeedback('Validation unavailable.', 'error');
        return { valid: false, suggestions: [] };
    }
}

function setCodeFeedback(message, kind = 'muted') {
    const feedback = document.getElementById('code-feedback');
    if (!feedback) {
        return;
    }
    feedback.textContent = message;
    feedback.className = `feedback ${kind}`;
}

function claimChart() {
    fetch('/api/charts/claim', {
        method: 'POST',
        headers: authenticatedHeaders(true),
        body: JSON.stringify({})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.chart) {
            const chart = data.chart;
            loadClaimedChart(chart.chart_id);
        } else {
            alert('No charts available to claim');
        }
    })
    .catch(err => alert('Claim failed: ' + err));
}

async function restoreCoderChart() {
    if (!currentUser || !['coder', 'coder_l1', 'coder_l2'].includes(currentUser.role) || !accessToken) return;
    try {
        const response = await fetch('/api/charts/current', {headers: authenticatedHeaders()});
        const data = await response.json();
        if (response.ok && data.success && data.chart) loadClaimedChart(data.chart.chart_id);
    } catch (error) {
        // The coder can still use the claim button if the restore request is unavailable.
    }
}

function renderEncounters(encounters) {
    const list = document.getElementById('encounter-list');
    const select = document.getElementById('encounter-select');
    if (!list || !select) return;
    list.innerHTML = encounters.length
        ? encounters.map(item => `<div class="encounter-row"><strong>${escapeHTML(item.date_of_service)}</strong><span>${escapeHTML(item.provider || 'Provider not entered')}</span><span>${(item.codes || []).length} code${(item.codes || []).length === 1 ? '' : 's'}</span></div>`).join('')
        : '<span class="feedback muted">No encounter lines yet.</span>';
    select.innerHTML = encounters.map(item => `<option value="${escapeHTML(item.encounter_id)}">${escapeHTML(item.date_of_service)} · ${escapeHTML(item.provider || 'Encounter')}</option>`).join('');
    select.disabled = !encounters.length;
}

async function createEncounter() {
    const chartId = document.getElementById('claimed-chart-id').textContent;
    const dateOfService = document.getElementById('encounter-date').value;
    if (!dateOfService) {
        document.getElementById('encounter-feedback').textContent = 'Enter a date of service.';
        return;
    }
    const response = await fetch(`/api/charts/${chartId}/encounters`, {
        method: 'POST',
        headers: authenticatedHeaders(true),
        body: JSON.stringify({
            date_of_service: dateOfService,
            provider: document.getElementById('encounter-provider').value,
            place_of_service: document.getElementById('encounter-place').value
        })
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
        document.getElementById('encounter-feedback').textContent = data.error || 'Unable to create encounter line.';
        return;
    }
    const current = Array.from(document.querySelectorAll('#encounter-select option')).map(option => ({
        encounter_id: option.value,
        date_of_service: option.textContent.split(' · ')[0],
        provider: option.textContent.split(' · ')[1] || '',
        codes: []
    }));
    current.push(data.encounter);
    renderEncounters(current);
    document.getElementById('encounter-date').value = '';
    document.getElementById('encounter-provider').value = '';
    document.getElementById('encounter-place').value = '';
    document.getElementById('encounter-feedback').textContent = 'Encounter line created. Select it before adding a code.';
}

async function loadWipCount() {
    try {
        const response = await fetch('/api/charts/wip', {headers: authenticatedHeaders()});
        const data = await response.json();
        if (response.ok && data.success) {
            const count = document.getElementById('wip-count');
            if (count) count.textContent = `WIP ${data.count}/${data.limit}`;
            const list = document.getElementById('wip-list');
            if (list) {
                list.innerHTML = data.charts.length
                    ? `<strong>My WIP (${data.count}/${data.limit})</strong> ${data.charts.map(chart => `<button type="button" class="wip-chart" data-chart-id="${chart.chart_id}">#${chart.chart_id} ${escapeHTML(chart.original_filename)} · ${escapeHTML(chart.status)}</button>`).join('')}`
                    : `<span class="feedback muted">My WIP is empty (${data.remaining} slots available).</span>`;
                list.querySelectorAll('.wip-chart').forEach(button => button.addEventListener('click', () => loadClaimedChart(button.dataset.chartId)));
            }
        }
    } catch (error) {
        // WIP status is informative; claiming remains available if this request fails.
    }
}

function openCoderWindow() {
    const tab = window.open(`${window.location.origin}/?tab=coder`, '_blank', 'noopener');
    if (!tab) setCodeFeedback('Allow pop-ups to open the coding workspace in a new tab.', 'error');
}

function renderL2AuditPanel(l1Codes, auditQuality) {
    const panel = document.getElementById('l2-audit-panel');
    const list = document.getElementById('l1-code-review');
    if (!panel || !list) return;
    const isL2 = currentUser && currentUser.role === 'coder_l2';
    panel.style.display = isL2 ? 'block' : 'none';
    if (!isL2) return;
    document.getElementById('l1-code-count').textContent = `${l1Codes.length} L1 line${l1Codes.length === 1 ? '' : 's'}`;
    const removedCodes = l1Codes.filter(code => !claimedCodes.includes(code));
    list.innerHTML = claimedCodes.length || removedCodes.length
        ? claimedCodes.map(code => `<span class="code-review-chip">${escapeHTML(code)}<button type="button" data-remove-code="${escapeHTML(code)}" aria-label="Remove ${escapeHTML(code)}">×</button></span>`).join('') +
            removedCodes.map(code => `<span class="code-review-chip code-review-removed">${escapeHTML(code)}<select data-audit-code="${escapeHTML(code)}"><option value="l1_error">L1 error</option><option value="l2_change">L2 change</option></select></span>`).join('')
        : '<span class="feedback muted">No codes submitted by L1.</span>';
    list.querySelectorAll('button[data-remove-code]').forEach(button => button.addEventListener('click', () => {
        if (l1Codes.includes(button.dataset.removeCode) && !auditWrongCodes.includes(button.dataset.removeCode)) {
            auditWrongCodes.push(button.dataset.removeCode);
        }
        auditDecisions[button.dataset.removeCode] = 'l1_error';
        claimedCodes = claimedCodes.filter(code => code !== button.dataset.removeCode);
        renderL2AuditPanel(l1Codes, auditQuality);
    }));
    list.querySelectorAll('select[data-audit-code]').forEach(select => {
        select.value = auditDecisions[select.dataset.auditCode] || 'l1_error';
        select.addEventListener('change', () => {
            auditDecisions[select.dataset.auditCode] = select.value;
        });
    });
    const preview = document.getElementById('audit-quality-preview');
    if (preview) preview.textContent = auditQuality.accuracy !== undefined
        ? `Previous audit accuracy: ${Math.round(auditQuality.accuracy * 100)}%`
        : 'Accuracy is calculated when this audit is submitted.';
}

function loadClaimedChart(chartId) {
    setCodeFeedback('', 'muted');
    document.getElementById('icd-suggestions').style.display = 'none';
    document.getElementById('icd-suggestions').innerHTML = '';
    fetch(`/api/charts/${chartId}`, {headers: authenticatedHeaders()})
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            document.getElementById('claimed-chart').style.display = 'block';
            document.getElementById('claimed-chart-id').textContent = data.chart.chart_id;
            document.getElementById('claimed-filename').textContent = data.chart.original_filename || data.chart.file_path;
            claimedCodes = data.latest_risk_input.captured_icd10_codes || [];
            auditL1Codes = data.latest_risk_input.l1_captured_icd10_codes || [];
            auditWrongCodes = [];
            auditDecisions = {};
            renderL2AuditPanel(auditL1Codes, data.latest_risk_input.audit_quality || {});
            renderEncounters(data.latest_risk_input.encounters || []);
            loadWipCount();

            loadChartPreview(chartId);

            const nlpResult = data.latest_risk_input.nlp_result || {};
            renderNLPReview(nlpResult, (data.latest_risk_input.user_inputs || {}).diagnosis_decisions || {});

        } else {
            alert('Failed to load chart');
        }

        function renderL2AuditPanel(l1Codes, auditQuality) {
            const panel = document.getElementById('l2-audit-panel');
            const list = document.getElementById('l1-code-review');
            if (!panel || !list) return;
            const isL2 = currentUser && currentUser.role === 'coder_l2';
            panel.style.display = isL2 ? 'block' : 'none';
            if (!isL2) return;
            document.getElementById('l1-code-count').textContent = `${l1Codes.length} L1 line${l1Codes.length === 1 ? '' : 's'}`;
            const removedCodes = l1Codes.filter(code => !claimedCodes.includes(code));
            list.innerHTML = claimedCodes.length || removedCodes.length
                ? claimedCodes.map(code => `<span class="code-review-chip">${escapeHTML(code)}<button type="button" data-remove-code="${escapeHTML(code)}" aria-label="Remove ${escapeHTML(code)}">×</button></span>`).join('') +
                    removedCodes.map(code => `<span class="code-review-chip code-review-removed">${escapeHTML(code)}<select data-audit-code="${escapeHTML(code)}"><option value="l1_error">L1 error</option><option value="l2_change">L2 change</option></select></span>`).join('')
                : '<span class="feedback muted">No codes submitted by L1.</span>';
            list.querySelectorAll('button[data-remove-code]').forEach(button => button.addEventListener('click', () => {
                if (l1Codes.includes(button.dataset.removeCode) && !auditWrongCodes.includes(button.dataset.removeCode)) {
                    auditWrongCodes.push(button.dataset.removeCode);
                }
                auditDecisions[button.dataset.removeCode] = 'l1_error';
                claimedCodes = claimedCodes.filter(code => code !== button.dataset.removeCode);
                renderL2AuditPanel(l1Codes, auditQuality);
            }));
            list.querySelectorAll('select[data-audit-code]').forEach(select => {
                select.value = auditDecisions[select.dataset.auditCode] || 'l1_error';
                select.addEventListener('change', () => {
                    auditDecisions[select.dataset.auditCode] = select.value;
                });
            });
            const preview = document.getElementById('audit-quality-preview');
            if (auditQuality.accuracy !== undefined) {
                preview.textContent = `Previous audit accuracy: ${Math.round(auditQuality.accuracy * 100)}%`;
            } else {
                preview.textContent = 'Accuracy is calculated when this audit is submitted.';
            }
        }
    })
    .catch(err => alert('Load failed: ' + err));
}

function toggleCoderFullscreen() {
    const workspace = document.getElementById('coder');
    const button = document.getElementById('coder-fullscreen-button');
    if (!workspace || !button) return;
    if (document.fullscreenElement) {
        document.exitFullscreen();
        return;
    }

    function openCoderWindow() {
        const tab = window.open(`${window.location.origin}/?tab=coder`, '_blank', 'noopener');
        if (!tab) setCodeFeedback('Allow pop-ups to open the coding workspace in a new tab.', 'error');
    }
    workspace.requestFullscreen().catch(() => workspace.classList.toggle('workspace-fullscreen'));
}

document.addEventListener('fullscreenchange', () => {
    const button = document.getElementById('coder-fullscreen-button');
    if (button) button.textContent = document.fullscreenElement ? 'Exit Full Screen' : 'Enter Full Screen';
});

function toggleDiagnosisEvidence() {
    const evidence = document.getElementById('diagnosis-evidence');
    const button = document.getElementById('diagnosis-evidence-button');
    const status = document.getElementById('pdf-review-status');
    if (!evidence || !button) return;
    evidence.hidden = !evidence.hidden;
    button.textContent = evidence.hidden ? 'Show diagnosis highlights' : 'Hide diagnosis highlights';
    if (status) status.textContent = evidence.hidden ? 'PDF document' : 'Diagnosis evidence shown below PDF';
}

async function loadChartPreview(chartId) {
    const preview = document.getElementById('chart-preview-frame');
    if (!preview) return;
    try {
        const response = await fetch(`/api/charts/${chartId}/file`, {headers: authenticatedHeaders()});
        if (!response.ok) throw new Error('Chart file unavailable');
        const highlightCount = response.headers.get('X-Diagnosis-Highlights');
        const status = document.getElementById('pdf-review-status');
        if (status) status.textContent = highlightCount
            ? `PDF document · ${highlightCount} diagnosis highlight(s)`
            : 'PDF document · no matching text highlights';
        const blob = await response.blob();
        if (preview.dataset.objectUrl) URL.revokeObjectURL(preview.dataset.objectUrl);
        preview.dataset.objectUrl = URL.createObjectURL(blob);
        preview.src = preview.dataset.objectUrl;
        preview.onload = () => {
            const status = document.getElementById('pdf-review-status');
            if (status) status.textContent = 'PDF document ready';
        };
        preview.onerror = () => {
            setCodeFeedback('The chart PDF could not be displayed by the browser.', 'error');
        };
    } catch (error) {
        preview.removeAttribute('src');
        setCodeFeedback('Chart PDF is unavailable. Ask intake to re-upload this chart.', 'error');
    }
}

function escapeHTML(value) {
    return String(value).replace(/[&<>'"]/g, character => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[character]));
}

function highlightDiagnoses(text, medicalEntities) {
    let highlighted = escapeHTML(text);
    const conditions = medicalEntities.medical_conditions || [];
    conditions.forEach(condition => {
        const safeCondition = escapeHTML(condition);
        const pattern = new RegExp(`(${safeCondition.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')})`, 'gi');
        highlighted = highlighted.replace(pattern, '<mark class="diagnosis-highlight">$1</mark>');
    });
    return highlighted;
}

function renderNLPReview(nlpResult, savedDecisions = {}) {
    const container = document.getElementById('nlp-suggestions');
    const conditions = (nlpResult.entities || []).filter(entity => entity.type === 'condition');
    const detectedCodes = (nlpResult.entities || []).filter(entity => entity.type === 'icd10');
    if (!conditions.length && !detectedCodes.length) {
        container.textContent = 'No diagnosis suggestions found. Review the chart manually.';
        return;
    }
    const conditionMarkup = conditions.map(condition => {
        const suggestions = condition.icd10_suggestions || [];
        const workbookMatches = condition.workbook_matches || [];
        const allSuggestions = [...suggestions, ...workbookMatches.filter(match => !suggestions.some(item => item.code === match.code))];
        const codes = allSuggestions.map(item => item.code).join(', ') || 'No mapped ICD-10 code';
        const similar = workbookMatches.length
            ? `<br><small>Similar ICD-10 codes: ${workbookMatches.map(item => `${item.code} (${Math.round(item.similarity * 100)}% match)`).join(', ')}</small>`
            : '';
        const meat = condition.meat_evidence || [];
        const meatSummary = meat.length
            ? `<div class="meat-evidence"><strong>MEAT evidence:</strong> ${meat.map(item => `${item.type} · page ${item.page_number}`).join(', ')}</div>`
            : '<div class="meat-warning">MEAT evidence not found. Verify the chart before adding this code.</div>';
        const encodedDiagnosis = encodeURIComponent(condition.name);
        const encodedSuggestions = encodeURIComponent(JSON.stringify(allSuggestions));
        const encodedMeatEvidence = encodeURIComponent(JSON.stringify(meat));
        const saved = savedDecisions[condition.name] || {};
        const defaultCode = saved.icd10_code || (allSuggestions[0] && allSuggestions[0].code) || '';
        const pageNumber = saved.page_number || '';
        return `<div class="nlp-suggestion" data-diagnosis="${encodedDiagnosis}"><strong>${escapeHTML(condition.name)}</strong> <span>${Math.round((condition.confidence || 0) * 100)}% confidence</span><button type="button" class="view-in-pdf" data-term="${encodedDiagnosis}">View in PDF</button><br><small>${escapeHTML(codes)}</small>${similar}${meatSummary}<div class="diagnosis-edit-fields"><label>ICD-10 code <input class="diagnosis-code-input" value="${escapeHTML(defaultCode)}" placeholder="E11.9"></label><label>Page no. <input class="diagnosis-page-input" type="number" min="1" value="${escapeHTML(pageNumber)}" placeholder="1"></label></div><div class="diagnosis-actions"><button type="button" class="decision-choice accept-choice" data-decision="accepted">Add</button><button type="button" class="decision-choice reject-choice" data-decision="rejected">ASR</button><select class="comment-select" disabled><option value="">Select reason</option></select><button type="button" class="save-decision" data-diagnosis="${encodedDiagnosis}" data-suggestions="${encodedSuggestions}" data-meat-evidence="${encodedMeatEvidence}">Save</button><span class="decision-status"></span></div></div>`;
    }).join('');
    const codeMarkup = detectedCodes.map(entity => {
        const mapping = entity.hcc && typeof entity.hcc === 'object' ? entity.hcc : {};
        return `<div class="nlp-suggestion nlp-detected-code"><strong>${escapeHTML(entity.code)}</strong> · ${escapeHTML(entity.description || 'Detected ICD-10 code')}<br><small>Detected in chart${mapping.hcc_code ? ` · ${escapeHTML(mapping.hcc_code)}` : ''}</small></div>`;
    }).join('');
    container.innerHTML = conditionMarkup + codeMarkup;
    container.querySelectorAll('.decision-choice').forEach(choice => {
        choice.addEventListener('click', () => {
            const reason = choice.parentElement.querySelector('.comment-select');
            const decision = choice.dataset.decision;
            reason.disabled = false;
            reason.innerHTML = decision === 'accepted'
                ? '<option value="">Select reason</option><option value="support">Support</option><option value="without_support">Without support</option>'
                : '<option value="">Select reason</option><option value="unconfirmed_diagnosis">Unconfirmed diagnosis</option><option value="conflicting_diagnosis">Conflicting diagnosis</option>';
            choice.parentElement.querySelectorAll('.decision-choice').forEach(item => item.classList.toggle('selected', item === choice));
            choice.parentElement.dataset.decision = decision;
        });
    });
    container.querySelectorAll('.nlp-suggestion').forEach(suggestion => {
        const decision = savedDecisions[decodeURIComponent(suggestion.dataset.diagnosis)];
        if (!decision) return;
        const commentSelect = suggestion.querySelector('.comment-select');
        const decisionChoice = suggestion.querySelector(`[data-decision="${decision.decision}"]`);
        if (decisionChoice) decisionChoice.click();
        commentSelect.value = decision.secondary_comment || '';
        suggestion.dataset.secondaryComment = decision.secondary_comment || '';
        suggestion.dataset.decision = decision.decision;
        suggestion.querySelector('.decision-status').textContent = `${decision.decision === 'accepted' ? 'Accepted' : 'Rejected'}: ${(decision.secondary_comment || '').replaceAll('_', ' ')}`;
        suggestion.querySelector('.decision-status').className = `decision-status ${decision.decision}`;
    });
    container.querySelectorAll('.save-decision').forEach(button => {
        button.addEventListener('click', () => saveDiagnosisDecision(button));
    });
    container.querySelectorAll('.view-in-pdf').forEach(button => {
        button.addEventListener('click', () => focusDiagnosisInPdf(decodeURIComponent(button.dataset.term)));
    });
}

async function focusDiagnosisInPdf(term) {
    const chartId = document.getElementById('claimed-chart-id').textContent;
    const preview = document.getElementById('chart-preview-frame');
    const status = document.getElementById('pdf-review-status');
    if (!preview || !chartId) return;
    try {
        const response = await fetch(`/api/charts/${chartId}/file?term=${encodeURIComponent(term)}`, {headers: authenticatedHeaders()});
        if (!response.ok) throw new Error('Selected diagnosis was not found in the PDF text.');
        const page = response.headers.get('X-Diagnosis-Page') || '1';
        const count = response.headers.get('X-Diagnosis-Highlights') || '0';
        const blob = await response.blob();
        if (preview.dataset.objectUrl) URL.revokeObjectURL(preview.dataset.objectUrl);
        preview.dataset.objectUrl = URL.createObjectURL(blob);
        preview.src = `${preview.dataset.objectUrl}#page=${page}`;
        if (status) status.textContent = `${term} · ${count} highlight(s) · page ${page}`;
    } catch (error) {
        setCodeFeedback(error.message, 'error');
    }
}

async function saveDiagnosisDecision(button) {
    const chartId = document.getElementById('claimed-chart-id').textContent;
    const diagnosis = decodeURIComponent(button.dataset.diagnosis);
    const suggestions = JSON.parse(decodeURIComponent(button.dataset.suggestions));
    const meatEvidence = JSON.parse(decodeURIComponent(button.dataset.meatEvidence || '%5B%5D'));
    const decision = button.parentElement.dataset.decision || '';
    const secondaryComment = button.parentElement.querySelector('.comment-select').value;
    const code = button.closest('.nlp-suggestion').querySelector('.diagnosis-code-input').value.trim().toUpperCase();
    const pageNumberValue = button.closest('.nlp-suggestion').querySelector('.diagnosis-page-input').value;
    const pageNumber = pageNumberValue ? Number(pageNumberValue) : null;
    const status = button.parentElement.querySelector('.decision-status');
    if (!decision || !secondaryComment) {
        status.textContent = 'Select a decision and reason.';
        status.className = 'decision-status error';
        return;
    }
    try {
        const response = await fetch(`/api/charts/${chartId}/diagnosis-decision`, {
            method: 'POST',
            headers: authenticatedHeaders(true),
            body: JSON.stringify({ diagnosis, decision, secondary_comment: secondaryComment, icd10_code: code, page_number: pageNumber, meat_evidence: meatEvidence, icd10_suggestions: suggestions })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Unable to save decision');
        if (decision === 'accepted' && code && !claimedCodes.includes(code)) claimedCodes.push(code);
        button.closest('.nlp-suggestion').dataset.secondaryComment = secondaryComment;
        status.textContent = `${decision === 'accepted' ? 'Accepted' : 'Rejected'}: ${secondaryComment.replaceAll('_', ' ')}`;
        status.className = `decision-status ${decision}`;
    } catch (error) {
        status.textContent = error.message;
        status.className = 'decision-status error';
    }
}

async function loadICDEvidence() {
    const chartId = document.getElementById('claimed-chart-id').textContent;
    const panel = document.getElementById('icd-evidence-panel');
    const list = document.getElementById('icd-evidence-list');
    try {
        const response = await fetch(`/api/charts/${chartId}/icd-evidence`, {headers: authenticatedHeaders()});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Unable to load ICD evidence');
        list.innerHTML = data.evidence.length ? data.evidence.map(item => `<div class="icd-evidence-row"><strong>${escapeHTML(item.icd10_code)}</strong> <span>${escapeHTML(item.description)}</span><br><small>Category: ${escapeHTML(item.category)} · Page(s): ${item.page_numbers.length ? item.page_numbers.join(', ') : 'not found'}</small><button type="button" class="view-in-pdf" data-term="${encodeURIComponent(item.icd10_code)}">View in PDF</button></div>`).join('') : '<p>No ICD diagnosis evidence found.</p>';
        list.querySelectorAll('.view-in-pdf').forEach(button => button.addEventListener('click', () => focusDiagnosisInPdf(decodeURIComponent(button.dataset.term))));
        panel.hidden = false;
    } catch (error) {
        setCodeFeedback(error.message, 'error');
    }
}

async function addCodeToChart() {
    const chartId = document.getElementById('claimed-chart-id').textContent;
    const code = document.getElementById('new-code-input').value.trim();
    const encounterId = document.getElementById('encounter-select').value;
    if (!code) {
        setCodeFeedback('Enter an ICD-10 code to add.', 'error');
        return;
    }
    if (!encounterId) {
        setCodeFeedback('Create and select an encounter line before adding a code.', 'error');
        return;
    }

    const validation = await validateCodeInput(code);
    if (!validation.valid) {
        setCodeFeedback('Use a valid ICD-10 code before submitting.', 'error');
        return;
    }

    if (currentUser && currentUser.role === 'coder_l2') {
        if (!claimedCodes.includes(code)) claimedCodes.push(code);
        auditDecisions[code] = 'l2_change';
        renderL2AuditPanel(auditL1Codes, {});
        document.getElementById('new-code-input').value = '';
        setCodeFeedback(`Missed code ${code} added for audit.`, 'success');
        return;
    }
    try {
        const response = await fetch(`/api/charts/${chartId}/add-code`, {
            method: 'POST',
            headers: authenticatedHeaders(true),
            body: JSON.stringify({ code: code, encounter_id: encounterId })
        });
        const data = await response.json();

        if (data.success) {
            claimedCodes = data.captured_icd10_codes;
            const el = document.getElementById('add-code-result');
            el.style.display = 'block';
            el.textContent = 'Code added: ' + code;
            setTimeout(() => el.style.display = 'none', 3000);
            document.getElementById('new-code-input').value = '';
            setCodeFeedback('Code added successfully.', 'success');
        } else {
            setCodeFeedback('Add code failed: ' + (data.error || 'unknown'), 'error');
        }
    } catch (err) {
        setCodeFeedback('Add failed: ' + err, 'error');
    }
}

async function submitCoding() {
    const chartId = parseInt(document.getElementById('claimed-chart-id').textContent, 10);
    if (!chartId) {
        setCodeFeedback('Claim a chart before submitting.', 'error');
        return;
    }
    const codes = claimedCodes;

    const decisions = {};
    document.querySelectorAll('#nlp-suggestions .nlp-suggestion').forEach(suggestion => {
        const diagnosis = decodeURIComponent(suggestion.dataset.diagnosis);
        const decision = suggestion.dataset.decision || '';
        const secondaryComment = suggestion.dataset.secondaryComment || '';
        if (decision) decisions[diagnosis] = {decision, secondary_comment: secondaryComment};
    });
    const wrongL1Codes = currentUser && currentUser.role === 'coder_l2' ? auditWrongCodes : [];
    const auditDecisionPayload = currentUser && currentUser.role === 'coder_l2'
        ? Object.entries(auditDecisions).map(([code, classification]) => ({code, classification}))
        : [];
    const payload = {
        chart_id: chartId,
        user_inputs: { coder_note: 'submitted from UI', diagnosis_decisions: decisions, wrong_l1_codes: wrongL1Codes, audit_decisions: auditDecisionPayload },
        captured_icd10_codes: codes,
        mapped_hcc_versions: [],
        calculated_raf_score: null
    };

    try {
        const response = await fetch('/api/dashboard/submit', {
            method: 'POST',
            headers: authenticatedHeaders(true),
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'unknown');
        document.getElementById('claimed-chart').classList.add('submitted');
        document.querySelector('#claimed-chart button[onclick="submitCoding()"]')?.setAttribute('disabled', 'disabled');
        if (data.audit_quality && data.audit_quality.accuracy !== undefined) {
            setCodeFeedback(`Audit submitted. L1 accuracy: ${Math.round(data.audit_quality.accuracy * 100)}% (${data.audit_quality.total_errors} error${data.audit_quality.total_errors === 1 ? '' : 's'}).`, 'success');
        } else {
            setCodeFeedback('Coding submitted. Chart is now waiting for L2 audit.', 'success');
        }
    } catch (error) {
        setCodeFeedback('Submit failed: ' + error.message, 'error');
    }
}
