import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="EY | Geopolitical Bank Capital Stress Dashboard (Rebuilt)",
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


def pct(x: float) -> str:
    return f"{x:.1f}%"


# -----------------------------
# Header
# -----------------------------
st.markdown(
    "<h1 style='color:#FFE600;'>EY | Geopolitical Bank Capital Stress Dashboard</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "*Rebuilt version: reconciled CET1 math, RWA-based balance sheet, PPNR absorption, management actions, and stronger stress logic*"
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

    oil_dependency = st.slider(
        "Portfolio Sensitivity to Energy / Oil Shock", 0.5, 1.5, 1.0, 0.1
    )
    sanctions_exposure = st.slider(
        "Direct Exposure to Sanctions / Cross-Border Corridor Risk", 0.0, 1.5, 0.5, 0.1
    )
    cyber_vulnerability = st.slider(
        "Operational / Cyber Vulnerability", 0.5, 1.5, 1.0, 0.1
    )
    vulnerable_sector_share = st.slider(
        "Vulnerable Sector Share of Loan Book", 5, 50, 20, 1
    ) / 100.0

    st.markdown("---")
    st.markdown("<h2 style='color:#FFE600;'>Management Actions</h2>", unsafe_allow_html=True)
    cancel_distributions = st.checkbox("Cancel dividends / buybacks", value=True)
    enable_hedging = st.checkbox("Assume partial hedging benefit", value=True)
    enable_rwa_mitigation = st.checkbox("Assume moderate RWA mitigation", value=False)

    st.markdown("---")
    st.markdown("<h2 style='color:#FFE600;'>Optional Overrides</h2>", unsafe_allow_html=True)
    enable_overrides = st.checkbox("Enable calibration overrides", value=False)

    if enable_overrides:
        base_pd = st.slider("Base PD (%)", 0.5, 5.0, 2.0, 0.1) / 100
        downturn_lgd = st.slider("Downturn LGD (%)", 20, 75, 45, 5) / 100
        deposit_beta = st.slider("Deposit Beta", 0.1, 1.0, 0.5, 0.05)
        annual_ppnr_roa = st.slider("Annual PPNR / RWA (%)", 0.2, 3.0, 1.2, 0.1) / 100
        payout_ratio = st.slider("Baseline Capital Distribution Ratio (%)", 0, 60, 25, 5) / 100
        hedge_offset = st.slider("Market Hedging Offset (%)", 0, 50, 20, 5) / 100
        rwa_mitigation_pct = st.slider("RWA Mitigation (%)", 0, 20, 8, 1) / 100
    else:
        base_pd = 0.020
        downturn_lgd = 0.45
        deposit_beta = 0.50
        annual_ppnr_roa = 0.012
        payout_ratio = 0.25
        hedge_offset = 0.20
        rwa_mitigation_pct = 0.08


# -----------------------------
# RWA-based balance sheet archetypes
# -----------------------------
profile_map = {
    "Universal Bank": {
        "loan_book_to_rwa": 1.55,
        "banking_book_securities_to_rwa": 0.55,
        "trading_book_to_rwa": 0.18,
        "wholesale_funding_to_rwa": 0.70,
        "deposit_base_to_rwa": 1.40,
        "direct_exposure_to_rwa": 0.06,
        "ops_cost_to_rwa": 0.012,
        "irrbb_duration": 4.8,
        "trading_duration": 2.2,
        "avg_loan_rw": 0.65,
    },
    "Wholesale / Markets Heavy": {
        "loan_book_to_rwa": 1.20,
        "banking_book_securities_to_rwa": 0.40,
        "trading_book_to_rwa": 0.32,
        "wholesale_funding_to_rwa": 1.00,
        "deposit_base_to_rwa": 0.95,
        "direct_exposure_to_rwa": 0.10,
        "ops_cost_to_rwa": 0.015,
        "irrbb_duration": 4.2,
        "trading_duration": 2.8,
        "avg_loan_rw": 0.70,
    },
    "Retail / Deposit Heavy": {
        "loan_book_to_rwa": 1.85,
        "banking_book_securities_to_rwa": 0.62,
        "trading_book_to_rwa": 0.08,
        "wholesale_funding_to_rwa": 0.30,
        "deposit_base_to_rwa": 1.75,
        "direct_exposure_to_rwa": 0.03,
        "ops_cost_to_rwa": 0.010,
        "irrbb_duration": 5.2,
        "trading_duration": 1.7,
        "avg_loan_rw": 0.55,
    },
    "EM / Cross-Border Heavy": {
        "loan_book_to_rwa": 1.45,
        "banking_book_securities_to_rwa": 0.48,
        "trading_book_to_rwa": 0.15,
        "wholesale_funding_to_rwa": 0.78,
        "deposit_base_to_rwa": 1.25,
        "direct_exposure_to_rwa": 0.12,
        "ops_cost_to_rwa": 0.014,
        "irrbb_duration": 4.6,
        "trading_duration": 2.4,
        "avg_loan_rw": 0.75,
    },
}

p = profile_map[bank_profile]

# Reconciled opening denominator: CET1 ratio actually drives opening RWA
base_rwa = starting_cet1 / (baseline_cet1_ratio / 100.0)
loan_book = base_rwa * p["loan_book_to_rwa"]
banking_book_securities = base_rwa * p["banking_book_securities_to_rwa"]
trading_book = base_rwa * p["trading_book_to_rwa"]
wholesale_funding = base_rwa * p["wholesale_funding_to_rwa"]
deposit_base = base_rwa * p["deposit_base_to_rwa"]
direct_exposure_base = base_rwa * p["direct_exposure_to_rwa"]
ops_cost_base = base_rwa * p["ops_cost_to_rwa"]


# -----------------------------
# Stage 1: Geopolitical -> macro translation
# -----------------------------
oil_peak = 75 + (severity * 8 * oil_dependency) * (1 + 0.35 * duration_years)
yield_shock_bps = (severity * 10) + (duration_years * 45)
credit_spread_shock_bps = (severity * 12) + (duration_years * 25)
wholesale_funding_spread_bps = (severity * 11) + (duration_years * 20)
fx_stress_index = (severity * 0.7 + duration_years * 1.2) * (1 + 0.4 * sanctions_exposure)

macro_multiplier = 1 + 0.05 * severity + 0.08 * duration_years


# -----------------------------
# Stage 2: Transmission channels
# -----------------------------
# 1) Market channel: IRRBB and trading/fair-value stress, with optional hedging offset
irrbb_yield_decimal = yield_shock_bps / 10000
credit_spread_decimal = credit_spread_shock_bps / 10000

raw_irrbb_loss = banking_book_securities * p["irrbb_duration"] * irrbb_yield_decimal
raw_trading_loss = trading_book * p["trading_duration"] * (
    0.55 * irrbb_yield_decimal + 0.45 * credit_spread_decimal
)
raw_market_loss = raw_irrbb_loss + raw_trading_loss
hedging_benefit = raw_market_loss * hedge_offset if enable_hedging else 0.0
market_loss = max(0.0, raw_market_loss - hedging_benefit)

# 2) Credit channel: stressed PD + vulnerable sectors + downturn LGD + PPNR absorption
pd_multiplier = (
    1
    + 0.60 * max(0, (oil_peak - 75) / 100)
    + 0.90 * (yield_shock_bps / 1000)
    + 0.50 * (credit_spread_shock_bps / 1000)
) * (1 + 0.35 * duration_years)
pd_multiplier *= macro_multiplier

sector_overlay = 1 + vulnerable_sector_share * (0.8 * oil_dependency + 0.4 * sanctions_exposure)
stressed_pd = clamp(base_pd * pd_multiplier * sector_overlay, base_pd, 0.25)
stressed_lgd = clamp(
    downturn_lgd * (1 + 0.10 * severity / 10 + 0.08 * duration_years),
    downturn_lgd,
    0.85,
)
credit_loss_gross = loan_book * stressed_pd * stressed_lgd

# PPNR as first line of defense against losses
ppnr_pre_stress = base_rwa * annual_ppnr_roa * duration_years
ppnr_stress_factor = clamp(1 - (0.05 * severity + 0.03 * duration_years), 0.35, 0.95)
stressed_ppnr = ppnr_pre_stress * ppnr_stress_factor
credit_loss = max(0.0, credit_loss_gross - stressed_ppnr)

# 3) Liquidity / funding channel: wholesale repricing + deposit repricing + runoff penalty
wholesale_funding_cost = wholesale_funding * (wholesale_funding_spread_bps / 10000) * (
    0.75 + 0.25 * duration_years
)
deposit_repricing_cost = deposit_base * (yield_shock_bps / 10000) * deposit_beta * 0.15
deposit_runoff_rate = clamp(
    0.01 * severity * (0.5 + 0.5 * duration_years) * (0.6 + 0.4 * sanctions_exposure),
    0.0,
    0.20,
)
runoff_replacement_cost = deposit_base * deposit_runoff_rate * (
    wholesale_funding_spread_bps / 10000
) * 0.50
liquidity_buffer_usage = base_rwa * 0.003 * severity * (0.5 + 0.5 * duration_years)
funding_liquidity_loss = (
    wholesale_funding_cost
    + deposit_repricing_cost
    + runoff_replacement_cost
    + liquidity_buffer_usage
)

# 4) Direct exposure / sanctions / corridor disruption
sanctions_loss = (
    direct_exposure_base
    * sanctions_exposure
    * (0.03 * severity)
    * (1 + 0.30 * duration_years)
)
settlement_and_corridor_loss = (
    direct_exposure_base * sanctions_exposure * 0.01 * (severity ** 1.15)
)
direct_exposure_loss = sanctions_loss + settlement_and_corridor_loss

# 5) Operational / cyber resilience
ops_loss = ops_cost_base * cyber_vulnerability * (0.45 * severity + 0.35 * duration_years)
fraud_and_recovery_loss = base_rwa * 0.0015 * severity * cyber_vulnerability
operational_cyber_loss = ops_loss + fraud_and_recovery_loss


# -----------------------------
# Stage 3: RWA inflation and management actions
# -----------------------------
credit_rwa_inflation = base_rwa * 0.012 * severity * (1 + 0.30 * duration_years)
market_rwa_inflation = base_rwa * 0.006 * severity * (1 + p["trading_book_to_rwa"] * 0.50)
ccr_cva_rwa_inflation = base_rwa * 0.004 * severity * (1 + sanctions_exposure)
fx_rwa_inflation = base_rwa * 0.002 * fx_stress_index
operational_rwa_inflation = base_rwa * 0.0015 * severity * cyber_vulnerability

gross_rwa_addon = (
    credit_rwa_inflation
    + market_rwa_inflation
    + ccr_cva_rwa_inflation
    + fx_rwa_inflation
    + operational_rwa_inflation
)
rwa_mitigation = gross_rwa_addon * rwa_mitigation_pct if enable_rwa_mitigation else 0.0
stressed_rwa = base_rwa + gross_rwa_addon - rwa_mitigation

# Capital actions
capital_distribution_saved = (
    base_rwa * annual_ppnr_roa * payout_ratio * duration_years if cancel_distributions else 0.0
)

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
breach_probability = 99.5 if buffer_headroom <= 0 else clamp(100 - buffer_headroom * 16, 1, 95)

opening_ratio_check = (starting_cet1 / base_rwa) * 100 if base_rwa > 0 else 0.0


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
    c4.metric("Buffer Breach Indicator", f"{breach_probability:.1f}%", delta_color="inverse")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Starting RWA", usd_billions(base_rwa))
    c6.metric("Stressed RWA", usd_billions(stressed_rwa), usd_billions(stressed_rwa - base_rwa))
    c7.metric("PPNR Offset", usd_billions(stressed_ppnr))
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

            **Opening balance sheet derived from reconciled starting ratio**
            - Starting CET1 = **{usd_billions(starting_cet1)}**
            - Baseline CET1 ratio = **{baseline_cet1_ratio:.1f}%**
            - Derived starting RWA = **{usd_billions(base_rwa)}**
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
            - Sanctions loss = **{usd_billions(sanctions_loss)}**
            - Settlement / corridor disruption = **{usd_billions(settlement_and_corridor_loss)}**

            **Operational / cyber**
            - Operational disruption = **{usd_billions(ops_loss)}**
            - Fraud / recovery = **{usd_billions(fraud_and_recovery_loss)}**

            **RWA inflation**
            - Credit RWA uplift = **{usd_billions(credit_rwa_inflation)}**
            - Market RWA uplift = **{usd_billions(market_rwa_inflation)}**
            - CCR / CVA uplift = **{usd_billions(ccr_cva_rwa_inflation)}**
            - FX / fragmentation uplift = **{usd_billions(fx_rwa_inflation)}**
            - Operational RWA uplift = **{usd_billions(operational_rwa_inflation)}**
            - RWA mitigation benefit = **{usd_billions(rwa_mitigation)}**

            **Capital actions**
            - Distributions saved = **{usd_billions(capital_distribution_saved)}**
            """
        )

with tab2:
    st.subheader("MECE Channel Structure")

    channel_df = pd.DataFrame(
        {
            "Channel": list(loss_components.keys()),
            "Loss ($B)": list(loss_components.values()),
            "% of Total": [
                x / total_depletion * 100 if total_depletion > 0 else 0 for x in loss_components.values()
            ],
            "Primary Driver": [
                "Rates + spreads net of hedging",
                "Borrower default, vulnerable sectors, downturn LGD, net of PPNR",
                "Wholesale spread + deposit repricing + runoff replacement",
                "Sanctions + trapped flows + settlement disruption",
                "Cyber + third-party + business continuity",
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
        **Design principle:** the model treats channels as **distinct first-order transmission mechanisms**:
        1. **Market** = valuation and fair-value effects from rates and spreads, net of simple hedging.
        2. **Credit** = borrower distress, sector overlays, downturn LGD, partially offset by PPNR.
        3. **Liquidity / Funding** = liability-side repricing, runoff replacement cost, and liquidity buffer usage.
        4. **Direct Exposure / Sanctions** = blocked assets, settlement friction, corridor interruption.
        5. **Operational / Cyber** = disruption, fraud, third-party outages, recovery cost.

        This is deliberately transparent rather than fully regulatory. The intent is defensible scenario translation, not black-box precision.
        """
    )

