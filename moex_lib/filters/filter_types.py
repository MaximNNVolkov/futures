from enum import Enum

class CouponType(Enum):
    FIXED = "fixed"
    FLOAT = "float"
    NONE = "none"

class BondType(Enum):
    OFZ = "ofz"
    CORPORATE = "corporate"
    MUNICIPAL = "municipal"
