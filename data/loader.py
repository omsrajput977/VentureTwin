import json
from pathlib import Path
from typing import Dict, Any, List, Optional

DATA_DIR = Path(__file__).resolve().parent
SYNTHETIC_COMPANY_PATH = DATA_DIR / "synthetic_company.json"
SEEDED_DECISIONS_PATH = DATA_DIR / "seeded_decisions.json"
BENCHMARKS_PATH = DATA_DIR / "benchmarks.json"
MODEL_CONFIG_PATH = DATA_DIR / "model_config.json"

def load_model_config(file_path: Optional[Path] = None) -> Dict[str, Any]:
    path = file_path or MODEL_CONFIG_PATH
    if not path.exists():
        return {
            "baseline_activation_rate": 0.35,
            "free_user_monthly_churn": 0.12,
            "monthly_support_cost_per_fte": 7000.0,
            "tickets_per_fte_monthly": 300,
            "paid_tickets_per_customer_monthly": 1.83,
            "illustrative": True
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_benchmarks(file_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = file_path or BENCHMARKS_PATH
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_company_data(file_path: Optional[Path] = None) -> Dict[str, Any]:
    path = file_path or SYNTHETIC_COMPANY_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_company_snapshot(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Returns high-level snapshot suitable for dashboard display and agent prompt context.
    """
    raw = load_company_data(file_path)
    return {
        "company_name": raw["company_name"],
        "stage": raw["stage"],
        "currency": raw["currency"],
        "synthetic_data_badge": raw["synthetic_data_badge"],
        "mrr": raw["financials"]["mrr"],
        "arr": raw["financials"]["arr"],
        "cash_balance": raw["financials"]["cash_balance"],
        "runway_months": raw["financials"]["runway_months"],
        "monthly_burn_net": raw["financials"]["monthly_burn_net"],
        "gross_margin": raw["financials"]["gross_margin"],
        "paying_customers": raw["customers"]["total_paying"],
        "monthly_churn_rate": raw["customers"]["monthly_churn_rate"],
        "cac": raw["unit_economics"]["cac"],
        "ltv": raw["unit_economics"]["ltv"],
        "monthly_visitors": raw["funnel"]["monthly_visitors"],
        "trial_to_paid_conversion": raw["funnel"]["trial_to_paid_conversion"],
        "infra_cost_monthly": raw["infrastructure"]["monthly_cloud_cost"],
        "support_headcount": raw["support"]["headcount_fte"],
        "support_cost_monthly": raw["support"]["monthly_support_cost"]
    }

def load_seeded_decisions(file_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = file_path or SEEDED_DECISIONS_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

