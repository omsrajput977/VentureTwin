from typing import Dict, Any, Optional
from data.loader import load_company_data

def get_company_data_source() -> Dict[str, Any]:
    return load_company_data()

def lookup_financials() -> Dict[str, Any]:
    data = get_company_data_source()
    return data["financials"]

def lookup_funnel() -> Dict[str, Any]:
    data = get_company_data_source()
    return data["funnel"]

def lookup_customers() -> Dict[str, Any]:
    data = get_company_data_source()
    return data["customers"]

def lookup_infra_costs() -> Dict[str, Any]:
    data = get_company_data_source()
    return data["infrastructure"]

def lookup_support_metrics() -> Dict[str, Any]:
    data = get_company_data_source()
    return data["support"]

def lookup_unit_economics() -> Dict[str, Any]:
    data = get_company_data_source()
    return data["unit_economics"]
