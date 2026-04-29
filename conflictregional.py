import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Capital Impact Dashboard", layout="wide")


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def usd_billions(x: float) -> str:
    return f"${x:,.1f}B"


def pct_text(x: float) -> str:
    return f"{x:.1f}%"


def pp_text(x: float) -> str:
    return f"{x:+.1f}pp"


def ratio_points(amount: float, rwa: float) -> float:
    return 100.0 * amount / rwa if rwa > 0 else 0.0


def make_waterfall(labels, values, measures, text, title, yaxis_title):
    fig = go.Figure(
        go.Waterfall(
            x=labels,
            y=values,
            measure=measures,
            text=text,
            hovertext=text,
            hovertemplate="%{hovertext}<extra></extra>",
            textposition="outside",
            connector={"line": {"color": "rgba(160,160,160,0.45)", "width": 1}},
            increasing={"marker": {"color": "#22C55E"}},
            decreasing={"marker": {"color": "#D97706"}},
            totals={"marker": {"color": "#FDE047"}},
            cliponaxis=False,
        )
    )
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        title={"text": title, "x": 0.01, "xanchor": "left"},
        height=500,
        margin=dict(l=30, r=30, t=70, b=110),
        showlegend=False,
        yaxis=dict(title=yaxis_title, gridcolor="rgba(255,255,255,0.12)"),
        xaxis=dict(tickangle=-28, automargin=True),
    )
    return fig


PROFILE_MAP = {
    "Universal Bank": {
        "rwa_density": 0.33,
        "loan_share_assets": 0.56,
        "banking_book_securities_share_assets": 0.18,
        "trading_book_share_assets": 0.08,
        "direct_exposure_share_assets": 0.015,
        "wholesale_funding_share_assets": 0.22,
        "deposit_share_assets": 0.62,
        "loan_rwa_density_start": 0.33,
        "loan_rwa_density_stress": 0.37,
        "irrbb_duration": 3.8,
        "trading_duration": 2.0,
        "starting_loan_margin": 0.031,
        "structural_hedge_share_assets": 0.16,
        "non_interest_bearing_share_deposits": 0.28,
        "fee_to_rwa": 0.013,
        "traded_to_rwa": 0.010,
        "opex_to_rwa": 0.042,
        "misconduct_to_rwa": 0.003,
        "other_capital_to_rwa": 0.004,
        "distribution_to_rwa": 0.004,
    },
    "Wholesale / Markets Heavy": {
        "rwa_density": 0.37,
        "loan_share_assets": 0.42,
        "banking_book_securities_share_assets": 0.14,
        "trading_book_share_assets": 0.14,
        "direct_exposure_share_assets": 0.020,
        "wholesale_funding_share_assets": 0.30,
        "deposit_share_assets": 0.48,
        "loan_rwa_density_start": 0.38,
        "loan_rwa_density_stress": 0.42,
        "irrbb_duration": 3.2,
        "trading_duration": 2.4,
        "starting_loan_margin": 0.028,
        "structural_hedge_share_assets": 0.12,
        "non_interest_bearing_share_deposits": 0.22,
        "fee_to_rwa": 0.015,
        "traded_to_rwa": 0.016,
        "opex_to_rwa": 0.044,
        "misconduct_to_rwa": 0.003,
        "other_capital_to_rwa": 0.004,
        "distribution_to_rwa": 0.004,
    },
    "Retail / Deposit Heavy": {
        "rwa_density": 0.27,
        "loan_share_assets": 0.68,
        "banking_book_securities_share_assets": 0.18,
        "trading_book_share_assets": 0.03,
        "direct_exposure_share_assets": 0.008,
        "wholesale_funding_share_assets": 0.10,
        "deposit_share_assets": 0.78,
        "loan_rwa_density_start": 0.28,
        "loan_rwa_density_stress": 0.32,
        "irrbb_duration": 4.2,
        "trading_duration": 1.2,
        "starting_loan_margin": 0.030,
        "structural_hedge_share_assets": 0.22,
        "non_interest_bearing_share_deposits": 0.34,
        "fee_to_rwa": 0.010,
        "traded_to_rwa": 0.004,
        "opex_to_rwa": 0.038,
        "misconduct_to_rwa": 0.002,
        "other_capital_to_rwa": 0.003,
        "distribution_to_rwa": 0.003,
    },
    "EM / Cross-Border Heavy": {
        "rwa_density": 0.36,
        "loan_share_assets": 0.52,
        "banking_book_securities_share_assets": 0.15,
        "trading_book_share_assets": 0.06,
        "direct_exposure_share_assets": 0.025,
        "wholesale_funding_share_assets": 0.24,
        "deposit_share_assets": 0.56,
        "loan_rwa_density_start": 0.40,
        "loan_rwa_density_stress": 0.45,
        "irrbb_duration": 3.5,
        "trading_duration": 1.8,
        "starting_loan_margin": 0.033,
        "structural_hedge_share_assets": 0.12,
        "non_interest_bearing_share_deposits": 0.20,
        "fee_to_rwa": 0.012,
        "traded_to_rwa": 0.007,
        "opex_to_rwa": 0.043,
        "misconduct_to_rwa": 0.003,
        "other_capital_to_rwa": 0.004,
        "distribution_to_rwa": 0.004,
    },
}


