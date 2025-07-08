from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Asset:
    """Marketing asset file."""

    filename: str
    country: str
    language: str
    buyout_code: str
    concept: str
    audience: str
    transaction_side: str
    asset_format: str
    duration: str
    file_format: str
    file_id: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None

    # Asset metadata from Google Sheets
    production_date: Optional[datetime] = None
    year: Optional[int] = None
    month: Optional[int] = None

    # Asset performance data
    budget: int = 0
    ad_id: Optional[str] = None
    clicks: Optional[int] = None
    impressions: Optional[int] = None
    conversions: Optional[int] = None

    # Asset validation status
    is_valid_name: bool = False
    is_buyout_valid: bool = False
    quality_score: Optional[float] = None
    is_privacy_compliant: Optional[bool] = None

    # Budget
    previous_budget: Optional[int] = None
    budget_updated_at: Optional[datetime] = None
    budget_update_reason: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if the asset is valid based on all validation criteria.

        For testing purposes, we are using:
        - Valid filename is required
        - Either buyout is valid OR quality score > 5
        - Privacy compliance is required
        """
        return (
            self.is_valid_name
            and (self.is_buyout_valid or (self.quality_score is not None and self.quality_score > 5))
            and (self.is_privacy_compliant is not None and self.is_privacy_compliant)
        )

    @property
    def click_through_rate(self) -> Optional[float]:
        """Calculate click-through rate (CTR)."""
        if self.impressions and self.impressions > 0 and self.clicks is not None:
            return self.clicks / self.impressions
        return None

    @property
    def conversion_rate(self) -> Optional[float]:
        """Calculate conversion rate."""
        if self.clicks and self.clicks > 0 and self.conversions is not None:
            return self.conversions / self.clicks
        return None

    @property
    def performance_score(self) -> Optional[float]:
        """Calculate a performance score based on CTR and conversion rate.

        Returns:
            A score between 0 and 1, where higher is better,
            or None if metrics are missing.
        """
        ctr = self.click_through_rate or 0
        cvr = self.conversion_rate or 0

        # Simple weighted score, for testing purposes
        return (ctr * 0.4) + (cvr * 0.6)

    def update_budget(self, new_budget: int, reason: str) -> None:
        """Update the asset's budget and track the change.

        Args:
            new_budget: The new budget value
            reason: Reason for the budget update
        """
        self.previous_budget = self.budget
        self.budget = new_budget
        self.budget_updated_at = datetime.now()
        self.budget_update_reason = reason
