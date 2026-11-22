"""Validate the reviewed-proposal API and its generator payload."""

import json
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from meridian_agent.app import app
from meridian_agent.proposal_mapping import AssetKey, Horizon, Risk

client = TestClient(app)
ENDPOINT = "/api/proposals/map"


def test_sample_01_review_maps_to_vendor_fields():
    response = client.post(
        ENDPOINT,
        json={
            "approved": True,
            "review": {
                "client_name": "Mr George Whitfield",
                "currency": "ZAR",
                "investment_amount": {"amount": "6200000", "currency": "ZAR", "approximate": True},
                "monthly_income": {"amount": "28000", "currency": "ZAR", "approximate": True},
                "adviser_fee": "0.60",
                "risk": "Moderately Conservative",
                "horizon": "5 years+",
                "needs": "Supplement pension income.",
            },
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "proposal": {
            "clientName": "Mr George Whitfield",
            "needs": "Supplement pension income.\n\nThe investment amount is approximate."
            "\n\nThe monthly income amount is approximate.",
            "goalAssessment": {
                "currency": "ZAR",
                "investmentHorizon": "5 years+",
                "riskTolerance": "Moderately Conservative",
            },
            "strategy": {
                "currency": "ZAR",
                "keyFigures": {"totalInvestment": "6200000", "incomeValue": "28000"},
            },
            "objective": {
                "investmentHorizon": "5 years+",
                "riskProfileCategory": "Moderately Conservative",
            },
            "fees": {"advisorFee": "0.60"},
        },
        "generator_defaults": ["practice text and configured fees"],
    }


@pytest.mark.parametrize(
    "review",
    [
        {"currency": "EUR", "investment_amount": {"amount": "1,200", "currency": "EUR"}},
        {"currency": "EUR", "investment_amount": {"amount": 1200, "currency": "EUR"}},
        {"currency": "EUR", "investment_amount": {"amount": "0", "currency": "EUR"}},
        {"investment_amount": {"amount": "1200", "currency": "GBP"}},
        {"currency": "GBP", "monthly_income": {"amount": "400", "currency": "EUR"}},
        {"adviser_fee": "0.55%"},
        {"adviser_fee": "100.01"},
        {"risk": "Moderate to Aggressive"},
        {"horizon": "9 years"},
        {"goalAssessment": {"keyFigures": {"totalInvestment": "1200"}}},
        {"model_id": "balanced"},
        {
            "monthly_income": {"amount": "4200", "currency": "GBP", "frequency": "quarterly"},
            "currency": "GBP",
        },
        {"allocation": [{"class": "Cash", "key": "cash", "percent": 60}]},
        {
            "allocation": [
                {"class": "Cash", "key": "cash", "percent": 50},
                {"class": "Other cash", "key": "cash", "percent": 50},
            ]
        },
        {"allocation": [{"class": "Unknown", "key": "unknown", "percent": 100}]},
        {
            "model_id": "balanced",
            "currency": "ZAR",
            "risk": "Moderate",
            "horizon": "3 years+",
            "allocation": [{"class": "Cash", "key": "cash", "percent": 100}],
        },
    ],
)
def test_rejects_invalid_reviewed_values(review):
    response = client.post(ENDPOINT, json={"approved": True, "review": review})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "approval", [{}, {"approved": False}, {"approved": "true"}, {"approved": 1}]
)
def test_requires_explicit_approval(approval):
    assert client.post(ENDPOINT, json={**approval, "review": {}}).status_code == 422


def test_omissions_bespoke_allocation_and_zero_fee():
    empty = client.post(
        ENDPOINT, json={"approved": True, "review": {"client_name": "Fictional client"}}
    )
    assert empty.json()["proposal"] == {"clientName": "Fictional client"}
    review = {
        "adviser_fee": "0",
        "allocation": [
            {"class": "Cash", "key": "cash", "percent": 20},
            {"class": "Bonds", "key": "bonds", "percent": 80},
        ],
    }
    result = client.post(ENDPOINT, json={"approved": True, "review": review})
    assert result.status_code == 200
    assert result.json()["proposal"] == {
        "strategy": {"allocation": review["allocation"]},
        "fees": {"advisorFee": "0"},
    }


def test_review_enums_match_supplied_contract():
    path = Path(__file__).resolve().parents[1] / "challenge" / "schema.json"
    properties = json.loads(path.read_text(encoding="utf-8"))["properties"]
    objective = properties["objective"]["properties"]
    allocation = properties["strategy"]["properties"]["allocation"]["items"]["properties"]
    assert get_args(Horizon) == tuple(objective["investmentHorizon"]["enum"])
    assert get_args(Risk) == tuple(objective["riskProfileCategory"]["enum"])
    assert get_args(AssetKey) == tuple(allocation["key"]["enum"])
