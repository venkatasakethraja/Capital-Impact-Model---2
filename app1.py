import math
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


# -----------------------------
# Sidebar inputs
# -----------------------------
st.markdown("<h1 style='color:#FFE600;'>EY | Geopolitical Bank Capital Stress Dashboard</h1>", unsafe_allow_html=True)
st.markdown("*Middle East conflict scenario translated into bank capital, liquidity, and RWA stress*")
st.markdown("---")

with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/EY_logo_2019.svg/512px-EY_logo_2019.svg.png",
        width=110,
    )
    st.markdown("<h2 style='color:#FFE600;'>Scenario Inputs</h2>", unsafe_allow_html=True)

    starting_cet1 = st.slider("Starting CET1 Capital ($B)", 10, 500, 250, 10)
    baseline_cet1_ratio = st.slider("Baseline CET1 Ratio (%)", 10.0, 16.0, 12.5, 0.1)
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

    st.markdown("---")
    st.markdown("<h2 style='color:#FFE600;'>Optional Overrides</h2>", unsafe_allow_html=True)
    enable_overrides = st.checkbox("Enable calibration overrides", value=False)

    if enable_overrides:
        lgd = st.slider("LGD (%)", 20, 70, 40, 5) / 100
        base_pd = st.slider("Base PD (%)", 0.5, 5.0, 2.0, 0.1) / 100
        deposit_beta = st.slider("Deposit Beta", 0.1, 1.0, 0.5, 0.05)
    else:
        lgd = 0.40
        base_pd = 0.020
        deposit_beta = 0.50


# -----------------------------
# Balance-sheet archetypes
# -----------------------------
profile_map = {
    "Universal Bank": {
        "loan_book_mult": 5.0,
        "banking_book_securities_mult": 1.8,
        "trading_book_mult": 0.6,
        "wholesale_funding_mult": 2.2,
        "deposit_base_mult": 4.5,
        "direct_exposure_mult": 0.20,
        "ops_cost_mult": 0.04,
        "base_rwa_density": 1 / 0.125,
        "irrbb_duration": 4.8,
        "trading_duration": 2.2,
    },
    "Wholesale / Markets Heavy": {
        "loan_book_mult": 4.2,
        "banking_book_securities_mult": 1.4,
        "trading_book_mult": 1.2,
        "wholesale_funding_mult": 3.2,
        "deposit_base_mult": 3.0,
        "direct_exposure_mult": 0.35,
        "ops_cost_mult": 0.05,
        "base_rwa_density": 1 / 0.120,
        "irrbb_duration": 4.2,
        "trading_duration": 2.8,
    },
    "Retail / Deposit Heavy": {
        "loan_book_mult": 5.8,
        "banking_book_securities_mult": 2.0,
        "trading_book_mult": 0.3,
        "wholesale_funding_mult": 1.0,
        "deposit_base_mult": 5.5,
        "direct_exposure_mult": 0.10,
        "ops_cost_mult": 0.03,
        "base_rwa_density": 1 / 0.130,
        "irrbb_duration": 5.2,
        "trading_duration": 1.7,
    },
    "EM / Cross-Border Heavy": {
        "loan_book_mult": 5.3,
        "banking_book_securities_mult": 1.6,
        "trading_book_mult": 0.5,
        "wholesale_funding_mult": 2.5,
        "deposit_base_mult": 4.0,
        "direct_exposure_mult": 0.45,
        "ops_cost_mult": 0.05,
        "base_rwa_density": 1 / 0.118,
        "irrbb_duration": 4.6,
        "trading_duration": 2.4,
    },
}

p = profile_map[bank_profile]
base_rwa = starting_cet1 * p["base_rwa_density"]
loan_book = starting_cet1 * p["loan_book_mult"]
banking_book_securities = starting_cet1 * p["banking_book_securities_mult"]
trading_book = starting_cet1 * p["trading_book_mult"]
wholesale_funding = starting_cet1 * p["wholesale_funding_mult"]
deposit_base = starting_cet1 * p["deposit_base_mult"]
direct_exposure_base = starting_cet1 * p["direct_exposure_mult"]
ops_cost_base = starting_cet1 * p["ops_cost_mult"]


# -----------------------------
# Stage 1: Geopolitical -> macro translation
# -----------------------------
oil_peak = 75 + (severity * 8 * oil_dependency) * (1 + 0.35 * duration_years)
yield_shock_bps = (severity * 10) + (duration_years * 45)
credit_spread_shock_bps = (severity * 12) + (duration_years * 25)
wholesale_funding_spread_bps = (severity * 11) + (duration_years * 20)
fx_stress_index = (severity * 0.7 + duration_years * 1.2) * (1 + 0.4 * sanctions_exposure)

# Slight non-linearity, but bounded for explainability
macro_multiplier = 1 + 0.05 * severity + 0.08 * duration_years


# -----------------------------
# Stage 2: Transmission channels
# -----------------------------
# 1) Market channel: separate IRRBB and trading/fair value stress
irrbb_yield_decimal = yield_shock_bps / 10000
credit_spread_decimal = credit_spread_shock_bps / 10000

