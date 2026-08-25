"""
Flask Web Application for Insurance Risk Adjustment Tool - v2.0
Advanced HCC Medical Coding Tool with ML-based code prediction
"""

from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import logging
from datetime import datetime
from src.ocr_module import extract_text_from_pdf
from src.nlp_identifier_v3 import extract_nlp_insights
from src.risk_adjustment import RiskAdjustmentCalculator
from src.audit_logger import AuditLogger
from src.report_generator import ReportGenerator
from src.ml_model import HCCPredictionModel
from src.icd_mapper import ICD10Mapper
from src.hcc_engine import HCC_MAPPINGS, detect_hierarchy_issues
from src.icd_diagnosis_matcher import get_icd_diagnosis_matcher
from backend.app.api.auth.auth_routes import bp as auth_blueprint
from backend.app.api.charts.chart_routes import bp as charts_blueprint
from backend.app.api.cms.cms_routes import bp as cms_blueprint
from backend.app.api.dashboard.dashboard_routes import bp as dashboard_blueprint
from backend.app.core.db import engine
from backend.app.db_models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max upload
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['REPORT_FOLDER'] = 'reports'

app.register_blueprint(auth_blueprint)
app.register_blueprint(charts_blueprint)
app.register_blueprint(cms_blueprint)
app.register_blueprint(dashboard_blueprint)
Base.metadata.create_all(bind=engine)

# Create folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
os.makedirs('audit_logs', exist_ok=True)

# Initialize components
audit_logger = AuditLogger()
report_generator = ReportGenerator()
ml_model = HCCPredictionModel()
icd_mapper = ICD10Mapper()


@app.route('/')
def index():
    """Dashboard home page"""
    return render_template('index.html')


@app.route('/login')
def login_page():
    """Dedicated authentication page."""
    return render_template('login.html')


