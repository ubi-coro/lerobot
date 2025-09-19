"""
Shim control configs. Define minimal dataclasses to satisfy imports if real ones are gone.
"""
from dataclasses import dataclass

@dataclass
class TeleoperateControlConfig:
    hz: int = 30
    safety: bool = True

@dataclass
class RecordControlConfig:
    hz: int = 30
    buffer_size: int = 1000