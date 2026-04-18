import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="EY | Geopolitical Bank Capital Stress Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------
# Helpers
# -----------------------------
def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def usd_billions(x: float) -> str:
    return f"${x:,.1f}B"


def bps(x: float) -> str:
    return f"{x:,.0f} bps"


def ratio_points_from_capital(amount: float, base_rwa: float) -> float:
    return 100.0 * amount / base_rwa if base_rwa > 0 else 0.0


# -----------------------------
# Header
# -----------------------------
st.markdown(
    "<h1 style='color:#FFE600;'>EY | Geopolitical Bank Capital Stress Dashboard</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "*BoE-aligned Year 1 CET1 presentation: income, losses, RWAs/other capital items, drawdown pre-SMA and post-SMA*"
)
st.markdown("---")


# -----------------------------
# Sidebar inputs
# -----------------------------
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/EY_logo_2019.svg/512px-EY_logo_2019.svg.png",
        width=110,
    )
    st.markdown("<h2 style='color:#FFE600;'>Scenario Inputs</h2>", unsafe_allow_html=True)

    starting_cet1 = st.slider("Starting CET1 Capital ($B)", 10, 500, 250, 10)
    baseline_cet1_ratio = st.slider("Baseline CET1 Ratio (%)", 8.0, 18.0, 12.5, 0.1)
    severity = st.slider("Conflict Severity (1-10)", 1, 10, 5, 1)
    duration_months = st.slider("Conflict Duration (Months)", 1, 36, 12, 1)
    duration_years = duration_months / 12.0

    st.markdown("---")
    st.markdown("<h2 style='color:#FFE600;'>Bank Profile</h2>", unsafe_allow_html=True)

    bank_profile = st.selectbox(
        "Bank Archetype",
        [
            "Universal Bank",
            "Wholesale / Markets Heavy",
            "Retail / Deposit Heavy",
            "EM / Cross-Border Heavy",
        ],
    )

    oil_dependency = st.slider("Portfolio Sensitivity to Energy / Oil Shock", 0.5, 1.5, 1.0, 0.1)
    sanctions_exposure = st.slider("Direct Exposure to Sanctions / Corridor Risk", 0.0, 1.5, 0.5, 0.1)
    cyber_vulnerability = st.slider("Operational / Cyber Vulnerability", 0.5, 1.5, 1.0, 0.1)
    vulnerable_sector_share = st.slider("Vulnerable Sector Share of Loan Book (%)", 5, 50, 20, 1) / 100.0

    st.markdown("---")
    st.markdown("<h2 style='color:#FFE600;'>BoE-Style Controls</h2>", unsafe_allow_html=True)
    include_misconduct_costs = st.checkbox("Include misconduct / legal costs", value=False)
    include_sma = st.checkbox("Include strategic management actions (SMA)", value=True)
    sma_strength = st.slider("SMA effectiveness (% of pre-SMA drawdown recovered)", 0, 40, 18, 1) / 100.0
    cancel_distributions = st.checkbox("Cancel dividends / buybacks", value=True)
    enable_hedging = st.checkbox("Assume partial hedging benefit", value=True)
    enable_rwa_mitigation = st.checkbox("Assume moderate RWA mitigation", value=False)

    st.markdown("---")
    st.markdown("<h2 style='color:#FFE600;'>Optional Overrides</h2>", unsafe_allow_html=True)
    enable_overrides = st.checkbox("Enable calibration overrides", value=False)

    if enable_overrides:
        base_pd = st.slider("Base PD (%)", 0.3, 3.0, 1.2, 0.1) / 100
        downturn_lgd = st.slider("Downturn LGD (%)", 25, 65, 40, 5) / 100
        annual_nii_to_rwa = st.slider("Annual Net Interest Income / RWA (%)", 0.2, 3.0, 1.2, 0.1) / 100
        annual_fee_to_rwa = st.slider("Annual Net Fee Income / RWA (%)", 0.1, 1.5, 0.35, 0.05) / 100
        annual_traded_income_to_rwa = st.slider("Annual Net Traded Income / RWA (%)", 0.0, 1.5, 0.20, 0.05) / 100
        annual_opex_to_rwa = st.slider("Annual Operating Expenses / RWA (%)", 0.3, 3.0, 1.1, 0.1) / 100
        tax_and_other_pl_rate = st.slider("Tax and Other P&L / Capital Rate (bps of RWA)", -40, 40, -10, 1) / 10000
        payout_ratio = st.slider("Baseline Distribution Ratio (% of income pool)", 0, 60, 20, 5) / 100
        hedge_offset = st.slider("Traded Risk Hedging Offset (%)", 0, 50, 15, 5) / 100
        rwa_mitigation_pct = st.slider("RWA Mitigation on Add-ons (%)", 0, 20, 6, 1) / 100
        misconduct_cost_rate = st.slider("Misconduct / Legal Cost Rate (bps of RWA)", 0, 40, 8, 1) / 10000
        operational_risk_rate_bps = st.slider("Operational Risk Rate (bps of assets)", 1, 80, 18, 1) / 10000
    else:
        base_pd = 0.012
        downturn_lgd = 0.40
        annual_nii_to_rwa = 0.012
        annual_fee_to_rwa = 0.0035
        annual_traded_income_to_rwa = 0.0020
        annual_opex_to_rwa = 0.011
        tax_and_other_pl_rate = -0.0010
        payout_ratio = 0.20
        hedge_offset = 0.15
        rwa_mitigation_pct = 0.06
        misconduct_cost_rate = 0.0008
        operational_risk_rate_bps = 0.0018