@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    """Handle PDF upload and OCR processing with medical entity extraction"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400
        
        # Save uploaded file
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        logger.info(f"Processing PDF: {filename}")
        
        # Extract text from PDF
        ocr_text = extract_text_from_pdf(filepath)
        
        # Extract medical entities
        nlp_results = extract_nlp_insights(ocr_text)
        
        # Get HCC predictions from ML model
        predictions = ml_model.predict_hcc_codes(nlp_results['entities'])
        
        return jsonify({
            'success': True,
            'filename': filename,
            'ocr_text': ocr_text[:1000] + '...' if len(ocr_text) > 1000 else ocr_text,
            'entities': nlp_results['entities'],
            'document_type': nlp_results['document_type'],
            'confidence': nlp_results.get('confidence', 0.7),
            'hcc_predictions': predictions[:5]  # Top 5 predictions
        })
    
    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        return jsonify({'error': f'Processing error: {str(e)}'}), 500


@app.route('/api/predict-hcc', methods=['POST'])
def predict_hcc():
    """Predict HCC codes based on medical entities"""
    try:
        data = request.json
        medical_entities = data.get('entities', {})
        
        # Get predictions
        predictions = ml_model.predict_hcc_codes(medical_entities)
        
        return jsonify({
            'success': True,
            'predictions': predictions,
            'count': len(predictions)
        })
    except Exception as e:
        logger.error(f"HCC prediction error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/validate-icd10/<code>', methods=['GET'])
def validate_icd10(code):
    """Validate ICD-10 code"""
    try:
        is_valid, message = icd_mapper.validate_icd10_code(code)
        description = icd_mapper.get_icd10_description(code)
        hcc = icd_mapper.get_hcc_from_icd10(code)
        
        return jsonify({
            'success': True,
            'code': code,
            'valid': is_valid,
            'message': message,
            'description': description,
            'hcc': hcc
        })
    except Exception as e:
        logger.error(f"ICD-10 validation error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/find-icd10/<condition>', methods=['GET'])
def find_icd10(condition):
    """Find ICD-10 codes by condition"""
    try:
        codes = icd_mapper.find_icd10_by_condition(condition)
        return jsonify({
            'success': True,
            'condition': condition,
            'codes': codes,
            'count': len(codes)
        })
    except Exception as e:
        logger.error(f"ICD-10 search error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/calculate-risk', methods=['POST'])
def calculate_risk():
    """Calculate risk adjustment factors with advanced analysis"""
    try:
        data = request.json
        
        # Validate input
        icd10_codes = data.get('icd10_codes', [])
        if not icd10_codes:
            return jsonify({'error': 'At least one ICD-10 code is required'}), 400
        
        # Validate all codes
        validation = icd_mapper.validate_code_sequence(icd10_codes)
        if validation['invalid_codes']:
            logger.warning(f"Invalid codes found: {validation['invalid_codes']}")
        
        # Extract parameters
        insurance_model = data.get('insurance_model', 'MA')
        demographics = {
            'age': int(data.get('age', 65)),
            'gender': data.get('gender', 'M').upper()
        }
        patient_id = data.get('patient_id', f"PAT_{int(datetime.now().timestamp())}")
        
        # Calculate risk
        calculator = RiskAdjustmentCalculator(insurance_model)
        report = calculator.generate_risk_report({
            'patient_id': patient_id,
            'icd10_codes': validation['valid_codes'],
            'demographics': demographics
        })
        
        # Detect hierarchy issues
        hcc_list = [m['hcc_id'] for m in report['raf_calculation']['hcc_mappings']]
        hierarchy_issues = detect_hierarchy_issues(hcc_list)
        report['raf_calculation']['hierarchy_issues'].extend(hierarchy_issues)
        
        # Log to audit trail
        audit_logger.log_calculation({
            'patient_id': patient_id,
            'insurance_model': insurance_model,
            'icd10_codes': validation['valid_codes'],
            'raf_score': report['raf_calculation']['raf_score'],
            'adjusted_premium': report['premium_calculation']['adjusted_premium'],
            'risk_level': report['risk_level']
        })
        
        return jsonify({
            'success': True,
            'report': report,
            'validation': validation
        })
    
    except Exception as e:
        logger.error(f"Risk calculation error: {str(e)}")
        return jsonify({'error': f'Calculation error: {str(e)}'}), 500


@app.route('/api/generate-report', methods=['POST'])
def generate_report():
    """Generate downloadable report in multiple formats"""
    try:
        data = request.json
        report_data = data.get('report')
        report_format = data.get('format', 'text').lower()  # text, json, pdf, csv
        
        if not report_data:
            return jsonify({'error': 'No report data provided'}), 400
        
        if report_format == 'text':
            content = report_generator.generate_text_report(report_data)
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(app.config['REPORT_FOLDER'], filename)
            with open(filepath, 'w') as f:
                f.write(content)
        
        elif report_format == 'json':
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(app.config['REPORT_FOLDER'], filename)
            filepath = report_generator.generate_json_report(report_data, filepath)
        
        elif report_format == 'pdf':
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(app.config['REPORT_FOLDER'], filename)
            filepath = report_generator.generate_pdf_report(report_data, filepath)
        
        elif report_format == 'csv':
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(app.config['REPORT_FOLDER'], filename)
            filepath = report_generator.generate_csv_report([report_data], filepath)
        
        else:
            return jsonify({'error': f'Unsupported format: {report_format}'}), 400
        
        logger.info(f"Report generated: {filename}")
        
        return jsonify({
            'success': True,
            'filename': os.path.basename(filepath),
            'format': report_format,
            'download_url': f'/api/download-report/{os.path.basename(filepath)}'
        })
    
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        return jsonify({'error': f'Report error: {str(e)}'}), 500


@app.route('/api/download-report/<filename>', methods=['GET'])
def download_report(filename):
    """Download generated report"""
    try:
        filepath = os.path.join(app.config['REPORT_FOLDER'], filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'Report not found'}), 404
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/audit-trail/<patient_id>', methods=['GET'])
def get_audit_trail(patient_id):
    """Retrieve audit trail for patient"""
    try:
        trail = audit_logger.get_patient_audit_trail(patient_id)
        return jsonify({
            'success': True,
            'patient_id': patient_id,
            'events': trail,
            'event_count': len(trail)
        })
    except Exception as e:
        logger.error(f"Audit trail error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/compliance-summary', methods=['GET'])
def get_compliance_summary():
    """Get compliance summary report"""
    try:
        summary = audit_logger.get_compliance_summary()
        return jsonify({
            'success': True,
            'summary': summary
        })
    except Exception as e:
        logger.error(f"Compliance summary error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/hcc-reference', methods=['GET'])
def get_hcc_reference():
    """Get HCC reference data"""
    try:
        # Group by category
        by_category = {}
        for hcc_id, hcc_data in HCC_MAPPINGS.items():
            category = hcc_data.get('category', 'Other')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append({
                'hcc_id': hcc_id,
                'name': hcc_data['name'],
                'raf_score': hcc_data['raf_score'],
                'icd10_codes': hcc_data['icd10_codes']
            })
        
        return jsonify({
            'success': True,
            'total_hcc': len(HCC_MAPPINGS),
            'by_category': by_category,
            'hcc_mappings': HCC_MAPPINGS
        })
    except Exception as e:
        logger.error(f"HCC reference error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/icd-reference/search', methods=['GET'])
def search_icd_reference():
    """Search the official ICD diagnosis workbook by code or description."""
    query = request.args.get('q', '').strip()
    try:
        limit = min(max(int(request.args.get('limit', 100)), 1), 100)
    except ValueError:
        limit = 100
    matcher = get_icd_diagnosis_matcher()
    results = matcher.search(query, limit) if query else []
    return jsonify({
        'success': True,
        'query': query,
        'available': matcher.available,
        'total_matches': len(results),
        'results': results,
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return jsonify({'error': 'Server error'}), 500


if __name__ == '__main__':
    logger.info("Starting HCC Medical Coding Tool v2.0")
    app.run(debug=True, host='0.0.0.0', port=5000)