with tab3:
    st.subheader("Methodology")
    st.markdown(
        """
        The engine has three layers.

        ### Stage 1 — Translate conflict into macro-financial shocks
        Severity and duration drive oil, rates, spreads, funding pressure, and an FX/fragmentation index.
        """
    )
    st.latex(r"P_{oil} = 75 + (8S \times OilSensitivity) \times (1 + 0.35D)")
    st.latex(r"\Delta Y = 10S + 45D")
    st.latex(r"\Delta CS = 12S + 25D")
    st.latex(r"\Delta F = 11S + 20D")

    st.markdown("### Stage 2 — Apply five distinct loss channels")
    st.latex(r"L_{market} = L_{IRRBB} + L_{trading} - HedgeBenefit")
    st.latex(r"L_{credit} = LoanBook \times PD_{stressed} \times LGD_{downturn} - PPNR_{stressed}")
    st.latex(r"L_{liq} = WholesaleFunding \times \Delta F + DepositBase \times DepositBeta \times \Delta Y + RunoffCost + BufferUsage")
    st.latex(r"L_{direct} = SanctionsLoss + SettlementLoss")
    st.latex(r"L_{ops} = OpsDisruption + FraudRecovery")

    st.markdown("### Stage 3 — Stress both numerator and denominator")
    st.latex(r"CET1_{stressed} = CET1_{start} - \sum L_i + CapitalActions")
    st.latex(r"RWA_{stressed} = RWA_{start} + \Delta RWA_{credit} + \Delta RWA_{market} + \Delta RWA_{CCR/CVA} + \Delta RWA_{FX} + \Delta RWA_{ops} - Mitigation")
    st.latex(r"CET1Ratio_{stressed} = \frac{CET1_{stressed}}{RWA_{stressed}}")

    st.markdown(
        """
        **What changed in this rebuilt version**
        - Opening **RWA now reconciles exactly** to the selected baseline CET1 ratio.
        - Archetypes scale exposures from **RWA**, not directly from CET1.
        - Credit losses include **vulnerable-sector overlays**, **downturn LGD**, and **PPNR absorption**.
        - Management actions can reduce the capital hit through **distribution cancellation**, **partial hedging**, and **RWA mitigation**.
        - Operational risk now affects both **losses** and **RWA**.
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
        - **Reconciled opening ratio:** the opening CET1 ratio binds the denominator.
        - **Named channels:** each loss bucket maps to a clear mechanism.
        - **RWA-based archetype calibration:** better than pure CET1 scaling while still simple.
        - **Numerator + denominator stress:** both CET1 capital and RWA are stressed.
        - **PPNR and management actions:** allows a more realistic capital-absorption narrative.

        #### Limitations
        - Coefficients remain illustrative rather than empirically fitted.
        - No asset-class-level LGD, migration matrix, or obligor segmentation.
        - No legal-entity, jurisdiction, accounting, OCI/P&L, or hedge-designation treatment.
        - No explicit LCR / NSFR, collateral waterfall, or central-bank facility modeling.
        - No second-round macro feedback loops or dynamic balance-sheet evolution.
        - The breach indicator is heuristic, not a true statistical probability model.

        #### How to support the assumptions in a client-ready methodology note
        1. Map each coefficient to a public source range or internal benchmark range.
        2. Back-test directionally against selected historical episodes.
        3. Replace archetypes with client-specific balance-sheet inputs.
        4. Add sector overlays for CRE, energy, trade finance, sovereign, and leveraged lending.
        5. Add accounting views, management actions, and multi-period capital planning.
        """
    )

with tab5:
    st.subheader("How to Use This in a Partner or Client Meeting")
    st.markdown(
        """
        > **"Which channel hurts us most if the conflict is short but severe versus persistent but moderate?"**
        - Compare a high-severity 3-month case with a moderate-severity 24-month case.

        > **"Is our capital ratio falling more because of losses or because of RWA inflation?"**
        - Keep severity constant and vary duration to show denominator pressure.

        > **"How much downside is absorbed by earnings and management actions before CET1 is hit?"**
        - Toggle PPNR-related assumptions, capital distributions, and RWA mitigation.

        > **"How much of the downside is direct regional exposure versus global market repricing?"**
        - Increase sanctions exposure while keeping oil sensitivity steady.

        > **"Would a retail-heavy bank or a markets-heavy bank be more resilient?"**
        - Switch archetypes and compare loss composition and stressed ratio.

        > **"What happens if cyber escalation becomes the dominant second-order effect?"**
        - Raise cyber vulnerability to show how non-credit risks can dominate the tail.
        """
    )