CRISIS_MAP = {
    "Geopolitical conflict": {
        "rate_w": 0.75,
        "spread_w": 0.95,
        "market_vol_w": 0.85,
        "funding_w": 0.70,
        "supply_w": 0.55,
        "energy_w": 1.00,
        "fx_w": 1.00,
        "op_w": 0.80,
        "nii_beta": 0.95,
        "impairment_beta": 1.10,
        "traded_beta": 0.95,
        "rwa_beta": 1.05,
        "sma_beta": 0.90,
        "yield_shock_bps_anchor": 165,
        "mortgage_spread_start_bps": 60,
        "mortgage_spread_stress_bps": 82,
        "deposit_pass_through": 0.72,
        "nib_decline_5y_pp": 13,
    },
    "Supply chain / trade disruption": {
        "rate_w": 0.55,
        "spread_w": 0.80,
        "market_vol_w": 0.45,
        "funding_w": 0.55,
        "supply_w": 1.00,
        "energy_w": 0.65,
        "fx_w": 0.55,
        "op_w": 0.55,
        "nii_beta": 1.00,
        "impairment_beta": 1.00,
        "traded_beta": 0.75,
        "rwa_beta": 0.95,
        "sma_beta": 0.95,
        "yield_shock_bps_anchor": 140,
        "mortgage_spread_start_bps": 60,
        "mortgage_spread_stress_bps": 78,
        "deposit_pass_through": 0.68,
        "nib_decline_5y_pp": 12,
    },
    "Pandemic / public health crisis": {
        "rate_w": 0.35,
        "spread_w": 0.85,
        "market_vol_w": 0.55,
        "funding_w": 0.45,
        "supply_w": 0.75,
        "energy_w": 0.25,
        "fx_w": 0.25,
        "op_w": 0.70,
        "nii_beta": 0.85,
        "impairment_beta": 1.15,
        "traded_beta": 0.70,
        "rwa_beta": 0.90,
        "sma_beta": 1.00,
        "yield_shock_bps_anchor": 90,
        "mortgage_spread_start_bps": 60,
        "mortgage_spread_stress_bps": 72,
        "deposit_pass_through": 0.60,
        "nib_decline_5y_pp": 8,
    },
    "Financial market / liquidity shock": {
        "rate_w": 1.00,
        "spread_w": 1.15,
        "market_vol_w": 1.25,
        "funding_w": 1.10,
        "supply_w": 0.25,
        "energy_w": 0.10,
        "fx_w": 0.65,
        "op_w": 0.35,
        "nii_beta": 0.85,
        "impairment_beta": 0.85,
        "traded_beta": 1.25,
        "rwa_beta": 1.15,
        "sma_beta": 0.85,
        "yield_shock_bps_anchor": 230,
        "mortgage_spread_start_bps": 60,
        "mortgage_spread_stress_bps": 78,
        "deposit_pass_through": 0.78,
        "nib_decline_5y_pp": 12,
    },
}


REGION_MAP = {
    "Americas": {
        "rate_mult": 1.00,
        "spread_mult": 1.00,
        "market_mult": 1.05,
        "funding_mult": 1.00,
        "supply_mult": 0.95,
        "energy_mult": 0.90,
        "fx_mult": 0.95,
        "op_mult": 0.95,
        "impairment_mult": 0.95,
        "direct_exposure_mult": 0.90,
    },
    "Europe": {
        "rate_mult": 1.05,
        "spread_mult": 1.10,
        "market_mult": 1.05,
        "funding_mult": 1.10,
        "supply_mult": 1.05,
        "energy_mult": 1.20,
        "fx_mult": 1.05,
        "op_mult": 1.05,
        "impairment_mult": 1.10,
        "direct_exposure_mult": 1.15,
    },
    "APAC": {
        "rate_mult": 0.95,
        "spread_mult": 0.95,
        "market_mult": 1.00,
        "funding_mult": 1.00,
        "supply_mult": 1.15,
        "energy_mult": 0.85,
        "fx_mult": 0.95,
        "op_mult": 0.95,
        "impairment_mult": 0.85,
        "direct_exposure_mult": 0.75,
    },
    "Global / diversified": {
        "rate_mult": 1.00,
        "spread_mult": 1.00,
        "market_mult": 1.00,
        "funding_mult": 1.00,
        "supply_mult": 1.00,
        "energy_mult": 1.00,
        "fx_mult": 1.00,
        "op_mult": 1.00,
        "impairment_mult": 1.00,
        "direct_exposure_mult": 1.00,
    },
}