# -----------------------------
# Reconciled opening balance sheet
# -----------------------------
profile_map = {
    "Universal Bank": {
        "rwa_density": 0.58,
        "loan_share_assets": 0.54,
        "banking_book_securities_share_assets": 0.18,
        "trading_book_share_assets": 0.06,
        "direct_exposure_share_assets": 0.018,
        "loan_rwa_density": 0.70,
        "irrbb_duration": 3.8,
        "trading_duration": 1.8,
        "nii_sensitivity": 1.00,
        "fee_resilience": 1.00,
        "trading_income_resilience": 1.00,
    },
    "Wholesale / Markets Heavy": {
        "rwa_density": 0.62,
        "loan_share_assets": 0.42,
        "banking_book_securities_share_assets": 0.13,
        "trading_book_share_assets": 0.12,
        "direct_exposure_share_assets": 0.030,
        "loan_rwa_density": 0.75,
        "irrbb_duration": 3.4,
        "trading_duration": 2.1,
        "nii_sensitivity": 0.90,
        "fee_resilience": 1.10,
        "trading_income_resilience": 1.35,
    },
    "Retail / Deposit Heavy": {
        "rwa_density": 0.52,
        "loan_share_assets": 0.63,
        "banking_book_securities_share_assets": 0.20,
        "trading_book_share_assets": 0.03,
        "direct_exposure_share_assets": 0.010,
        "loan_rwa_density": 0.60,
        "irrbb_duration": 4.1,
        "trading_duration": 1.2,
        "nii_sensitivity": 1.15,
        "fee_resilience": 0.90,
        "trading_income_resilience": 0.65,
    },
    "EM / Cross-Border Heavy": {
        "rwa_density": 0.65,
        "loan_share_assets": 0.50,
        "banking_book_securities_share_assets": 0.16,
        "trading_book_share_assets": 0.05,
        "direct_exposure_share_assets": 0.035,
        "loan_rwa_density": 0.80,
        "irrbb_duration": 3.6,
        "trading_duration": 1.9,
        "nii_sensitivity": 0.95,
        "fee_resilience": 0.95,
        "trading_income_resilience": 0.95,
    },
}

p = profile_map[bank_profile]
base_rwa = starting_cet1 / (baseline_cet1_ratio / 100.0)
total_assets = base_rwa / p["rwa_density"]
loan_book = total_assets * p["loan_share_assets"]
banking_book_securities = total_assets * p["banking_book_securities_share_assets"]
trading_book = total_assets * p["trading_book_share_assets"]
direct_exposure_base = total_assets * p["direct_exposure_share_assets"]
opening_ratio_check = (starting_cet1 / base_rwa) * 100 if base_rwa > 0 else 0.0


# -----------------------------
# Stage 1: Scenario translation
# -----------------------------
duration_factor = clamp(0.65 + 0.35 * duration_years, 0.70, 1.40)

oil_peak = 75 + (severity * 6 * oil_dependency) * duration_factor
yield_shock_bps = (severity * 8 + duration_years * 20) * duration_factor
credit_spread_shock_bps = (severity * 10 + duration_years * 18) * duration_factor
fx_stress_index = (severity * 0.45 + duration_years * 0.60) * (1 + 0.35 * sanctions_exposure)

