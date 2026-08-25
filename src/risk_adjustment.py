"""
Risk Adjustment Factor (RAF) Calculation Module
Calculates insurance risk scores, premiums, and adjustments for different insurance models
"""

from typing import Dict, List
from datetime import datetime
from src.hcc_engine import get_hcc_from_icd10, get_raf_score, detect_hierarchy_issues

class RiskAdjustmentCalculator:
    """Calculate risk adjustment factors and premiums"""
    
    # Base premium rates by insurance model (2025 estimated)
    BASE_PREMIUMS = {
        "MA": 12000,           # Medicare Advantage
        "Medicare": 10500,     # Original Medicare
        "Medicaid": 8500,      # Medicaid
        "Commercial": 15000    # Commercial insurance
    }
    
    # Age-based adjustment factors
    AGE_FACTORS = {
        "MA": {18: 0.40, 21: 0.45, 25: 0.50, 30: 0.58, 35: 0.68, 40: 0.81, 
               45: 1.00, 50: 1.34, 55: 1.82, 60: 2.44, 65: 3.24, 70: 4.24},
        "Medicare": {65: 1.00, 70: 1.50, 75: 2.10, 80: 3.00, 85: 4.00, 90: 5.50},
        "Medicaid": {18: 0.30, 21: 0.35, 30: 0.45, 40: 0.65, 50: 1.00, 65: 1.20},
        "Commercial": {18: 0.35, 21: 0.45, 30: 0.60, 40: 0.90, 50: 1.40, 65: 2.20}
    }
    
    # Gender adjustment factors
    GENDER_FACTORS = {
        "MA": {"M": 1.02, "F": 0.98},
        "Medicare": {"M": 1.01, "F": 0.99},
        "Medicaid": {"M": 1.05, "F": 0.95},
        "Commercial": {"M": 1.08, "F": 0.92}
    }
    
    def __init__(self, insurance_model: str = "MA"):
        """Initialize calculator for specific insurance model"""
        self.insurance_model = insurance_model
        self.base_premium = self.BASE_PREMIUMS.get(insurance_model, 12000)
    
    def calculate_raf(self, icd10_codes: List[str], demographics: Dict) -> Dict:
        """
        Calculate RAF score from diagnosis codes
        
        Args:
            icd10_codes: List of ICD-10-CM codes
            demographics: {"age": int, "gender": str, "region": str}
        
        Returns:
            Dictionary with RAF calculation details
        """
        result = {
            "icd10_codes": icd10_codes,
            "hcc_mappings": [],
            "raf_score": 0.0,
            "hierarchy_issues": [],
            "demographics": demographics
        }
        
        hcc_list = []
        for code in icd10_codes:
            hcc_info = get_hcc_from_icd10(code)
            if hcc_info:
                hcc_list.append(hcc_info["hcc_id"])
                result["hcc_mappings"].append({
                    "icd10": code,
                    "hcc_id": hcc_info["hcc_id"],
                    "hcc_name": hcc_info["name"],
                    "raf_value": hcc_info["raf_score"]
                })
        
        # Detect hierarchy issues
        result["hierarchy_issues"] = detect_hierarchy_issues(hcc_list)
        
        # Calculate RAF score
        result["raf_score"] = get_raf_score(hcc_list, demographics)
        
        return result
    
    def calculate_premium(self, raf_score: float, demographics: Dict) -> Dict:
        """Calculate adjusted premium based on RAF"""
        age = demographics.get("age", 45)
        gender = demographics.get("gender", "M")
        
        # Get age factor
        age_factor = self._get_age_factor(age)
        
        # Get gender factor
        gender_factor = self.GENDER_FACTORS.get(self.insurance_model, {}).get(gender, 1.0)
        
        # Calculate adjusted premium
        adjusted_premium = self.base_premium * age_factor * gender_factor * (1 + raf_score)
        
        return {
            "base_premium": self.base_premium,
            "age_factor": age_factor,
            "gender_factor": gender_factor,
            "raf_multiplier": (1 + raf_score),
            "adjusted_premium": round(adjusted_premium, 2),
            "monthly_premium": round(adjusted_premium / 12, 2),
            "insurance_model": self.insurance_model
        }
    
    def _get_age_factor(self, age: int) -> float:
        """Get age adjustment factor"""
        factors = self.AGE_FACTORS.get(self.insurance_model, {})
        
        # Find closest age bracket
        for bracket_age in sorted(factors.keys()):
            if age <= bracket_age:
                return factors[bracket_age]
        
        # Return highest bracket if age exceeds max
        return max(factors.values())
    
    def calculate_risk_score(self, raf_score: float) -> str:
        """Classify risk level based on RAF score"""
        if raf_score < 0.5:
            return "Low Risk"
        elif raf_score < 1.5:
            return "Moderate Risk"
        elif raf_score < 3.0:
            return "High Risk"
        else:
            return "Very High Risk"
    
    def generate_risk_report(self, patient_data: Dict) -> Dict:
        """Generate comprehensive risk adjustment report"""
        icd10_codes = patient_data.get("icd10_codes", [])
        demographics = patient_data.get("demographics", {})
        
        # Calculate RAF
        raf_result = self.calculate_raf(icd10_codes, demographics)
        
        # Calculate premium
        premium_result = self.calculate_premium(raf_result["raf_score"], demographics)
        
        # Determine risk level
        risk_level = self.calculate_risk_score(raf_result["raf_score"])
        
        return {
            "report_date": datetime.now().isoformat(),
            "patient_id": patient_data.get("patient_id"),
            "insurance_model": self.insurance_model,
            "demographics": demographics,
            "raf_calculation": raf_result,
            "premium_calculation": premium_result,
            "risk_level": risk_level,
            "recommendations": self._generate_recommendations(raf_result, risk_level)
        }
    
    def _generate_recommendations(self, raf_result: Dict, risk_level: str) -> List[str]:
        """Generate coder recommendations based on analysis"""
        recommendations = []
        
        # Check for missing codes
        if len(raf_result["hcc_mappings"]) < 3 and risk_level in ["High Risk", "Very High Risk"]:
            recommendations.append("Consider chart review for additional compliant HCC codes")
        
        # Check for hierarchy issues
        if raf_result["hierarchy_issues"]:
            recommendations.append(f"Review HCC hierarchy: {len(raf_result['hierarchy_issues'])} conflicts detected")
        
        # Risk-specific recommendations
        if risk_level == "Low Risk":
            recommendations.append("Patient has low risk profile - standard care pathways appropriate")
        elif risk_level == "Very High Risk":
            recommendations.append("High-risk patient - consider care management intervention")
            recommendations.append("Recommend enhanced monitoring and preventive services")
        
        return recommendations