def build_profile(bank_profile: str, profile_overrides: dict | None):
    p = PROFILE_MAP[bank_profile].copy()
    if profile_overrides:
        p.update(profile_overrides)
    return p


def build_base_state(p: dict, starting_cet1: float, baseline_cet1_ratio: float, starting_leverage_ratio: float):
    base_rwa = starting_cet1 / (baseline_cet1_ratio / 100.0)
    leverage_exposure = starting_cet1 / (starting_leverage_ratio / 100.0)
    assets_from_rwa_density = base_rwa / p["rwa_density"]
    total_assets = max(leverage_exposure, assets_from_rwa_density)
    return {
        "base_rwa": base_rwa,
        "leverage_exposure": leverage_exposure,
        "total_assets": total_assets,
        "loan_book": total_assets * p["loan_share_assets"],
        "banking_book_securities": total_assets * p["banking_book_securities_share_assets"],
        "trading_book": total_assets * p["trading_book_share_assets"],
        "deposits": total_assets * p["deposit_share_assets"],
        "wholesale_funding": total_assets * p["wholesale_funding_share_assets"],
        "direct_exposure": total_assets * p["direct_exposure_share_assets"],
        "structural_hedge_assets": total_assets * p["structural_hedge_share_assets"],
    }


def build_shocks(c: dict, region: dict, severity: int, duration_years: float, stress_multiplier: float):
    severity_multiplier = 0.60 + 0.08 * severity
    duration_years_capped = min(duration_years, 3.0)
    stock_horizon_factor = clamp(0.70 + 0.28 * math.sqrt(max(duration_years, 1 / 12)), 0.75, 1.20)
    flow_horizon_factor = 1.0 + 0.10 * max(duration_years - 1.0, 0.0)

    rate_w = c["rate_w"] * region["rate_mult"]
    spread_w = c["spread_w"] * region["spread_mult"]
    market_w = c["market_vol_w"] * region["market_mult"]
    funding_w = c["funding_w"] * region["funding_mult"]
    supply_w = c["supply_w"] * region["supply_mult"]
    energy_w = c["energy_w"] * region["energy_mult"]
    fx_w = c["fx_w"] * region["fx_mult"]
    op_w = c["op_w"] * region["op_mult"]

    yield_shock_bps = (
        c["yield_shock_bps_anchor"]
        * (0.55 + 0.45 * severity_multiplier * rate_w)
        * (1.0 + 0.12 * max(duration_years_capped - 1.0, 0.0))
        * stock_horizon_factor
        * stress_multiplier
    )
    spread_shock_bps = (
        95
        * spread_w
        * (0.55 + 0.45 * severity_multiplier)
        * (1.0 + 0.14 * max(duration_years_capped - 1.0, 0.0) * (0.7 + 0.3 * funding_w))
        * stock_horizon_factor
        * stress_multiplier
    )
    wholesale_funding_spread_bps = (
        70
        * funding_w
        * (0.55 + 0.45 * severity_multiplier)
        * (1.0 + 0.15 * max(duration_years_capped - 1.0, 0.0))
        * stock_horizon_factor
        * stress_multiplier
    )
    deposit_pass_through = clamp(
        c["deposit_pass_through"]
        * (0.94 + 0.06 * severity_multiplier)
        * (1.0 + 0.05 * max(duration_years_capped - 1.0, 0.0)),
        0.45,
        0.92,
    )
    nib_decline_pp = c["nib_decline_5y_pp"] * (duration_years_capped / 5.0) * (0.90 + 0.10 * severity_multiplier)
    fx_fragmentation_index = 1.0 + 0.10 * fx_w * severity_multiplier + 0.06 * max(duration_years_capped - 1.0, 0.0) * fx_w
    macro_multiplier = 1.0 + 0.04 * severity_multiplier * supply_w + 0.06 * max(duration_years_capped - 1.0, 0.0) * (0.6 + 0.4 * funding_w)

    return {
        "severity_multiplier": severity_multiplier,
        "duration_years_capped": duration_years_capped,
        "stock_horizon_factor": stock_horizon_factor,
        "flow_horizon_factor": flow_horizon_factor,
        "yield_shock_bps": yield_shock_bps,
        "spread_shock_bps": spread_shock_bps,
        "wholesale_funding_spread_bps": wholesale_funding_spread_bps,
        "deposit_pass_through": deposit_pass_through,
        "nib_decline_pp": nib_decline_pp,
        "fx_fragmentation_index": fx_fragmentation_index,
        "macro_multiplier": macro_multiplier,
        "rate_w": rate_w,
        "spread_w": spread_w,
        "market_w": market_w,
        "funding_w": funding_w,
        "supply_w": supply_w,
        "energy_w": energy_w,
        "fx_w": fx_w,
        "op_w": op_w,
    }


def linear_progress(t_share: float) -> float:
    """Straight-line cumulative recognition: no artificial acceleration or delay."""
    return clamp(t_share, 0.0, 1.0)