macro_multiplier = 1 + 0.04 * severity + 0.05 * duration_years


# -----------------------------
# BoE-aligned Year 1 decomposition
# -----------------------------
# Income lines
baseline_nii = base_rwa * annual_nii_to_rwa
nii_rate_factor = clamp(
    1 + (yield_shock_bps / 10000) * 6.0 * p["nii_sensitivity"] - 0.03 * severity - 0.015 * max(0.0, duration_years - 1.0),
    0.65,
    1.35,
)
net_interest_income = baseline_nii * nii_rate_factor

baseline_fee_income = base_rwa * annual_fee_to_rwa * p["fee_resilience"]
fee_stress_factor = clamp(1 - (0.05 * severity + 0.03 * max(0.0, duration_years - 1.0)), 0.45, 0.95)
net_fee_and_commission_income = baseline_fee_income * fee_stress_factor

baseline_traded_income = base_rwa * annual_traded_income_to_rwa * p["trading_income_resilience"]
traded_income_factor = clamp(
    1 + 0.04 * severity - 0.02 * max(0.0, duration_years - 1.0) - 0.03 * sanctions_exposure,
    0.35,
    1.60,
)
net_traded_income = baseline_traded_income * traded_income_factor

operating_expenses = base_rwa * annual_opex_to_rwa * clamp(0.95 + 0.05 * severity + 0.03 * max(0.0, duration_years - 1.0), 0.95, 1.45)
net_income_less_expenses = net_interest_income + net_fee_and_commission_income + net_traded_income - operating_expenses

# Loss lines
pd_multiplier = (
    1
    + 0.35 * max(0, (oil_peak - 75) / 100)
    + 0.55 * (yield_shock_bps / 1000)
    + 0.45 * (credit_spread_shock_bps / 1000)
)
pd_multiplier *= (1 + 0.22 * duration_years)
pd_multiplier *= macro_multiplier
sector_overlay = 1 + vulnerable_sector_share * (0.45 * oil_dependency + 0.30 * sanctions_exposure)
stressed_pd = clamp(base_pd * pd_multiplier * sector_overlay, base_pd, 0.10)
stressed_lgd = clamp(
    downturn_lgd * (1 + 0.05 * severity / 10 + 0.05 * max(0.0, duration_years - 1.0)),
    downturn_lgd,
    0.65,
)
impairments = loan_book * stressed_pd * stressed_lgd

irrbb_yield_decimal = yield_shock_bps / 10000
credit_spread_decimal = credit_spread_shock_bps / 10000
raw_irrbb_loss = banking_book_securities * p["irrbb_duration"] * irrbb_yield_decimal * 0.35
raw_trading_loss = trading_book * p["trading_duration"] * (0.45 * irrbb_yield_decimal + 0.55 * credit_spread_decimal)
hedging_benefit = raw_trading_loss * hedge_offset if enable_hedging else 0.0
traded_risk_losses = max(0.0, raw_irrbb_loss + raw_trading_loss - hedging_benefit)

misconduct = base_rwa * misconduct_cost_rate * (0.5 + 0.5 * severity / 10) if include_misconduct_costs else 0.0
operational_risk = total_assets * operational_risk_rate_bps * cyber_vulnerability * clamp(0.7 + 0.08 * severity + 0.05 * max(0.0, duration_years - 1.0), 0.7, 1.6)
losses_total = impairments + traded_risk_losses + misconduct + operational_risk

# RWAs and other capital items
credit_rwa_inflation = loan_book * p["loan_rwa_density"] * (0.010 + 0.0035 * severity) * (0.85 + 0.15 * min(duration_years, 2.0))
market_rwa_inflation = trading_book * 0.20 * (0.010 + 0.003 * severity)
fx_rwa_inflation = base_rwa * 0.0008 * fx_stress_index
operational_rwa_inflation = base_rwa * 0.0006 * severity * cyber_vulnerability
gross_rwa_addon = credit_rwa_inflation + market_rwa_inflation + fx_rwa_inflation + operational_rwa_inflation
rwa_mitigation = gross_rwa_addon * rwa_mitigation_pct if enable_rwa_mitigation else 0.0
stressed_rwa_pre_sma = base_rwa + gross_rwa_addon - rwa_mitigation

