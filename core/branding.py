"""
Chimeras v3.2 — White-Label Templating

Allows consulting firms to rebrand Chimeras deliverables with their own
logo, colors, company name, and legal footer. The --brand flag loads a
brand config JSON that overrides defaults across all exporters.

Usage:
    from core.branding import BrandConfig, apply_brand

    brand = BrandConfig.from_file("myfirm.json")
    # Pass brand to PDF/DOCX/portal exporters
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BrandConfig:
    """Branding configuration for white-label deliverables."""
    company_name: str = "Cyberian Defenses"
    tagline: str = "Guiding businesses to stronger cybersecurity."
    logo_path: Optional[str] = None
    primary_color: str = "#173054"
    secondary_color: str = "#1e3a5f"
    accent_color: str = "#225777"
    success_color: str = "#10b981"
    warning_color: str = "#f59e0b"
    critical_color: str = "#ef4444"
    font_sans: str = "Inter, sans-serif"
    font_mono: str = "JetBrains Mono, monospace"
    footer_text: str = "Cyberian Defenses"
    legal_notice: str = "CONFIDENTIAL — Authorized Security Assessment"
    email: str = ""
    website: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company_name": self.company_name,
            "tagline": self.tagline,
            "logo_path": self.logo_path,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "accent_color": self.accent_color,
            "success_color": self.success_color,
            "warning_color": self.warning_color,
            "critical_color": self.critical_color,
            "font_sans": self.font_sans,
            "font_mono": self.font_mono,
            "footer_text": self.footer_text,
            "legal_notice": self.legal_notice,
            "email": self.email,
            "website": self.website,
        }

    @classmethod
    def from_file(cls, path: Path) -> "BrandConfig":
        """Load brand config from JSON file."""
        data = json.loads(Path(path).read_text())
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrandConfig":
        """Create brand config from dict."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

    def to_json(self, path: Path) -> None:
        """Save brand config as JSON."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))


def apply_brand_to_pdf_css(brand: BrandConfig, base_css: str = "") -> str:
    """Inject brand colors into PDF CSS."""
    return base_css.replace("#173054", brand.primary_color) \
                   .replace("#1e3a5f", brand.secondary_color) \
                   .replace("#225777", brand.accent_color) \
                   .replace("#10b981", brand.success_color) \
                   .replace("#f59e0b", brand.warning_color) \
                   .replace("#ef4444", brand.critical_color)