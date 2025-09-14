from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ContactConfig:
    """Configuration for a contact."""
    name: str
    msisdn: str  # Phone number
    group: str
    role: str = ""
    dow: str = "ALL"  # Days of week
    window_start: str = "00:00"
    window_end: str = "23:59"
    enabled: bool = True

@dataclass
class ThresholdConfig:
    """Configuration for a threshold."""
    threshold_ref: str
    limit_value: float
    comparison_operator: str
    target: str  # day_total, shift_total, absolute_value
    severity: str  # critical, warn, medium, info
    message_template: str
    enabled: bool = True

@dataclass
class TagConfig:
    """Configuration for a tag."""
    tag_name: str
    description: str = ""
    group: str = ""
    unit: str = "L"
    comparison_operator: str = ">="
    comparison_target: str = "absolute_value"

@dataclass
class AppConfig:
    """Main application configuration."""
    # Twilio SMS Settings
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_from: str = ""
    
    # System Settings
    timezone: str = "Pacific/Auckland"
    test_mode: bool = True
    test_numbers: List[str] = None
    
    # Lists of configurations
    contacts: List[ContactConfig] = None
    thresholds: List[ThresholdConfig] = None
    tags: List[TagConfig] = None
    
    def __post_init__(self):
        if self.test_numbers is None:
            self.test_numbers = []
        if self.contacts is None:
            self.contacts = []
        if self.thresholds is None:
            self.thresholds = []
        if self.tags is None:
            self.tags = []