irrbb_loss = banking_book_securities * p["irrbb_duration"] * irrbb_yield_decimal
trading_loss = trading_book * p["trading_duration"] * (0.55 * irrbb_yield_decimal + 0.45 * credit_spread_decimal)
market_loss = irrbb_loss + trading_loss

# 2) Credit channel: PD stress from oil, rates, spreads, and scenario duration
pd_multiplier = (
    1
    + 0.60 * max(0, (oil_peak - 75) / 100)
    + 0.90 * (yield_shock_bps / 1000)
    + 0.50 * (credit_spread_shock_bps / 1000)
) * (1 + 0.35 * duration_years)
pd_multiplier *= macro_multiplier
stressed_pd = clamp(base_pd * pd_multiplier, base_pd, 0.20)
credit_loss = loan_book * stressed_pd * lgd

# 3) Liquidity / funding channel: wholesale repricing + deposit pass-through
wholesale_funding_cost = wholesale_funding * (wholesale_funding_spread_bps / 10000) * (0.75 + 0.25 * duration_years)
deposit_repricing_cost = deposit_base * (yield_shock_bps / 10000) * deposit_beta * 0.15
liquidity_buffer_usage = starting_cet1 * 0.015 * severity * (0.5 + 0.5 * duration_years)
funding_liquidity_loss = wholesale_funding_cost + deposit_repricing_cost + liquidity_buffer_usage

# 4) Direct exposure / sanctions / corridor disruption channel
sanctions_loss = direct_exposure_base * sanctions_exposure * (0.03 * severity) * (1 + 0.30 * duration_years)
settlement_and_corridor_loss = direct_exposure_base * sanctions_exposure * 0.01 * (severity ** 1.15)
direct_exposure_loss = sanctions_loss + settlement_and_corridor_loss

# 5) Operational / cyber resilience channel
ops_loss = ops_cost_base * cyber_vulnerability * (0.45 * severity + 0.35 * duration_years)
fraud_and_recovery_loss = starting_cet1 * 0.0025 * severity * cyber_vulnerability
operational_cyber_loss = ops_loss + fraud_and_recovery_loss

# RWA inflation: denominator stress matters as much as numerator depletion
credit_rwa_inflation = base_rwa * 0.012 * severity * (1 + 0.30 * duration_years)
market_rwa_inflation = base_rwa * 0.006 * severity * (1 + trading_book / max(starting_cet1, 1) * 0.15)
ccr_cva_rwa_inflation = base_rwa * 0.004 * severity * (1 + sanctions_exposure)
fx_rwa_inflation = base_rwa * 0.002 * fx_stress_index
stressed_rwa = base_rwa + credit_rwa_inflation + market_rwa_inflation + ccr_cva_rwa_inflation + fx_rwa_inflation

# Aggregate capital depletion
loss_components = {
    "Market": market_loss,
    "Credit": credit_loss,
    "Liquidity / Funding": funding_liquidity_loss,
    "Direct Exposure / Sanctions": direct_exposure_loss,
    "Operational / Cyber": operational_cyber_loss,
}

