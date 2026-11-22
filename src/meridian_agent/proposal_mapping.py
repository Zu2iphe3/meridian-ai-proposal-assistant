"""Validate PM-reviewed values and translate them to the generator's supported fields."""

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Currency = Literal["ZAR", "USD", "GBP", "EUR"]
Risk = Literal[
    "Conservative", "Moderately Conservative", "Moderate", "Moderately Aggressive", "Aggressive"
]
Horizon = Literal["1 year+", "3 years+", "5 years+"]
AssetKey = Literal[
    "sa-equity", "intl-equity", "fixed-interest", "bonds", "property", "cash", "other"
]
Digits = Annotated[str, StringConstraints(pattern=r"^[0-9]+$", max_length=30)]
Percentage = Annotated[str, StringConstraints(pattern=r"^[0-9]+(?:\.[0-9]+)?$", max_length=20)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Money(Contract):
    amount: Digits
    currency: Currency
    approximate: bool = False


class Allocation(Contract):
    asset_class: Label = Field(alias="class")
    key: AssetKey
    percent: float = Field(ge=0, le=100, allow_inf_nan=False)


class ReviewedProposal(Contract):
    client_name: Label | None = None
    currency: Currency | None = None
    investment_amount: Money | None = None
    monthly_income: Money | None = None
    adviser_fee: Percentage | None = None
    horizon: Horizon | None = None
    risk: Risk | None = None
    needs: Annotated[str, StringConstraints(max_length=4000)] | None = None
    model_id: Label | None = None
    allocation: list[Allocation] | None = Field(default=None, min_length=1, max_length=7)

    @model_validator(mode="after")
    def validate_review(self) -> Self:
        for money in (self.investment_amount, self.monthly_income):
            if money and money.currency != self.currency:
                raise ValueError("Confirm a matching proposal currency for each monetary figure.")
        if self.investment_amount and not int(self.investment_amount.amount):
            raise ValueError("Investment capital must be positive.")
        if self.adviser_fee is not None and Decimal(self.adviser_fee) > 100:
            raise ValueError("Adviser fee must be between 0% and 100%.")
        if self.model_id and self.allocation:
            raise ValueError("Select a model or enter a bespoke allocation.")
        # The vendor hydrates these client-specific fields from a model before
        # applying overrides. Require reviewed replacements covering each preset.
        if self.model_id and not all((self.currency, self.horizon, self.risk)):
            raise ValueError("Confirm currency, horizon and risk before applying a model.")
        if self.allocation:
            keys = {row.key for row in self.allocation}
            total = sum(Decimal(str(row.percent)) for row in self.allocation)
            if len(keys) != len(self.allocation) or total != 100:
                raise ValueError("Allocation keys must be unique and weights must total 100%.")
        return self


class ApprovedProposal(Contract):
    approved: Literal[True]
    review: ReviewedProposal

    @field_validator("approved", mode="before")
    @classmethod
    def require_explicit_approval(cls, value: object) -> Literal[True]:
        if value is not True:
            raise ValueError("The current review requires explicit approval.")
        return True


class GoalAssessment(Contract):
    currency: Currency | None = None
    investmentHorizon: Horizon | None = None
    riskTolerance: Risk | None = None


class KeyFigures(Contract):
    totalInvestment: Digits | None = None
    incomeValue: Digits | None = None


class Strategy(Contract):
    currency: Currency | None = None
    keyFigures: KeyFigures | None = None
    allocation: list[Allocation] | None = None


class Objective(Contract):
    investmentHorizon: Horizon | None = None
    riskProfileCategory: Risk | None = None


class Fees(Contract):
    advisorFee: Percentage


class GeneratorProposal(Contract):
    clientName: Label | None = None
    needs: str | None = None
    goalAssessment: GoalAssessment | None = None
    objective: Objective | None = None
    strategy: Strategy | None = None
    fees: Fees | None = None
    applyModel: Label | None = None


class MappedProposal(Contract):
    proposal: GeneratorProposal
    generator_defaults: list[str]


def map_reviewed(review: ReviewedProposal) -> MappedProposal:
    capital, income = review.investment_amount, review.monthly_income
    notes = [review.needs.strip()] if review.needs and review.needs.strip() else []
    if capital and capital.approximate:
        notes.append("The investment amount is approximate.")
    if income and income.approximate:
        notes.append("The monthly income amount is approximate.")

    defaults = ["practice text and configured fees"]
    if review.model_id:
        defaults.extend(
            ["model allocation and composition", "model holdings", "model objective and fees"]
        )
    goal = GoalAssessment(
        currency=review.currency, investmentHorizon=review.horizon, riskTolerance=review.risk
    )
    # Both the goal summary and the strategy editor/PDF read these fields.
    strategy = Strategy(
        currency=review.currency,
        keyFigures=KeyFigures(
            totalInvestment=capital.amount if capital else None,
            incomeValue=income.amount if income else None,
        )
        if capital or income
        else None,
        allocation=review.allocation,
    )
    return MappedProposal(
        proposal=GeneratorProposal(
            clientName=review.client_name,
            needs="\n\n".join(notes) or None,
            goalAssessment=goal if review.currency or review.horizon or review.risk else None,
            objective=Objective(investmentHorizon=review.horizon, riskProfileCategory=review.risk)
            if review.horizon or review.risk
            else None,
            strategy=strategy
            if review.currency or capital or income or review.allocation
            else None,
            fees=Fees(advisorFee=review.adviser_fee) if review.adviser_fee is not None else None,
            applyModel=review.model_id,
        ),
        generator_defaults=defaults,
    )