def compute_outcome(mode, crisis_type, region_name, bank_profile, starting_cet1, baseline_cet1_ratio, starting_leverage_ratio,
                    severity, duration_months, include_sma, sma_strength, include_distributions,
                    stress_multiplier, profile_overrides=None):
    p = build_profile(bank_profile, profile_overrides)
    c = CRISIS_MAP[crisis_type]
    region = REGION_MAP[region_name]
    duration_years = duration_months / 12.0
    modelling_horizon_years = duration_years
    reporting_horizon_months = max(6, duration_months)

    s = build_base_state(p, starting_cet1, baseline_cet1_ratio, starting_leverage_ratio)
    sh = build_shocks(c, region, severity, modelling_horizon_years, stress_multiplier)

    spread_uplift_bps = (c["mortgage_spread_stress_bps"] - c["mortgage_spread_start_bps"]) * min(modelling_horizon_years, 1.5)
    nib_start = p["non_interest_bearing_share_deposits"]
    nib_end = max(0.03, nib_start - sh["nib_decline_pp"] / 100.0)
    avg_nib = 0.5 * (nib_start + nib_end)

    # Challenge #2 fix: revenue is now stressed as an outcome, not treated as
    # an automatic positive offset. The formulas below retain actual calculated
    # KPI values and avoid timing overlays.
    deposit_beta_cost = (sh["yield_shock_bps"] / 10000.0) * sh["deposit_pass_through"] * (1.0 - avg_nib)
    structural_hedge_benefit = (sh["yield_shock_bps"] / 10000.0) * (s["structural_hedge_assets"] / max(s["loan_book"], 1e-9)) * 0.60
    asset_repricing_benefit = (spread_uplift_bps / 10000.0) * 0.35
    funding_drag_margin = (sh["wholesale_funding_spread_bps"] / 10000.0) * (s["wholesale_funding"] / max(s["loan_book"], 1e-9)) * 0.75
    credit_margin_leakage = (sh["spread_shock_bps"] / 10000.0) * (0.20 + 0.10 * sh["macro_multiplier"]) * sh["spread_w"]
    deposit_mix_drag = max(0.0, nib_start - nib_end) * (sh["yield_shock_bps"] / 10000.0) * 0.70

    stressed_loan_margin = clamp(
        p["starting_loan_margin"]
        + asset_repricing_benefit
        + structural_hedge_benefit
        - deposit_beta_cost
        - funding_drag_margin
        - credit_margin_leakage
        - deposit_mix_drag,
        -0.005,
        0.055,
    )
    avg_loan_margin = 0.5 * (p["starting_loan_margin"] + stressed_loan_margin)
    loan_volume_factor = clamp(
        1.0
        - 0.015 * sh["supply_w"] * sh["macro_multiplier"]
        - 0.015 * sh["funding_w"] * (sh["wholesale_funding_spread_bps"] / 100.0) / 100.0
        - 0.020 * max(modelling_horizon_years - 1.0, 0.0),
        0.82,
        1.00,
    )
    avg_loan_book = s["loan_book"] * 0.5 * (1.0 + loan_volume_factor)
    net_interest_income = avg_loan_book * avg_loan_margin * modelling_horizon_years * c["nii_beta"] * sh["flow_horizon_factor"]

    fee_decay = clamp(
        1.0
        - 0.12 * sh["supply_w"] * (sh["macro_multiplier"] - 1.0)
        - 0.10 * sh["market_w"] * (sh["spread_shock_bps"] / 100.0) / 100.0
        - 0.08 * sh["funding_w"] * (sh["wholesale_funding_spread_bps"] / 100.0) / 100.0
        - 0.06 * max(modelling_horizon_years - 1.0, 0.0),
        0.35,
        1.00,
    )
    traded_income_factor = clamp(
        0.55
        + 0.18 * sh["market_w"]
        - 0.22 * sh["market_w"] * (sh["spread_shock_bps"] / 100.0) / 100.0
        - 0.16 * sh["funding_w"] * (sh["wholesale_funding_spread_bps"] / 100.0) / 100.0
        - 0.10 * max(modelling_horizon_years - 1.0, 0.0),
        -0.25,
        0.95,
    )
    opex_factor = 1.0 + 0.05 * max(modelling_horizon_years - 1.0, 0.0)

    net_fees = s["base_rwa"] * p["fee_to_rwa"] * modelling_horizon_years * fee_decay
    net_traded_income = s["base_rwa"] * p["traded_to_rwa"] * modelling_horizon_years * traded_income_factor
    operating_expenses = s["base_rwa"] * p["opex_to_rwa"] * modelling_horizon_years * opex_factor

    loan_rwa_density_delta = max(0.0, p["loan_rwa_density_stress"] - p["loan_rwa_density_start"])
    effective_impairment_beta = c["impairment_beta"] * region["impairment_mult"]
    stressed_annual_pd = clamp(
        0.012
        * (1.00 + 0.55 * (sh["spread_shock_bps"] / 100.0) / 100.0 * effective_impairment_beta)
        * (1.00 + 0.35 * (sh["wholesale_funding_spread_bps"] / 100.0) / 100.0 * sh["funding_w"])
        * (1.0 + 0.18 * max(modelling_horizon_years - 1.0, 0.0))
        * sh["macro_multiplier"],
        0.008,
        0.090,
    )
    stressed_lgd = clamp(
        0.38
        * (1.0 + 0.04 * (sh["spread_shock_bps"] / 100.0) / 100.0 + 0.04 * max(modelling_horizon_years - 1.0, 0.0)),

        0.35,
        0.60,
    )
    cumulative_default_rate = 1.0 - math.exp(-stressed_annual_pd * modelling_horizon_years)
    impairments = s["loan_book"] * cumulative_default_rate * stressed_lgd * stress_multiplier

    irrbb_loss = s["banking_book_securities"] * p["irrbb_duration"] * (sh["yield_shock_bps"] / 10000.0) * 0.22
    trading_loss = s["trading_book"] * p["trading_duration"] * (0.45 * (sh["yield_shock_bps"] / 10000.0) + 0.55 * (sh["spread_shock_bps"] / 10000.0)) * sh["market_w"]
    valuation_adjustments = s["trading_book"] * 0.012 * sh["severity_multiplier"] * sh["market_w"]
    traded_risk_losses = ((irrbb_loss + trading_loss + valuation_adjustments) * c["traded_beta"] * sh["stock_horizon_factor"] * (0.85 + 0.15 * sh["duration_years_capped"]) * stress_multiplier)

    misconduct = s["base_rwa"] * p["misconduct_to_rwa"] * modelling_horizon_years * (0.85 + 0.10 * sh["severity_multiplier"])
    operational_risk = (
        s["base_rwa"] * 0.0010 * sh["op_w"] * sh["severity_multiplier"] * modelling_horizon_years
        + s["total_assets"] * 0.00035 * sh["op_w"] * (0.40 + 0.08 * sh["severity_multiplier"]) * min(modelling_horizon_years, 2.0)
    )

    direct_crisis_loss = s["direct_exposure"] * region["direct_exposure_mult"] * (0.010 * sh["severity_multiplier"] + 0.007 * min(modelling_horizon_years, 2.0)) * max(sh["energy_w"], sh["fx_w"])
    tax_and_other_pl_and_capital = -(s["base_rwa"] * p["other_capital_to_rwa"] * modelling_horizon_years + direct_crisis_loss)
    distributions = -(s["base_rwa"] * p["distribution_to_rwa"] * modelling_horizon_years) if include_distributions else 0.0

    selected_rwa_pre_sma = s["base_rwa"] + (
        s["loan_book"] * loan_rwa_density_delta * c["rwa_beta"] * (0.75 + 0.15 * min(modelling_horizon_years, 3.0))
        + s["trading_book"] * 0.18 * sh["market_w"] * sh["severity_multiplier"] * 0.12 * min(modelling_horizon_years, 2.0) * sh["stock_horizon_factor"]
        + s["base_rwa"] * 0.004 * (sh["fx_fragmentation_index"] - 1.0) * min(modelling_horizon_years, 2.0)
    )
    selected_capital_pre_sma = (
        starting_cet1 + net_interest_income + net_fees + net_traded_income - operating_expenses - impairments - traded_risk_losses - misconduct - operational_risk + tax_and_other_pl_and_capital + distributions
    )
    pre_sma_ratio = 100.0 * selected_capital_pre_sma / selected_rwa_pre_sma
    raw_sma_pp = max(0.0, baseline_cet1_ratio - pre_sma_ratio) * sma_strength * c["sma_beta"] if include_sma else 0.0
    sma_pp = min(raw_sma_pp, 0.9)

    path_rows = []
    for m in range(reporting_horizon_months + 1):
        t_years = m / 12.0
        t_share = 0.0 if modelling_horizon_years <= 0 else min(t_years / modelling_horizon_years, 1.0)

        # KPI recognition is intentionally kept neutral and pro-rata.
        # No artificial acceleration, delay, smoothing curve, or timing overlay is applied.
        # Each cumulative KPI uses the same horizon share so the displayed trajectory
        # follows the model's actual calculated values consistently across the code.
        progress = linear_progress(t_share)
        income_prog = progress
        fee_prog = progress
        traded_income_prog = progress
        expense_prog = progress
        impairment_prog = progress
        traded_loss_prog = progress
        misconduct_prog = progress
        op_risk_prog = progress
        tax_other_prog = progress
        distribution_prog = progress
        rwa_progress = progress

        capital_t = (
            starting_cet1
            + net_interest_income * income_prog
            + net_fees * fee_prog
            + net_traded_income * traded_income_prog
            - operating_expenses * expense_prog
            - impairments * impairment_prog
            - traded_risk_losses * traded_loss_prog
            - misconduct * misconduct_prog
            - operational_risk * op_risk_prog
            + tax_and_other_pl_and_capital * tax_other_prog
            + distributions * distribution_prog
        )
        rwa_t = s["base_rwa"] + (selected_rwa_pre_sma - s["base_rwa"]) * rwa_progress
        ratio_t = 100.0 * capital_t / rwa_t if rwa_t > 0 else 0.0
        path_rows.append({"Month": m, "CET1 capital ($B)": capital_t, "RWA ($B)": rwa_t, "CET1 ratio (%)": ratio_t})

    trajectory_df = pd.DataFrame(path_rows)
    low_idx_pre_sma = trajectory_df["CET1 ratio (%)"].idxmin()
    low_month_pre_sma = int(trajectory_df.loc[low_idx_pre_sma, "Month"])

    if include_sma and sma_pp > 0:
        sma_capital_add = s["base_rwa"] * (sma_pp / 100.0) * 0.75
        sma_rwa_relief = s["base_rwa"] * (sma_pp / 100.0) * 0.25
        for i in range(len(trajectory_df)):
            if int(trajectory_df.loc[i, "Month"]) >= low_month_pre_sma:
                trajectory_df.loc[i, "CET1 capital ($B)"] += sma_capital_add
                trajectory_df.loc[i, "RWA ($B)"] = max(s["base_rwa"] * 0.88, trajectory_df.loc[i, "RWA ($B)"] - sma_rwa_relief)
                trajectory_df.loc[i, "CET1 ratio (%)"] = 100.0 * trajectory_df.loc[i, "CET1 capital ($B)"] / trajectory_df.loc[i, "RWA ($B)"]

    low_idx = trajectory_df["CET1 ratio (%)"].idxmin()
    low_month = int(trajectory_df.loc[low_idx, "Month"])
    low_ratio = float(trajectory_df.loc[low_idx, "CET1 ratio (%)"])
    low_capital = float(trajectory_df.loc[low_idx, "CET1 capital ($B)"])
    end_ratio = float(trajectory_df.iloc[-1]["CET1 ratio (%)"])
    end_capital = float(trajectory_df.iloc[-1]["CET1 capital ($B)"])

    if mode == "Low-point benchmark mode":
        selected_ratio = low_ratio
        selected_capital = low_capital
        selected_label = "Low-point CET1"
    else:
        selected_ratio = end_ratio
        selected_capital = end_capital
        selected_label = "End-of-conflict CET1"

    selected_drawdown = selected_ratio - baseline_cet1_ratio

    nii_pp = ratio_points(net_interest_income, s["base_rwa"])
    fees_pp = ratio_points(net_fees, s["base_rwa"])
    traded_income_pp = ratio_points(net_traded_income, s["base_rwa"])
    opex_pp = -ratio_points(operating_expenses, s["base_rwa"])
    impairments_pp = -ratio_points(impairments, s["base_rwa"])
    traded_risk_pp = -ratio_points(traded_risk_losses, s["base_rwa"])
    misconduct_pp = -ratio_points(misconduct, s["base_rwa"])
    operational_risk_pp = -ratio_points(operational_risk, s["base_rwa"])
    tax_other_pp = ratio_points(tax_and_other_pl_and_capital, s["base_rwa"])
    distributions_pp = ratio_points(distributions, s["base_rwa"])

    ratio_other = selected_ratio - (
        baseline_cet1_ratio + nii_pp + fees_pp + traded_income_pp + opex_pp + impairments_pp + traded_risk_pp + misconduct_pp + operational_risk_pp + tax_other_pp + distributions_pp
    )
    capital_other = selected_capital - (
        starting_cet1 + net_interest_income + net_fees + net_traded_income - operating_expenses - impairments - traded_risk_losses - misconduct - operational_risk + tax_and_other_pl_and_capital + distributions
    )

    return {
        "yield_shock_bps": sh["yield_shock_bps"],
        "spread_shock_bps": sh["spread_shock_bps"],
        "wholesale_funding_spread_bps": sh["wholesale_funding_spread_bps"],
        "deposit_pass_through": sh["deposit_pass_through"],
        "selected_ratio": selected_ratio,
        "selected_capital": selected_capital,
        "selected_drawdown": selected_drawdown,
        "selected_label": selected_label,
        "stress_low_point_ratio": low_ratio,
        "stress_end_ratio": end_ratio,
        "trajectory_df": trajectory_df,
        "trajectory_low_point_month": low_month,
        "ratio_driver_values": [nii_pp, fees_pp, traded_income_pp, opex_pp, impairments_pp, traded_risk_pp, misconduct_pp, operational_risk_pp, tax_other_pp, distributions_pp, ratio_other],
        "capital_driver_values": [net_interest_income, net_fees, net_traded_income, -operating_expenses, -impairments, -traded_risk_losses, -misconduct, -operational_risk, tax_and_other_pl_and_capital, distributions, capital_other],
        "stressed_loan_margin": stressed_loan_margin,
        "loan_volume_factor": loan_volume_factor,
        "fee_decay": fee_decay,
        "traded_income_factor": traded_income_factor,
    }