# Ratio-point effect of RWA movement, using capital before RWA / other capital items
capital_before_rwa_other = starting_cet1 + net_income_less_expenses - losses_total
pre_rwa_ratio = 100.0 * capital_before_rwa_other / base_rwa if base_rwa > 0 else 0.0
post_rwa_ratio = 100.0 * capital_before_rwa_other / stressed_rwa_pre_sma if stressed_rwa_pre_sma > 0 else 0.0
rwas_leverage_exposure = post_rwa_ratio - pre_rwa_ratio

# Tax and other P&L and capital
# Includes sanctions / corridor losses and any tax / other capital drag.
direct_exposure_loss = direct_exposure_base * sanctions_exposure * (0.015 * severity + 0.010 * max(duration_years, 0.5))
tax_and_other_pl_and_capital = (base_rwa * tax_and_other_pl_rate) - direct_exposure_loss

# Distributions
baseline_distributions = max(0.0, (net_interest_income + net_fee_and_commission_income + net_traded_income) * payout_ratio)
distributions = 0.0 if cancel_distributions else baseline_distributions

rwas_and_other_capital_items = rwas_leverage_exposure + ratio_points_from_capital(tax_and_other_pl_and_capital - distributions, base_rwa)

# Drawdown pre-SMA
capital_pre_sma = capital_before_rwa_other + tax_and_other_pl_and_capital - distributions
stress_test_low_point_pre_sma = 100.0 * capital_pre_sma / stressed_rwa_pre_sma if stressed_rwa_pre_sma > 0 else 0.0
drawdown_pre_sma = stress_test_low_point_pre_sma - opening_ratio_check

# SMAs
pre_sma_drawdown_abs = max(0.0, opening_ratio_check - stress_test_low_point_pre_sma)
sma_ratio_points = pre_sma_drawdown_abs * sma_strength if include_sma else 0.0

# Apply SMA as a mix of capital support and modest RWA relief
sma_capital_support = base_rwa * (sma_ratio_points / 100.0) * 0.70
sma_rwa_relief = base_rwa * (sma_ratio_points / 100.0) * 0.30
stressed_rwa_post_sma = max(base_rwa * 0.85, stressed_rwa_pre_sma - sma_rwa_relief)
capital_post_sma = capital_pre_sma + sma_capital_support
stress_test_low_point_post_sma = 100.0 * capital_post_sma / stressed_rwa_post_sma if stressed_rwa_post_sma > 0 else 0.0
drawdown_post_sma = stress_test_low_point_post_sma - opening_ratio_check

stressed_cet1 = capital_post_sma
stressed_cet1_ratio = stress_test_low_point_post_sma
required_cet1_ratio = 9.0
systemic_risk_buffer_threshold = 10.5
buffer_headroom = stressed_cet1_ratio - required_cet1_ratio
breach_indicator = 99.5 if buffer_headroom <= 0 else clamp(100 - buffer_headroom * 13, 1, 95)


# -----------------------------
# Year 1 BoE-style waterfall data
# -----------------------------
waterfall_labels = [
    "Start point (Year 0)",
    "Net interest income",
    "Net fees and commission income",
    "Net traded income",
    "Operational expenses",
    "Net income less expenses",
    "Impairments",
    "Traded risk losses",
    "Misconduct",
    "Operational risk",
    "Losses",
    "RWAs/Leverage exposure",
    "Tax and other P&L and capital",
    "Distributions",
    "RWAs and other capital items",
    "Drawdown pre-SMA (Year 1)",
    "SMAs",
    "Drawdown post-SMA (Year 1)",
    "Stress test low-point (Year 1)",
]

nii_rp = ratio_points_from_capital(net_interest_income, base_rwa)
fee_rp = ratio_points_from_capital(net_fee_and_commission_income, base_rwa)
traded_income_rp = ratio_points_from_capital(net_traded_income, base_rwa)
opex_rp = -ratio_points_from_capital(operating_expenses, base_rwa)
net_income_less_expenses_rp = nii_rp + fee_rp + traded_income_rp + opex_rp
impairments_rp = -ratio_points_from_capital(impairments, base_rwa)
traded_risk_rp = -ratio_points_from_capital(traded_risk_losses, base_rwa)
misconduct_rp = -ratio_points_from_capital(misconduct, base_rwa)
operational_risk_rp = -ratio_points_from_capital(operational_risk, base_rwa)
losses_rp = impairments_rp + traded_risk_rp + misconduct_rp + operational_risk_rp
tax_other_rp = ratio_points_from_capital(tax_and_other_pl_and_capital, base_rwa)
distributions_rp = -ratio_points_from_capital(distributions, base_rwa)
rwas_other_capital_rp = rwas_leverage_exposure + tax_other_rp + distributions_rp
smas_rp = stress_test_low_point_post_sma - stress_test_low_point_pre_sma

