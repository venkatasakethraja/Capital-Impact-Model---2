import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="EY | Geopolitical Bank Capital Stress Dashboard (Recalibrated)",
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


# -----------------------------
# Header
# -----------------------------
st.markdown(
    "<h1 style='color:#FFE600;'>EY | Geopolitical Bank Capital Stress Dashboard</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "*Recalibrated version: reconciled opening CET1 ratio, saner loss magnitudes, and consistent one-year-style stress interpretation*"
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
    sanctions_exposure = st.slider("Direct Exposure to Sanctions / Cross-Border Corridor Risk", 0.0, 1.5, 0.5, 0.1)
    cyber_vulnerability = st.slider("Operational / Cyber Vulnerability", 0.5, 1.5, 1.0, 0.1)
    vulnerable_sector_share = st.slider("Vulnerable Sector Share of Loan Book (%)", 5, 50, 20, 1) / 100.0

    st.markdown("---")
    st.markdown("<h2 style='color:#FFE600;'>Management Actions</h2>", unsafe_allow_html=True)
    cancel_distributions = st.checkbox("Cancel dividends / buybacks", value=True)
    enable_hedging = st.checkbox("Assume partial hedging benefit", value=True)
    enable_rwa_mitigation = st.checkbox("Assume moderate RWA mitigation", value=False)

    st.markdown("---")
    st.markdown("<h2 style='color:#FFE600;'>Optional Overrides</h2>", unsafe_allow_html=True)
    enable_overrides = st.checkbox("Enable calibration overrides", value=False)

    if enable_overrides:
        base_pd = st.slider("Base PD (%)", 0.3, 3.0, 1.2, 0.1) / 100
        downturn_lgd = st.slider("Downturn LGD (%)", 25, 65, 40, 5) / 100
        deposit_beta = st.slider("Deposit Beta", 0.1, 1.0, 0.4, 0.05)
        annual_ppnr_to_rwa = st.slider("Annual PPNR / RWA (%)", 0.3, 2.5, 1.0, 0.1) / 100
        payout_ratio = st.slider("Baseline Capital Distribution Ratio (%)", 0, 60, 20, 5) / 100
        hedge_offset = st.slider("Market Hedging Offset (%)", 0, 50, 15, 5) / 100
        rwa_mitigation_pct = st.slider("RWA Mitigation on Add-ons (%)", 0, 20, 6, 1) / 100
    else:
        base_pd = 0.012
        downturn_lgd = 0.40
        deposit_beta = 0.40
        annual_ppnr_to_rwa = 0.010
        payout_ratio = 0.20
        hedge_offset = 0.15
        rwa_mitigation_pct = 0.06


# -----------------------------
# Reconciled opening balance sheet
# -----------------------------
profile_map = {
    "Universal Bank": {
        "rwa_density": 0.58,
        "loan_share_assets": 0.54,
        "banking_book_securities_share_assets": 0.18,
        "trading_book_share_assets": 0.06,
        "wholesale_funding_share_assets": 0.22,
        "deposit_share_assets": 0.62,
        "direct_exposure_share_assets": 0.018,
        "loan_rwa_density": 0.70,
        "irrbb_duration": 3.8,
        "trading_duration": 1.8,
    },
    "Wholesale / Markets Heavy": {
        "rwa_density": 0.62,
        "loan_share_assets": 0.42,
        "banking_book_securities_share_assets": 0.13,
        "trading_book_share_assets": 0.12,
        "wholesale_funding_share_assets": 0.34,
        "deposit_share_assets": 0.42,
        "direct_exposure_share_assets": 0.030,
        "loan_rwa_density": 0.75,
        "irrbb_duration": 3.4,
        "trading_duration": 2.1,
    },
    "Retail / Deposit Heavy": {
        "rwa_density": 0.52,
        "loan_share_assets": 0.63,
        "banking_book_securities_share_assets": 0.20,
        "trading_book_share_assets": 0.03,
        "wholesale_funding_share_assets": 0.10,
        "deposit_share_assets": 0.76,
        "direct_exposure_share_assets": 0.010,
        "loan_rwa_density": 0.60,
        "irrbb_duration": 4.1,
        "trading_duration": 1.2,
    },
    "EM / Cross-Border Heavy": {
        "rwa_density": 0.65,
        "loan_share_assets": 0.50,
        "banking_book_securities_share_assets": 0.16,
        "trading_book_share_assets": 0.05,
        "wholesale_funding_share_assets": 0.26,
        "deposit_share_assets": 0.55,
        "direct_exposure_share_assets": 0.035,
        "loan_rwa_density": 0.80,
        "irrbb_duration": 3.6,
        "trading_duration": 1.9,
    },
}

p = profile_map[bank_profile]

base_rwa = starting_cet1 / (baseline_cet1_ratio / 100.0)
total_assets = base_rwa / p["rwa_density"]
loan_book = total_assets * p["loan_share_assets"]
banking_book_securities = total_assets * p["banking_book_securities_share_assets"]
trading_book = total_assets * p["trading_book_share_assets"]
wholesale_funding = total_assets * p["wholesale_funding_share_assets"]
deposit_base = total_assets * p["deposit_share_assets"]
direct_exposure_base = total_assets * p["direct_exposure_share_assets"]

opening_ratio_check = (starting_cet1 / base_rwa) * 100 if base_rwa > 0 else 0.0


# -----------------------------
# Stage 1: Geopolitical -> macro translation
# -----------------------------
# Interpret as peak one-year stress conditions rather than cumulative multi-year losses.
duration_factor = clamp(0.65 + 0.35 * duration_years, 0.70, 1.40)

oil_peak = 75 + (severity * 6 * oil_dependency) * duration_factor
yield_shock_bps = (severity * 8 + duration_years * 20) * duration_factor
credit_spread_shock_bps = (severity * 10 + duration_years * 18) * duration_factor
wholesale_funding_spread_bps = (severity * 9 + duration_years * 14) * duration_factor
fx_stress_index = (severity * 0.45 + duration_years * 0.60) * (1 + 0.35 * sanctions_exposure)

macro_multiplier = 1 + 0.035 * severity + 0.04 * duration_years


# -----------------------------
# Stage 2: Transmission channels
# -----------------------------
# 1) Market channel
irrbb_yield_decimal = yield_shock_bps / 10000
credit_spread_decimal = credit_spread_shock_bps / 10000

raw_irrbb_loss = banking_book_securities * p["irrbb_duration"] * irrbb_yield_decimal * 0.55
raw_trading_loss = trading_book * p["trading_duration"] * (0.45 * irrbb_yield_decimal + 0.55 * credit_spread_decimal)
raw_market_loss = raw_irrbb_loss + raw_trading_loss
hedging_benefit = raw_market_loss * hedge_offset if enable_hedging else 0.0
market_loss = max(0.0, raw_market_loss - hedging_benefit)

# 2) Credit channel
pd_multiplier = (
    1
    + 0.30 * max(0, (oil_peak - 75) / 100)
    + 0.45 * (yield_shock_bps / 1000)
    + 0.35 * (credit_spread_shock_bps / 1000)
)
pd_multiplier *= (1 + 0.18 * duration_years)
pd_multiplier *= macro_multiplier

sector_overlay = 1 + vulnerable_sector_share * (0.35 * oil_dependency + 0.25 * sanctions_exposure)
stressed_pd = clamp(base_pd * pd_multiplier * sector_overlay, base_pd, 0.08)
stressed_lgd = clamp(
    downturn_lgd * (1 + 0.04 * severity / 10 + 0.04 * max(0.0, duration_years - 1.0)),
    downturn_lgd,
    0.60,
)
credit_loss_gross = loan_book * stressed_pd * stressed_lgd

ppnr_pre_stress = base_rwa * annual_ppnr_to_rwa
ppnr_stress_factor = clamp(1 - (0.035 * severity + 0.02 * max(0.0, duration_years - 1.0)), 0.50, 0.95)
stressed_ppnr = ppnr_pre_stress * ppnr_stress_factor
credit_loss = max(0.0, credit_loss_gross - stressed_ppnr)

# 3) Liquidity / funding channel
wholesale_funding_cost = wholesale_funding * (wholesale_funding_spread_bps / 10000) * 0.65
deposit_repricing_cost = deposit_base * (yield_shock_bps / 10000) * deposit_beta * 0.06
deposit_runoff_rate = clamp(
    0.0025 * severity * (0.75 + 0.25 * duration_years) * (0.7 + 0.3 * sanctions_exposure),
    0.0,
    0.04,
)
runoff_replacement_cost = deposit_base * deposit_runoff_rate * (wholesale_funding_spread_bps / 10000) * 0.30
liquidity_buffer_usage = total_assets * 0.0008 * severity * (0.6 + 0.4 * min(duration_years, 2.0))
funding_liquidity_loss = (
    wholesale_funding_cost
    + deposit_repricing_cost
    + runoff_replacement_cost
    + liquidity_buffer_usage
)

# 4) Direct exposure / sanctions / corridor disruption
direct_exposure_loss = direct_exposure_base * sanctions_exposure * (
    0.015 * severity + 0.010 * max(duration_years, 0.5)
)

# 5) Operational / cyber resilience
# Event-style calibration to avoid runaway losses.
ops_event_rate = (0.0006 + 0.00045 * severity + 0.00025 * max(0.0, duration_years - 1.0)) * cyber_vulnerability
ops_event_rate = clamp(ops_event_rate, 0.0005, 0.0080)
operational_cyber_loss = total_assets * ops_event_rate


# -----------------------------
# Stage 3: RWA inflation and capital actions
# -----------------------------
credit_rwa_inflation = loan_book * p["loan_rwa_density"] * (0.010 + 0.0035 * severity) * (0.85 + 0.15 * min(duration_years, 2.0))
market_rwa_inflation = trading_book * 0.20 * (0.010 + 0.003 * severity)
ccr_cva_rwa_inflation = max(trading_book, direct_exposure_base * 3.0) * 0.12 * 0.01 * severity * (1 + 0.25 * sanctions_exposure)
fx_rwa_inflation = base_rwa * 0.0008 * fx_stress_index
operational_rwa_inflation = base_rwa * 0.0006 * severity * cyber_vulnerability

gross_rwa_addon = (
    credit_rwa_inflation
    + market_rwa_inflation
    + ccr_cva_rwa_inflation
    + fx_rwa_inflation
    + operational_rwa_inflation
)
rwa_mitigation = gross_rwa_addon * rwa_mitigation_pct if enable_rwa_mitigation else 0.0
stressed_rwa = base_rwa + gross_rwa_addon - rwa_mitigation

capital_distribution_saved = base_rwa * annual_ppnr_to_rwa * payout_ratio if cancel_distributions else 0.0

loss_components = {
    "Market": market_loss,
    "Credit": credit_loss,
    "Liquidity / Funding": funding_liquidity_loss,
    "Direct Exposure / Sanctions": direct_exposure_loss,
    "Operational / Cyber": operational_cyber_loss,
}

total_depletion = sum(loss_components.values())
stressed_cet1 = starting_cet1 - total_depletion + capital_distribution_saved
stressed_cet1_ratio = (stressed_cet1 / stressed_rwa) * 100 if stressed_rwa > 0 else 0.0

required_cet1_ratio = 9.0
buffer_headroom = stressed_cet1_ratio - required_cet1_ratio
breach_indicator = 99.5 if buffer_headroom <= 0 else clamp(100 - buffer_headroom * 13, 1, 95)


# -----------------------------
# Tabs
# -----------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📊 Dashboard",
        "🧠 Channel Decomposition",
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
    m4.metric("Funding Spread Shock", bps(wholesale_funding_spread_bps))
    m5.metric("FX / Fragmentation Index", f"{fx_stress_index:.1f}")

    st.markdown("---")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Starting CET1 Ratio", f"{opening_ratio_check:.1f}%")
    c2.metric(
        "Stressed CET1 Ratio",
        f"{stressed_cet1_ratio:.1f}%",
        f"{stressed_cet1_ratio - opening_ratio_check:.1f}%",
        delta_color="inverse",
    )
    c3.metric("Capital Depletion", usd_billions(total_depletion))
    c4.metric("Breach Indicator", f"{breach_indicator:.1f}%", delta_color="inverse")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Starting RWA", usd_billions(base_rwa))
    c6.metric("Stressed RWA", usd_billions(stressed_rwa), usd_billions(stressed_rwa - base_rwa))
    c7.metric("Stressed PPNR Offset", usd_billions(stressed_ppnr))
    c8.metric("Capital Actions Saved", usd_billions(capital_distribution_saved))

    wf = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "relative", "relative", "relative", "total"],
            x=[
                "Starting CET1",
                "Market",
                "Credit",
                "Liquidity / Funding",
                "Direct Exposure / Sanctions",
                "Operational / Cyber",
                "Capital Actions",
                "Stressed CET1",
            ],
            y=[
                starting_cet1,
                -market_loss,
                -credit_loss,
                -funding_liquidity_loss,
                -direct_exposure_loss,
                -operational_cyber_loss,
                capital_distribution_saved,
                stressed_cet1,
            ],
            text=[
                usd_billions(starting_cet1),
                f"-{usd_billions(market_loss)}",
                f"-{usd_billions(credit_loss)}",
                f"-{usd_billions(funding_liquidity_loss)}",
                f"-{usd_billions(direct_exposure_loss)}",
                f"-{usd_billions(operational_cyber_loss)}",
                usd_billions(capital_distribution_saved),
                usd_billions(stressed_cet1),
            ],
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
        title="Capital Depletion Waterfall",
        showlegend=False,
        height=520,
        margin=dict(l=20, r=20, t=50, b=20),
        font=dict(color="#FFFFFF"),
    )
    st.plotly_chart(wf, use_container_width=True)

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

            **Market channel**
            - Raw IRRBB loss = **{usd_billions(raw_irrbb_loss)}**
            - Raw trading / FV loss = **{usd_billions(raw_trading_loss)}**
            - Hedging benefit = **{usd_billions(hedging_benefit)}**
            - Net market loss = **{usd_billions(market_loss)}**

            **Credit channel**
            - Stressed PD = **{stressed_pd * 100:.2f}%**
            - Stressed LGD = **{stressed_lgd * 100:.1f}%**
            - Gross credit loss = **{usd_billions(credit_loss_gross)}**
            - Stressed PPNR offset = **{usd_billions(stressed_ppnr)}**
            - Net credit loss through CET1 = **{usd_billions(credit_loss)}**

            **Liquidity / funding channel**
            - Wholesale repricing = **{usd_billions(wholesale_funding_cost)}**
            - Deposit repricing = **{usd_billions(deposit_repricing_cost)}**
            - Deposit runoff replacement cost = **{usd_billions(runoff_replacement_cost)}**
            - Liquidity buffer usage = **{usd_billions(liquidity_buffer_usage)}**

            **Direct exposure / sanctions**
            - Net direct exposure loss = **{usd_billions(direct_exposure_loss)}**

            **Operational / cyber**
            - Event-style operational / cyber loss = **{usd_billions(operational_cyber_loss)}**

            **RWA inflation**
            - Credit RWA uplift = **{usd_billions(credit_rwa_inflation)}**
            - Market RWA uplift = **{usd_billions(market_rwa_inflation)}**
            - CCR / CVA uplift = **{usd_billions(ccr_cva_rwa_inflation)}**
            - FX / fragmentation uplift = **{usd_billions(fx_rwa_inflation)}**
            - Operational RWA uplift = **{usd_billions(operational_rwa_inflation)}**
            - RWA mitigation benefit = **{usd_billions(rwa_mitigation)}**
            """
        )

with tab2:
    st.subheader("MECE Channel Structure")

    channel_df = pd.DataFrame(
        {
            "Channel": list(loss_components.keys()),
            "Loss ($B)": list(loss_components.values()),
            "% of Total": [x / total_depletion * 100 if total_depletion > 0 else 0 for x in loss_components.values()],
            "Primary Driver": [
                "Rates + spreads net of hedging",
                "Borrower default and vulnerable-sector overlay, net of PPNR",
                "Wholesale repricing + deposit pass-through + runoff",
                "Sanctions + settlement friction + trapped flows",
                "Cyber / operational event loss",
            ],
        }
    )
    st.dataframe(channel_df, use_container_width=True, hide_index=True)

    donut = go.Figure(
        data=[
            go.Pie(
                labels=channel_df["Channel"],
                values=channel_df["Loss ($B)"],
                hole=0.50,
                textinfo="label+percent",
            )
        ]
    )
    donut.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        title="Loss Composition by Channel",
        height=520,
    )
    st.plotly_chart(donut, use_container_width=True)

    st.markdown(
        """
        **Design principle:** channels remain deliberately transparent and separately challengeable.

        This build is meant to feel like a credible advisory translation of a geopolitical stress, not a black-box regulatory engine and not a catastrophe generator.
        """
    )

with tab3:
    st.subheader("Methodology")
    st.markdown(
        """
        The engine has three layers.

        ### Stage 1 — Translate conflict into peak one-year macro-financial shocks
        Severity and duration shape oil, rates, spreads, funding pressure, and an FX/fragmentation index.
        """
    )
    st.latex(r"RWA_{start} = \frac{CET1_{start}}{CET1Ratio_{start}}")
    st.latex(r"Assets_{start} = \frac{RWA_{start}}{RWA\ Density_{archetype}}")
    st.latex(r"\Delta Y, \Delta CS, \Delta F = f(Severity, Duration)")

    st.markdown("### Stage 2 — Apply five distinct loss channels")
    st.latex(r"L_{market} = L_{IRRBB} + L_{trading} - HedgeBenefit")
    st.latex(r"L_{credit} = LoanBook \times PD_{stressed} \times LGD_{stressed} - PPNR_{stressed}")
    st.latex(r"L_{liq} = WholesaleRepricing + DepositPassThrough + RunoffCost + BufferUsage")
    st.latex(r"L_{direct} = DirectExposure \times StressFactor")
    st.latex(r"L_{ops} = Assets \times EventRate")

    st.markdown("### Stage 3 — Stress both numerator and denominator")
    st.latex(r"CET1_{stressed} = CET1_{start} - \sum L_i + CapitalActions")
    st.latex(r"RWA_{stressed} = RWA_{start} + \sum \Delta RWA_i - Mitigation")
    st.latex(r"CET1Ratio_{stressed} = \frac{CET1_{stressed}}{RWA_{stressed}}")

    st.markdown(
        """
        **What is fixed in this recalibrated version**
        - Opening CET1 ratio now truly reconciles to opening RWA.
        - Exposures are derived from total assets using an archetype RWA density, avoiding runaway scaling.
        - Operational / cyber is now calibrated as a capped event-style loss rather than a large recurring-cost multiplier.
        - Duration is interpreted as shaping a **peak stress year**, not mechanically compounding every channel.
        - Credit, funding, and RWA inflation are all brought back into advisory-plausible ranges.
        """
    )

with tab4:
    st.subheader("Model Governance, Limits, and How to Defend It")
    st.markdown(
        """
        #### What this model is
        A transparent advisory stress model for scenario discussion.

        #### What this model is not
        It is **not** a regulatory capital engine, CCAR model, ICAAP model, or legal view on sanctions exposure.

        #### Defensible assumptions in this build
        - **Reconciled opening ratio:** opening CET1 and RWA tie exactly.
        - **Archetype RWA density:** links RWA back to a more sensible asset base.
        - **Named channels:** each loss bucket maps to a clear mechanism.
        - **PPNR and capital actions:** provides a more realistic pre-CET1 absorption narrative.
        - **Numerator and denominator stress:** both capital and RWA move under stress.

        #### Limitations
        - Coefficients remain illustrative rather than empirically estimated.
        - No obligor-level PD migration, staging, or asset-class-specific LGD.
        - No accounting treatment split across OCI, P&L, AFS, HTM, or hedge designation.
        - No explicit LCR / NSFR engine, collateral waterfall, or central-bank facility modeling.
        - No multi-period balance-sheet evolution or management reaction function.
        - The breach indicator is heuristic, not statistical.
        """
    )

with tab5:
    st.subheader("How to Use This in a Partner or Client Meeting")
    st.markdown(
        """
        > **"Which channel hurts us most if the conflict is short but severe versus persistent but moderate?"**
        - Compare a high-severity 3-month case with a moderate-severity 24-month case.

        > **"How much of the downside is absorbed before CET1 is hit?"**
        - Focus on PPNR offset and capital actions.

        > **"Is our ratio falling more because of losses or because of RWA inflation?"**
        - Keep severity constant and vary duration.

        > **"How much downside is direct regional exposure versus global market repricing?"**
        - Increase sanctions exposure while keeping oil sensitivity steady.

        > **"Would a retail-heavy bank or a markets-heavy bank be more resilient?"**
        - Switch archetypes and compare both loss mix and final ratio.
        """
    )