st.title("Capital Impact Dashboard — Regionalized")
st.caption("Crisis type, bank archetype, and regional orientation are all reflected in the transmission layer. Both ratio and absolute CET1 waterfalls use the same simplified structure.")

with st.sidebar:
    st.header("Mode")
    mode = st.radio("Analysis mode", ["Low-point benchmark mode", "Through-conflict cumulative mode"], index=1)

    st.header("Scenario")
    crisis_type = st.selectbox("Crisis type", list(CRISIS_MAP.keys()), index=0)
    region_name = st.selectbox("Regional orientation", list(REGION_MAP.keys()), index=3)
    bank_profile = st.selectbox("Bank archetype", list(PROFILE_MAP.keys()), index=0)
    starting_cet1 = st.slider("Starting CET1 capital ($B)", 20, 400, 250, 10)
    baseline_cet1_ratio = st.slider("Starting CET1 ratio (%)", 10.0, 18.0, 14.5, 0.1)
    starting_leverage_ratio = st.slider("Starting leverage ratio (%)", 3.5, 7.0, 5.3, 0.1)
    severity = st.slider("Stress severity (1-10)", 1, 10, 7, 1)
    duration_months = st.slider("Stress duration (months)", 6, 36, 12, 1)
    stress_multiplier = st.slider("Scenario multiplier", 0.7, 1.4, 1.0, 0.05)

    st.header("Model assumptions")
    enable_profile_overrides = st.checkbox("Enable user overrides", value=False)
    base_profile = PROFILE_MAP[bank_profile]
    profile_overrides = None
    if enable_profile_overrides:
        profile_overrides = {}
        profile_overrides["rwa_density"] = st.slider("RWA density", 0.15, 0.60, float(base_profile["rwa_density"]), 0.01)
        profile_overrides["loan_share_assets"] = st.slider("Loan share of assets", 0.20, 0.85, float(base_profile["loan_share_assets"]), 0.01)
        profile_overrides["trading_book_share_assets"] = st.slider("Trading-book share of assets", 0.00, 0.25, float(base_profile["trading_book_share_assets"]), 0.01)
        profile_overrides["wholesale_funding_share_assets"] = st.slider("Wholesale funding share of assets", 0.00, 0.50, float(base_profile["wholesale_funding_share_assets"]), 0.01)
        profile_overrides["deposit_share_assets"] = st.slider("Deposit share of assets", 0.20, 0.90, float(base_profile["deposit_share_assets"]), 0.01)
        profile_overrides["loan_rwa_density_start"] = st.slider("Starting loan RWA density", 0.10, 0.70, float(base_profile["loan_rwa_density_start"]), 0.01)
        profile_overrides["loan_rwa_density_stress"] = st.slider("Stressed loan RWA density", 0.10, 0.80, float(base_profile["loan_rwa_density_stress"]), 0.01)
        profile_overrides["starting_loan_margin"] = st.slider("Starting loan margin", 0.010, 0.060, float(base_profile["starting_loan_margin"]), 0.001)
        profile_overrides["fee_to_rwa"] = st.slider("Annual net fees / RWA", 0.000, 0.040, float(base_profile["fee_to_rwa"]), 0.001)
        profile_overrides["traded_to_rwa"] = st.slider("Annual net traded income / RWA", 0.000, 0.040, float(base_profile["traded_to_rwa"]), 0.001)
        profile_overrides["opex_to_rwa"] = st.slider("Annual operating expenses / RWA", 0.005, 0.080, float(base_profile["opex_to_rwa"]), 0.001)

    st.header("Management actions")
    include_sma = st.checkbox("Include SMAs", value=True)
    sma_strength = st.slider("SMA effectiveness (% of pre-SMA drawdown)", 0, 40, 19, 1) / 100.0
    include_distributions = st.checkbox("Include distributions", value=True)

