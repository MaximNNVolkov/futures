from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/candles.sqlite3")
    moex_base_url: str = "https://iss.moex.com/iss"


settings = Settings()