total_depletion = sum(loss_components.values())
stressed_cet1 = starting_cet1 - total_depletion
stressed_cet1_ratio = (stressed_cet1 / stressed_rwa) * 100 if stressed_rwa > 0 else 0
required_cet1_ratio = 9.0
buffer_headroom = stressed_cet1_ratio - required_cet1_ratio
breach_probability = 99.5 if buffer_headroom <= 0 else clamp(100 - buffer_headroom * 18, 1, 95)


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
    c1.metric("Starting CET1 Ratio", f"{baseline_cet1_ratio:.1f}%")
    c2.metric("Stressed CET1 Ratio", f"{stressed_cet1_ratio:.1f}%", f"{stressed_cet1_ratio - baseline_cet1_ratio:.1f}%", delta_color="inverse")
    c3.metric("Capital Depletion", usd_billions(total_depletion))
    c4.metric("Buffer Breach Probability", f"{breach_probability:.1f}%", delta_color="inverse")

    c5, c6, c7 = st.columns(3)
    c5.metric("Starting RWA", usd_billions(base_rwa))
    c6.metric("Stressed RWA", usd_billions(stressed_rwa), usd_billions(stressed_rwa - base_rwa))
    c7.metric("Headroom vs 9.0%", f"{buffer_headroom:.1f}%")

    wf = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "relative", "relative", "total"],
            x=[
                "Starting CET1",
                "Market",
                "Credit",
                "Liquidity / Funding",
                "Direct Exposure / Sanctions",
                "Operational / Cyber",
                "Stressed CET1",
            ],
            y=[
                starting_cet1,
                -market_loss,
                -credit_loss,
                -funding_liquidity_loss,
                -direct_exposure_loss,
                -operational_cyber_loss,
                stressed_cet1,
            ],
            text=[
                usd_billions(starting_cet1),
                f"-{usd_billions(market_loss)}",
                f"-{usd_billions(credit_loss)}",
                f"-{usd_billions(funding_liquidity_loss)}",
                f"-{usd_billions(direct_exposure_loss)}",
                f"-{usd_billions(operational_cyber_loss)}",
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
        st.markdown(f"""
        **Bank archetype:** {bank_profile}

        **Market channel**
        - IRRBB loss = {usd_billions(banking_book_securities)} × {p['irrbb_duration']:.1f} × {irrbb_yield_decimal:.4f} = **{usd_billions(irrbb_loss)}**
        - Trading / FV loss = {usd_billions(trading_book)} × {p['trading_duration']:.1f} × mixed shock = **{usd_billions(trading_loss)}**

        **Credit channel**
        - Stressed PD = **{stressed_pd * 100:.2f}%**
        - Credit loss = {usd_billions(loan_book)} × {stressed_pd * 100:.2f}% × {lgd * 100:.0f}% = **{usd_billions(credit_loss)}**

        **Liquidity / funding channel**
        - Wholesale repricing = **{usd_billions(wholesale_funding_cost)}**
        - Deposit repricing = **{usd_billions(deposit_repricing_cost)}**
        - Buffer usage = **{usd_billions(liquidity_buffer_usage)}**

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
        """)


with tab2:
    st.subheader("MECE Channel Structure")

    channel_df = pd.DataFrame(
        {
            "Channel": list(loss_components.keys()),
            "Loss ($B)": list(loss_components.values()),
            "% of Total": [x / total_depletion * 100 if total_depletion > 0 else 0 for x in loss_components.values()],
            "Primary Driver": [
                "Rates + spreads",
                "Borrower default and migration",
                "Wholesale spread + deposit repricing",
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
        1. **Market** = valuation and fair-value effects from rates and spreads.
        2. **Credit** = borrower distress and migration.
        3. **Liquidity / Funding** = liability-side repricing and liquidity buffer use.
        4. **Direct Exposure / Sanctions** = blocked assets, settlement friction, corridor interruption.
        5. **Operational / Cyber** = disruption, fraud, third-party outages, recovery cost.

        This is more MECE than a generic “contagion” bucket because each channel now maps to a named mechanism that can be calibrated separately.
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
    st.latex(r"L_{market} = V_{banking} \times Dur_{IRRBB} \times \Delta Y + V_{trading} \times Dur_{trading} \times Mix(\Delta Y, \Delta CS)")
    st.latex(r"L_{credit} = LoanBook \times PD_{stressed} \times LGD")
    st.latex(r"L_{liq} = WholesaleFunding \times \Delta F + DepositBase \times DepositBeta \times \Delta Y + BufferUsage")
    st.latex(r"L_{direct} = SanctionsLoss + SettlementLoss")
    st.latex(r"L_{ops} = OpsDisruption + FraudRecovery")

    st.markdown("### Stage 3 — Stress both numerator and denominator")
    st.latex(r"CET1_{stressed} = CET1_{start} - \sum L_i")
    st.latex(r"RWA_{stressed} = RWA_{start} + \Delta RWA_{credit} + \Delta RWA_{market} + \Delta RWA_{CCR/CVA} + \Delta RWA_{FX}")
    st.latex(r"CET1Ratio_{stressed} = \frac{CET1_{stressed}}{RWA_{stressed}}")

    st.markdown(
        """
        **Why this is better than the original version**
        - Separates **IRRBB** from trading/fair-value loss.
        - Replaces a vague contagion plug with **named direct-exposure** losses.
        - Adds **operational / cyber** risk.
        - Adds **RWA inflation**, so the CET1 ratio can fall from both capital depletion and denominator expansion.
        - Keeps the model transparent enough for advisory discussion while being more aligned with bank stress-testing logic.
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
        - **Named channels:** each loss bucket maps to a clear mechanism.
        - **Archetype-based balance sheet:** better than pure linear scaling while still simple.
        - **Numerator + denominator stress:** both CET1 capital and RWA are stressed.
        - **User-visible simplifications:** calibration remains explicit and challengeable.

        #### Limitations
        - Coefficients remain illustrative rather than empirically fitted.
        - No asset-class-level LGD or sector-level PD curves.
        - No dynamic management actions such as hedging, capital raise, dividend cancellation, or asset sales.
        - No legal-entity, jurisdiction, accounting, or hedge-designation treatment.
        - No explicit LCR / NSFR or collateral waterfall.
        - No second-round macro feedback loops.

        #### How to support the assumptions in a client-ready methodology note
        1. Map each coefficient to a public source range or internal benchmark range.
        2. Back-test directionally against selected historical episodes.
        3. Replace archetypes with client-specific balance-sheet inputs.
        4. Add sector overlays for CRE, energy, trade finance, and sovereign exposures.
        5. Add management-action toggles and sensitivity ranges.
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

        > **"How much of the downside is direct regional exposure versus global market repricing?"**
        - Increase sanctions exposure while keeping oil sensitivity steady.

        > **"Would a retail-heavy bank or a markets-heavy bank be more resilient?"**
        - Switch archetypes and compare loss composition.

        > **"What happens if cyber escalation becomes the dominant second-order effect?"**
        - Raise cyber vulnerability to show how non-credit risks can dominate the tail.
        """
    )
