# Quick Start Guide - Insurance Risk Adjustment Tool

## Getting Started in 5 Minutes

### Step 1: Install Dependencies (Already Done!)
✅ Flask and web framework installed
✅ PyMuPDF for PDF processing
✅ All Python packages ready

### Step 2: Start the Web Application

Run this command in the terminal:
```bash
cd c:\RCMX
python app.py
```

You should see:
```
* Running on http://127.0.0.1:5000
* Debug mode: on
```

### Step 3: Open in Browser

Open your browser and go to:
```
http://localhost:5000
```

You'll see the Insurance Risk Adjustment Tool dashboard!

---

## Using the Tool

### Dashboard Tab
- View summary statistics
- See recent analysis
- Access all insurance models

### Upload Tab
- Upload medical PDF documents
- Automatic OCR text extraction
- Entity identification (names, IDs, diagnoses)
- Document type detection

### Risk Calculator Tab
1. Enter Patient Information:
   - Patient ID
   - Age & Gender
   - Select Insurance Model

2. Enter Diagnosis Codes:
   - Example: `E11.9, I50, J44.9`
   - (Type ICD-10-CM codes separated by commas)

3. Click "Calculate Risk"

4. View Results:
   - RAF Score
   - Risk Level (Low/Moderate/High/Very High)
   - Adjusted Annual & Monthly Premiums
   - HCC Mappings
   - Coder Recommendations

### Export Reports
Choose format:
- 📄 **Text** - Simple text report
- 📊 **JSON** - For data integration
- 🖨️ **PDF** - Professional report
- 📈 **Excel** - For analysis

### Audit Trail Tab
- Search patient history
- View compliance events
- Download audit logs

### HCC Reference Tab
- Browse all HCC categories (CMS 2025)
- Search by HCC ID or ICD-10 code
- View RAF scores and descriptions

---

## Example Workflow

### Scenario: Process a Medicare Advantage Patient

```
Patient: John Smith, Age 72, Male
Insurance: Medicare Advantage
Diagnoses: Type 2 Diabetes, Heart Failure, COPD
```

**Steps:**
1. Click **Risk Calculator** tab
2. Enter:
   - Patient ID: `PAT-001`
   - Age: `72`
   - Gender: `Male`
   - Insurance Model: `Medicare Advantage`
   - ICD-10 Codes: `E11.9, I50, J44.9`
3. Click **Calculate Risk**

**Results:**
- RAF Score: 1.245
- Risk Level: **High Risk**
- HCC Mappings:
  - E11.9 → HCC035 (Diabetes)
  - I50 → HCC047 (Heart Failure)
  - J44.9 → HCC111 (COPD)
- Adjusted Premium: $116,476/year ($9,706/month)
- Recommendations:
  - Patient has high-risk profile
  - Recommend care management intervention
  - Consider enhanced monitoring

4. Click **Export PDF** to share with stakeholders

---

## Common ICD-10 Codes for Testing

### Chronic Conditions
| Code | Description |
|------|-------------|
| E11.9 | Type 2 Diabetes Mellitus |
| I10 | Essential Hypertension |
| I50 | Heart Failure |
| J44.9 | COPD |
| N18.5 | Chronic Kidney Disease Stage 5 |
| F32.9 | Major Depressive Disorder |

### Try It:
Copy and paste into ICD-10 Codes field:
```
E11.9, I50, J44.9
```

---

## Tips for Medical Coders

### RAF Score Interpretation
- **< 0.5**: Low Risk - Standard care
- **0.5 - 1.5**: Moderate Risk - Monitor closely
- **1.5 - 3.0**: High Risk - Care management
- **> 3.0**: Very High Risk - Intensive intervention

### Maximizing Accuracy
1. **Verify All Codes**: Ensure ICD-10 codes are documented
2. **Check Hierarchy**: Tool alerts on superseded codes
3. **Review Combinations**: Some codes work better together
4. **Update Records**: Add supporting diagnoses for higher RAF scores
5. **Document Carefully**: Audit trail tracks all changes

### HCC Hierarchy Examples
- **Metastatic Cancer (HCC008)** supersedes:
  - Lung Cancer (HCC010)
  - Breast Cancer (HCC011)
  - Colorectal Cancer (HCC012)

- **Heart Failure (HCC047)** supersedes:
  - Acute MI (HCC046)

---

## API Usage (For Developers)

### Calculate Risk via API
```bash
curl -X POST http://localhost:5000/api/calculate-risk \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "PAT-001",
    "age": 72,
    "gender": "M",
    "insurance_model": "MA",
    "icd10_codes": ["E11.9", "I50", "J44.9"]
  }'
```

### Get Audit Trail
```bash
curl http://localhost:5000/api/audit-trail/PAT-001
```

### Get HCC Reference
```bash
curl http://localhost:5000/api/hcc-reference
```

---

## Troubleshooting

### Flask won't start
```bash
# Check if port 5000 is in use
netstat -ano | findstr :5000

# Try different port
python app.py  # Edit app.py last line to: app.run(port=5001)
```

### PDF upload fails
- Ensure PDF is readable (not scanned image-only)
- File size < 16MB
- Check file permissions

### Codes not matching HCC
- Verify ICD-10 format (e.g., E11.9, not E119)
- Check HCC Reference tab for valid codes
- Some codes may not have HCC mapping

---

## File Structure Reference

```
c:\RCMX\
├── app.py                 ← Start here for web app
├── main.py                ← CLI version
├── README.md              ← Full documentation
├── QUICKSTART.md          ← This file
├── templates/index.html   ← Web interface
├── static/
│   ├── style.css          ← Styling
│   └── app.js             ← Frontend logic
├── src/
│   ├── hcc_engine.py      ← HCC mapping logic
│   ├── risk_adjustment.py ← RAF calculation
│   └── [other modules]
└── reports/               ← Generated reports
```

---

## Next Steps

1. **Start the web app** (see Step 2 above)
2. **Upload a test PDF** or use the calculator directly
3. **Explore features** - try different insurance models
4. **Generate reports** in various formats
5. **Review audit logs** for compliance

---

## Support Resources

- **CMS Risk Adjustment Models**: https://www.cms.gov/Medicare/Health-Plans/
- **ICD-10-CM Code Lookup**: https://www.icd10data.com/
- **HCC Documentation**: Review in the "HCC Reference" tab
- **Code Comments**: Check source files for implementation details

---

## Security Notes

- All audit logs are stored locally in `/audit_logs/`
- No external data transmission
- Reports generated locally
- Suitable for HIPAA environments (with proper infrastructure)

---

**Ready to go!** Open http://localhost:5000 in your browser now. 🚀