waterfall_values = [
    opening_ratio_check,
    nii_rp,
    fee_rp,
    traded_income_rp,
    opex_rp,
    net_income_less_expenses_rp,
    impairments_rp,
    traded_risk_rp,
    misconduct_rp,
    operational_risk_rp,
    losses_rp,
    rwas_leverage_exposure,
    tax_other_rp,
    distributions_rp,
    rwas_other_capital_rp,
    drawdown_pre_sma,
    smas_rp,
    drawdown_post_sma,
    stress_test_low_point_post_sma,
]

# Use totals/subtotals as absolute checkpoints for readability, like the BoE table.
waterfall_measure = [
    "absolute",
    "relative",
    "relative",
    "relative",
    "relative",
    "total",
    "relative",
    "relative",
    "relative",
    "relative",
    "total",
    "relative",
    "relative",
    "relative",
    "total",
    "total",
    "relative",
    "total",
    "total",
]

waterfall_text = []
for idx, value in enumerate(waterfall_values):
    if idx in [0, 5, 10, 14, 15, 17, 18]:
        waterfall_text.append(f"{value:.1f}%")
    else:
        waterfall_text.append(f"{value:+.1f}pp")


# -----------------------------
# Tables for display
# -----------------------------
bridge_df = pd.DataFrame(
    {
        "Line item": waterfall_labels,
        "CET1 capital ratio": waterfall_text,
    }
)

mapping_df = pd.DataFrame(
    {
        "BoE-style line item": [
            "Net interest income",
            "Net fees and commission income",
            "Net traded income",
            "Operational expenses",
            "Impairments",
            "Traded risk losses",
            "Misconduct",
            "Operational risk",
            "RWAs/Leverage exposure",
            "Tax and other P&L and capital",
            "Distributions",
            "SMAs",
        ],
        "Scenario mapping": [
            "Core interest earnings under stressed rates",
            "Fee income under stressed activity volumes",
            "Trading / markets income under stress",
            "Recurring expense base in stress year",
            "Credit losses from PD/LGD stress",
            "IRRBB + fair-value / trading losses net of hedging",
            "Optional legal / conduct overlay",
            "Standalone non-credit event loss, including cyber / disruption",
            "Denominator effect from RWA inflation",
            "Tax drag plus sanctions / corridor losses",
            "Dividends, buybacks, AT1 coupons and similar distributions",
            "Strategic management actions shown explicitly as a post pre-SMA offset",
        ],
    }
)

summary_df = pd.DataFrame(
    {
        "Metric": [
            "Starting CET1 ratio",
            "Net income less expenses",
            "Losses",
            "RWAs and other capital items",
            "Drawdown pre-SMA (Year 1)",
            "SMAs",
            "Drawdown post-SMA (Year 1)",
            "Stress test low-point (Year 1)",
            "Minima",
            "Minima and Systemic Risk Buffer",
        ],
        "Value": [
            f"{opening_ratio_check:.1f}%",
            f"{net_income_less_expenses_rp:+.1f}pp",
            f"{losses_rp:+.1f}pp",
            f"{rwas_other_capital_rp:+.1f}pp",
            f"{drawdown_pre_sma:+.1f}pp",
            f"{smas_rp:+.1f}pp",
            f"{drawdown_post_sma:+.1f}pp",
            f"{stress_test_low_point_post_sma:.1f}%",
            f"{required_cet1_ratio:.1f}%",
            f"{systemic_risk_buffer_threshold:.1f}%",
        ],
    }
)


# -----------------------------
# Tabs
# -----------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📊 Dashboard",
        "🧠 BoE-Style Decomposition",
        "🧮 Methodology",
        "⚠️ Governance & Limitations",
        "💬 Client Storylines",
    ]
)

