// Insurance Risk Adjustment Tool - Frontend Logic

let currentReport = null;
let coderValidationTimer = null;
let accessToken = sessionStorage.getItem('access_token') || '';
let currentUser = JSON.parse(sessionStorage.getItem('current_user') || 'null');
let claimedCodes = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    if (!accessToken || !currentUser) {
        window.location.replace('/login');
        return;
    }
    setupTabNavigation();
    setupFileUpload();
    setupCoderValidation();
    loadHCCReference();
    updateDashboard();
    updateSessionUI();
    restoreCoderChart();
});

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
    document.querySelectorAll('.role-supervisor').forEach(element => {
        element.style.display = authenticated && ['supervisor', 'admin', 'master_admin'].includes(currentUser.role) ? '' : 'none';
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
    event.target.classList.add('active');
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
    fetch('/api/compliance-summary')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('total-calculations').textContent = data.summary.total_calculations;
            document.getElementById('total-patients').textContent = data.summary.unique_patients;
        }
    })
    .catch(error => console.log('Failed to update dashboard:', error));
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
    if (!currentUser || currentUser.role !== 'coder' || !accessToken) return;
    try {
        const response = await fetch('/api/charts/current', {headers: authenticatedHeaders()});
        const data = await response.json();
        if (response.ok && data.success && data.chart) loadClaimedChart(data.chart.chart_id);
    } catch (error) {
        // The coder can still use the claim button if the restore request is unavailable.
    }
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

            loadChartPreview(chartId);

            const nlpResult = data.latest_risk_input.nlp_result || {};
            renderNLPReview(nlpResult, (data.latest_risk_input.user_inputs || {}).diagnosis_decisions || {});

        } else {
            alert('Failed to load chart');
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
    } catch (error) {
        preview.removeAttribute('src');
        setCodeFeedback('Chart preview unavailable. Use diagnosis evidence review.', 'error');
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
    if (!conditions.length) {
        container.textContent = 'No diagnosis suggestions found. Review the chart manually.';
        return;
    }
    container.innerHTML = conditions.map(condition => {
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
    if (!code) {
        setCodeFeedback('Enter an ICD-10 code to add.', 'error');
        return;
    }

    const validation = await validateCodeInput(code);
    if (!validation.valid) {
        setCodeFeedback('Use a valid ICD-10 code before submitting.', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/charts/${chartId}/add-code`, {
            method: 'POST',
            headers: authenticatedHeaders(true),
            body: JSON.stringify({ code: code })
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
    const payload = {
        chart_id: chartId,
        user_inputs: { coder_note: 'submitted from UI', diagnosis_decisions: decisions },
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
        setCodeFeedback('Coding submitted successfully. Chart marked completed.', 'success');
    } catch (error) {
        setCodeFeedback('Submit failed: ' + error.message, 'error');
    }
}
