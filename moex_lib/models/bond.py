from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class Bond:
    secid: str
    name: str
    maturity_date: Optional[date]
    coupon_type: str
    coupon_frequency: Optional[int]
    coupon_period: Optional[int]
    currency: str
    face_value: Optional[float]

    is_ofz: bool
    is_municipal: bool
    is_corporate: bool

    has_amortization: bool
    has_offer: bool

    current_price: Optional[float] = None
    next_coupon: Optional[float] = None
