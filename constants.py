"""
Pénzügyi hitelminősítő rendszer oszlopnév konstansok.
25 feature: 8 meglévő + 17 új mérleg/eredmény/arány mutató.
Az oszlopneveknek meg kell egyezniük a tanítási CSV fejlécével.
"""

# Nominális (kategorikus) oszlopok - OneHot encoding
NOMINAL_COLUMNS = [
    "Industry_code",
    "legal_entity_type",
    "pl_subseg_desc",        # Ügyfélszegmens: Micro, SME, Corporate
    "address_county",        # Székhely megye
]

# Diszkrét numerikus oszlopok
DISCRETE_COLUMNS = [
    "LatePaymentCount",
    "num_employees",         # Alkalmazottak száma
    "BusinessAge",           # Vállalkozás kora (év)
]

# Folytonos numerikus oszlopok - MinMaxScaler
CONTINUOUS_COLUMNS = [
    # Meglévők
    "NetSales",
    "Operating Margin",
    "Current Ratio",
    "DebtToEquityRatio",
    "Return on Assets (ROA)",
    # Mérleg
    "TotalAssets",
    "TotalLiabs",
    "CurrentAssets",
    "CurrentLiabs",
    "RetainedEarnings",
    "collateral_value",
    # Eredménykimutatás
    "EBIT",
    "GrossMargin",
    "AnnualRevenueGrowth",
    # Aránymutatók
    "Return on Equity (ROE)",
    "QuickRatio",
    "WorkingCapital",
    "DaysSalesOutstanding (DSO)",
    "OperatingCashFlowRatio",
]

# Ordinális oszlopok
ORDINAL_COLUMNS = []

# Összes bemeneti oszlop neve (predikció inputja)
COLUMN_NAMES = (
    NOMINAL_COLUMNS
    + DISCRETE_COLUMNS
    + CONTINUOUS_COLUMNS
    + ORDINAL_COLUMNS
)

# Adatbázis mező → CSV oszlopnév leképezés (predikció összeállításhoz)
DB_TO_CSV_MAPPING = {
    "industry_code":           "Industry_code",
    "legal_entity_type":       "legal_entity_type",
    "client_segment":          "pl_subseg_desc",
    "address_county":          "address_county",
    "late_payment_count":      "LatePaymentCount",
    "num_employees":           "num_employees",
    "business_age":            "BusinessAge",
    "net_sales":               "NetSales",
    "operating_margin":        "Operating Margin",
    "current_ratio":           "Current Ratio",
    "debt_to_equity":          "DebtToEquityRatio",
    "return_on_assets":        "Return on Assets (ROA)",
    "total_assets":            "TotalAssets",
    "total_liabs":             "TotalLiabs",
    "current_assets":          "CurrentAssets",
    "current_liabs":           "CurrentLiabs",
    "retained_earnings":       "RetainedEarnings",
    "collateral_value":        "collateral_value",
    "ebit":                    "EBIT",
    "gross_margin":            "GrossMargin",
    "annual_revenue_growth":   "AnnualRevenueGrowth",
    "return_on_equity":        "Return on Equity (ROE)",
    "quick_ratio":             "QuickRatio",
    "working_capital":         "WorkingCapital",
    "days_sales_outstanding":  "DaysSalesOutstanding (DSO)",
    "operating_cash_flow_ratio": "OperatingCashFlowRatio",
    "description":             "description",
}