with tab1:
    st.markdown("<h3 style='color:#AAAAAA;'>Scenario Translation</h3>", unsafe_allow_html=True)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Implied Brent Peak", f"${oil_peak:,.0f}/bbl")
    m2.metric("Rates Shock", bps(yield_shock_bps))
    m3.metric("Credit Spread Shock", bps(credit_spread_shock_bps))
    m4.metric("Start point (Year 0)", f"{opening_ratio_check:.1f}%")
    m5.metric("Stress test low-point (Year 1)", f"{stress_test_low_point_post_sma:.1f}%", f"{drawdown_post_sma:.1f}pp", delta_color="inverse")

    st.markdown("---")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net income less expenses", f"{net_income_less_expenses_rp:+.1f}pp")
    c2.metric("Losses", f"{losses_rp:+.1f}pp")
    c3.metric("RWAs and other capital items", f"{rwas_other_capital_rp:+.1f}pp")
    c4.metric("SMAs", f"{smas_rp:+.1f}pp")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Starting RWA", usd_billions(base_rwa))
    c6.metric("Stressed RWA pre-SMA", usd_billions(stressed_rwa_pre_sma), usd_billions(stressed_rwa_pre_sma - base_rwa))
    c7.metric("Gross impairments", usd_billions(impairments))
    c8.metric("Breach indicator", f"{breach_indicator:.1f}%", delta_color="inverse")

    wf = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=waterfall_measure,
            x=waterfall_labels,
            y=waterfall_values,
            text=waterfall_text,
            textposition="outside",
            connector={"line": {"color": "#777777"}},
            decreasing={"marker": {"color": "#FF4136"}},
            increasing={"marker": {"color": "#FFE600"}},
            totals={"marker": {"color": "#FFE600"}},
        )
    )
    wf.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        title="BoE-Aligned CET1 Ratio Waterfall (Year 1)",
        showlegend=False,
        height=700,
        margin=dict(l=20, r=20, t=60, b=20),
        font=dict(color="#FFFFFF"),
        yaxis_title="CET1 ratio / percentage-point contribution",
    )
    st.plotly_chart(wf, use_container_width=True)

    st.markdown("### Threshold Reference")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    with st.expander("Live Calculation Audit Log"):
        st.markdown(
            f"""
            **Bank archetype:** {bank_profile}

            **Opening balance sheet**
            - Starting CET1 = **{usd_billions(starting_cet1)}**
            - Baseline CET1 ratio = **{baseline_cet1_ratio:.1f}%**
            - Derived starting RWA = **{usd_billions(base_rwa)}**
            - Derived total assets = **{usd_billions(total_assets)}**
            - Loan book = **{usd_billions(loan_book)}**
            - Banking book securities = **{usd_billions(banking_book_securities)}**
            - Trading book = **{usd_billions(trading_book)}**

            **Income and expenses**
            - Net interest income = **{usd_billions(net_interest_income)}**
            - Net fees and commission income = **{usd_billions(net_fee_and_commission_income)}**
            - Net traded income = **{usd_billions(net_traded_income)}**
            - Operational expenses = **{usd_billions(operating_expenses)}**

            **Losses**
            - Impairments = **{usd_billions(impairments)}**
            - Traded risk losses = **{usd_billions(traded_risk_losses)}**
            - Misconduct = **{usd_billions(misconduct)}**
            - Operational risk = **{usd_billions(operational_risk)}**

            **RWAs and other capital items**
            - Credit RWA uplift = **{usd_billions(credit_rwa_inflation)}**
            - Market RWA uplift = **{usd_billions(market_rwa_inflation)}**
            - FX / operational RWA uplift = **{usd_billions(fx_rwa_inflation + operational_rwa_inflation)}**
            - RWA mitigation benefit = **{usd_billions(rwa_mitigation)}**
            - RWAs / leverage exposure line = **{rwas_leverage_exposure:+.2f}pp**
            - Tax and other P&L and capital = **{usd_billions(tax_and_other_pl_and_capital)}**
            - Distributions = **{usd_billions(distributions)}**

            **Scenario-specific mapping into BoE-style structure**
            - Direct exposure / sanctions embedded in tax and other P&L and capital = **{usd_billions(direct_exposure_loss)}**
            - Operational / cyber reflected in operational risk = **{usd_billions(operational_risk)}**

            **SMA mechanics**
            - SMA ratio uplift = **{smas_rp:+.2f}pp**
            - SMA capital support = **{usd_billions(sma_capital_support)}**
            - SMA RWA relief = **{usd_billions(sma_rwa_relief)}**
            """
        )

