from dataclasses import dataclass
from typing import Optional
from .filter_types import CouponType, BondType
from .maturity_delta import MaturityDelta

@dataclass
class BondSearchFilters:
    maturity_from: Optional[MaturityDelta] = None
    maturity_to: Optional[MaturityDelta] = None

    coupon_type: Optional[CouponType] = None
    bond_type: Optional[BondType] = None

    coupon_frequency: Optional[int] = None
    currency: Optional[str] = None

    has_amortization: Optional[bool] = None
    has_offer: Optional[bool] = None
