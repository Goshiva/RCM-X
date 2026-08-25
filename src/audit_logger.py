"""
Audit Logger for Compliance and Compliance Tracking
Logs all risk adjustment calculations for audit trail purposes
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List

class AuditLogger:
    """Audit trail logger for compliance"""
    
    def __init__(self, log_dir: str = "audit_logs"):
        """Initialize audit logger"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.current_log_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
    
    def log_calculation(self, event_data: Dict) -> None:
        """Log a risk adjustment calculation"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "risk_calculation",
            "user_id": event_data.get("user_id", "system"),
            "patient_id": event_data.get("patient_id"),
            "insurance_model": event_data.get("insurance_model"),
            "icd10_codes": event_data.get("icd10_codes", []),
            "raf_score": event_data.get("raf_score"),
            "adjusted_premium": event_data.get("adjusted_premium"),
            "risk_level": event_data.get("risk_level"),
            "status": event_data.get("status", "success")
        }
        
        # Write to JSONL for audit trail
        with open(self.current_log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    def log_code_change(self, change_data: Dict) -> None:
        """Log when codes are added/modified"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "code_modification",
            "user_id": change_data.get("user_id"),
            "patient_id": change_data.get("patient_id"),
            "action": change_data.get("action"),  # "add", "remove", "update"
            "code": change_data.get("code"),
            "reason": change_data.get("reason"),
            "approved_by": change_data.get("approved_by")
        }
        
        with open(self.current_log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    def log_hierarchy_resolution(self, resolution_data: Dict) -> None:
        """Log HCC hierarchy conflicts and resolutions"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "hierarchy_resolution",
            "user_id": resolution_data.get("user_id"),
            "patient_id": resolution_data.get("patient_id"),
            "conflict": resolution_data.get("conflict"),
            "resolution": resolution_data.get("resolution"),
            "notes": resolution_data.get("notes")
        }
        
        with open(self.current_log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    def get_patient_audit_trail(self, patient_id: str) -> List[Dict]:
        """Retrieve all audit events for a patient"""
        events = []
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            with open(log_file, 'r') as f:
                for line in f:
                    event = json.loads(line)
                    if event.get("patient_id") == patient_id:
                        events.append(event)
        
        return sorted(events, key=lambda x: x["timestamp"], reverse=True)
    
    def export_audit_report(self, output_file: str = None) -> str:
        """Export audit logs to CSV for compliance review"""
        if output_file is None:
            output_file = f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        all_events = []
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            with open(log_file, 'r') as f:
                for line in f:
                    all_events.append(json.loads(line))
        
        if not all_events:
            return None
        
        # Write to CSV
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_events[0].keys())
            writer.writeheader()
            writer.writerows(all_events)
        
        return output_file
    
    def get_compliance_summary(self, start_date: str = None, end_date: str = None) -> Dict:
        """Generate compliance summary report"""
        events = []
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            with open(log_file, 'r') as f:
                for line in f:
                    events.append(json.loads(line))
        
        # Filter by date if provided
        if start_date:
            events = [e for e in events if e["timestamp"] >= start_date]
        if end_date:
            events = [e for e in events if e["timestamp"] <= end_date]
        
        # Generate summary
        summary = {
            "total_calculations": len([e for e in events if e["event_type"] == "risk_calculation"]),
            "code_modifications": len([e for e in events if e["event_type"] == "code_modification"]),
            "hierarchy_issues_resolved": len([e for e in events if e["event_type"] == "hierarchy_resolution"]),
            "unique_patients": len(set(e.get("patient_id") for e in events if e.get("patient_id"))),
            "period_start": start_date or "all_time",
            "period_end": end_date or datetime.now().isoformat(),
            "report_generated": datetime.now().isoformat()
        }
        
        return summary