with tab2:
    st.subheader("BoE-Style Decomposition")
    st.dataframe(bridge_df, use_container_width=True, hide_index=True)

    st.markdown("### Line-Item Mapping")
    st.dataframe(mapping_df, use_container_width=True, hide_index=True)

    gross_component_df = pd.DataFrame(
        {
            "Component": [
                "Net interest income",
                "Net fees and commission income",
                "Net traded income",
                "Operational expenses",
                "Impairments",
                "Traded risk losses",
                "Misconduct",
                "Operational risk",
                "Direct exposure / sanctions",
                "Distributions",
            ],
            "Amount ($B)": [
                net_interest_income,
                net_fee_and_commission_income,
                net_traded_income,
                -operating_expenses,
                -impairments,
                -traded_risk_losses,
                -misconduct,
                -operational_risk,
                -direct_exposure_loss,
                -distributions,
            ],
        }
    )
    st.markdown("### Underlying Dollar Diagnostics")
    st.dataframe(gross_component_df, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Methodology")
    st.markdown(
        """
        This version is aligned to the structure shown in your screenshot.

        It does **not** simply mimic an old BoE waterfall header list. Instead, it follows the newer presentation logic:
        - start point
        - income lines
        - **Net income less expenses** subtotal
        - loss lines
        - **Losses** subtotal
        - RWA / other capital lines
        - **RWAs and other capital items** subtotal
        - **Drawdown pre-SMA**
        - **SMAs**
        - **Drawdown post-SMA**
        - **Stress test low-point**
        """
    )
    st.latex(r"RWA_{start} = \frac{CET1_{start}}{CET1Ratio_{start}}")
    st.latex(r"Assets_{start} = \frac{RWA_{start}}{RWA\ Density_{archetype}}")
    st.latex(r"Net\ income\ less\ expenses = NII + Fees + Traded\ income - Opex")
    st.latex(r"Losses = Impairments + Traded\ risk\ losses + Misconduct + Operational\ risk")
    st.latex(r"RWAs\ and\ other\ capital\ items = RWA\ effect + Tax/Other\ P\&L\ and\ capital - Distributions")
    st.latex(r"Low\ point_{pre\text{-}SMA} = Start + Net\ income\ less\ expenses - Losses + RWAs\ and\ other\ capital\ items")
    st.latex(r"Low\ point_{post\text{-}SMA} = Low\ point_{pre\text{-}SMA} + SMA")

    st.markdown(
        """
        **Why this is the right move**
        - It matches the presentation style in your screenshot much more closely.
        - It separates income, losses, and denominator/capital effects cleanly.
        - It gives you the same supervisory-story logic: pre-SMA drawdown, then management action recovery, then low-point.

        **How the geopolitical model maps in**
        - sanctions / corridor losses sit inside **Tax and other P&L and capital**
        - cyber / disruption sits inside **Operational risk**
        - RWA inflation sits in **RWAs/Leverage exposure**
        """
    )

with tab4:
    st.subheader("Governance, Limits, and Why This Mapping Is Defensible")
    st.markdown(
        """
        #### Why I agree with the change
        The structure in your screenshot is more coherent for senior banking audiences than the earlier bridge. It shows the stress narrative in the sequence they usually expect: earnings, losses, denominator/capital effects, then management actions.

        #### What is aligned
        - The waterfall line items and subtotals now follow the same style and sequencing.
        - The chart is presented in **CET1 ratio percentage points**, not just dollar losses.
        - Pre-SMA and post-SMA drawdowns are shown explicitly.

        #### What is not a literal replication
        - This is still your geopolitical scenario, not a Bank Capital Stress Test replication.
        - The BoE's leverage ratio column is not built here.
        - SMAs are stylized management actions rather than a regulatory-authorized treatment.
        - Tax and other P&L / capital is a scenario-mapped bucket, not a full accounting engine.
        """
    )

with tab5:
    st.subheader("How to Use This in a Client or Partner Discussion")
    st.markdown(
        """
        > **"Can we present this in the same style as the Bank of England table?"**
        - Yes. The CET1 ratio bridge now follows that Year 1 presentation logic.

        > **"Where do geopolitical effects show up?"**
        - Credit stress shows up in **Impairments**, cyber shows up in **Operational risk**, and sanctions/corridor effects are embedded in **Tax and other P&L and capital**.

        > **"Can we explain management actions clearly?"**
        - Yes. The model now shows **Drawdown pre-SMA**, then **SMAs**, then **Drawdown post-SMA**.

        > **"Does this make the chart easier to compare with published stress tests?"**
        - Yes, at the presentation level, while still preserving your own scenario economics.
        """
    )