r = compute_outcome(
    mode=mode,
    crisis_type=crisis_type,
    region_name=region_name,
    bank_profile=bank_profile,
    starting_cet1=starting_cet1,
    baseline_cet1_ratio=baseline_cet1_ratio,
    starting_leverage_ratio=starting_leverage_ratio,
    severity=severity,
    duration_months=duration_months,
    include_sma=include_sma,
    sma_strength=sma_strength,
    include_distributions=include_distributions,
    stress_multiplier=stress_multiplier,
    profile_overrides=profile_overrides,
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Starting CET1 ratio", pct_text(baseline_cet1_ratio))
c2.metric(r["selected_label"], pct_text(r["selected_ratio"]), pp_text(r["selected_drawdown"]), delta_color="inverse")
c3.metric("Stress low-point", pct_text(r["stress_low_point_ratio"]), f"Month {r['trajectory_low_point_month']}")
c4.metric("End-of-horizon CET1", pct_text(r["stress_end_ratio"]))

c5, c6, c7, c8 = st.columns(4)
c5.metric("Yield shock", f"{r['yield_shock_bps']:.0f} bps")
c6.metric("Spread shock", f"{r['spread_shock_bps']:.0f} bps")
c7.metric("Funding spread", f"{r['wholesale_funding_spread_bps']:.0f} bps")
c8.metric("Deposit pass-through", f"{r['deposit_pass_through']*100:.0f}%")

c9, c10, c11, c12 = st.columns(4)
c9.metric("Stressed loan margin", pct_text(r["stressed_loan_margin"] * 100.0))
c10.metric("Loan volume factor", pct_text(r["loan_volume_factor"] * 100.0))
c11.metric("Fee income factor", pct_text(r["fee_decay"] * 100.0))
c12.metric("Trading income factor", pct_text(r["traded_income_factor"] * 100.0))

ratio_labels = ["Start point", "NII", "Net fees", "Net traded income", "Operating expenses", "Impairments", "Traded risk losses", "Misconduct", "Operational risk", "Tax & other capital", "Distributions", "Other denominator / SMA", r["selected_label"]]
ratio_values = [baseline_cet1_ratio] + r["ratio_driver_values"] + [r["selected_ratio"]]
ratio_measures = ["absolute"] + ["relative"] * len(r["ratio_driver_values"]) + ["total"]
ratio_text = [pct_text(baseline_cet1_ratio)] + [pp_text(v) for v in r["ratio_driver_values"]] + [pct_text(r["selected_ratio"])]

capital_labels = ["Starting CET1", "NII", "Net fees", "Net traded income", "Operating expenses", "Impairments", "Traded risk losses", "Misconduct", "Operational risk", "Tax & other capital", "Distributions", "Other denominator / SMA", r["selected_label"]]
capital_values = [starting_cet1] + r["capital_driver_values"] + [r["selected_capital"]]
capital_measures = ["absolute"] + ["relative"] * len(r["capital_driver_values"]) + ["total"]
capital_text = [usd_billions(starting_cet1)] + [usd_billions(v) for v in r["capital_driver_values"]] + [usd_billions(r["selected_capital"])]

tab_w, tab_s = st.tabs(["Waterfall view", "Scenario analysis"])
with tab_w:
    st.plotly_chart(make_waterfall(ratio_labels, ratio_values, ratio_measures, ratio_text, "CET1 Ratio Bridge", "CET1 ratio / percentage-point contribution"), use_container_width=True)
    st.plotly_chart(make_waterfall(capital_labels, capital_values, capital_measures, capital_text, "Absolute CET1 Bridge", "CET1 capital ($B)"), use_container_width=True)

with tab_s:
    traj = r["trajectory_df"]
    fig_ratio = go.Figure()
    fig_ratio.add_trace(go.Scatter(x=traj["Month"], y=traj["CET1 ratio (%)"], mode="lines+markers", hovertemplate="%{y:.2f}%<extra></extra>"))
    fig_ratio.add_hline(y=baseline_cet1_ratio, line_dash="dot", annotation_text="Starting ratio")
    fig_ratio.add_vline(x=r["trajectory_low_point_month"], line_dash="dash", annotation_text="Low point")
    fig_ratio.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", title={"text": "CET1 Ratio Through Horizon", "x": 0.01}, height=430, xaxis_title="Month", yaxis_title="CET1 ratio (%)", showlegend=False)
    st.plotly_chart(fig_ratio, use_container_width=True)

    fig_cap = go.Figure()
    fig_cap.add_trace(go.Scatter(x=traj["Month"], y=traj["CET1 capital ($B)"], mode="lines+markers", hovertemplate="$%{y:.1f}B<extra></extra>"))
    fig_cap.add_vline(x=r["trajectory_low_point_month"], line_dash="dash", annotation_text="Low point")
    fig_cap.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", title={"text": "Absolute CET1 Through Horizon", "x": 0.01}, height=430, xaxis_title="Month", yaxis_title="CET1 capital ($B)", showlegend=False)
    st.plotly_chart(fig_cap, use_container_width=True)

    st.dataframe(traj.style.format({"CET1 capital ($B)": "{:.1f}", "RWA ($B)": "{:.1f}", "CET1 ratio (%)": "{:.2f}"}), use_container_width=True)

with st.expander("Revenue and timing basis"):
    st.markdown(
        """
        - Revenue is now stressed in the calculation itself rather than treated as an automatic positive offset.
        - NII reflects stressed deposit pass-through, wholesale funding drag, limited asset repricing, credit-spread leakage, deposit-mix pressure and loan-volume contraction.
        - Fee income is reduced under higher severity, supply disruption, market stress and funding stress.
        - Trading income can fall materially or become negative under severe market/funding stress instead of always offsetting traded losses.
        - KPI recognition through time remains neutral and pro-rata; there is no artificial income delay or loss front-loading overlay.
        """
    )
