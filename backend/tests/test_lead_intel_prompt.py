from datetime import datetime, timezone
import pytest
from agents.lead_intel import build_lead_intel_description
from configs.verticals import build_execution_brief


def test_execution_brief_includes_runtime_date():
    brief = build_execution_brief(
        "Research Acme",
        "b2b_sales_lead_intel",
        {"company_url": "https://acme.example", "target_role": "CISO"},
    )
    assert datetime.now(timezone.utc).date().isoformat() in brief


def test_ciso_prompt_uses_runtime_year_role_and_product():
    description = build_lead_intel_description(
        "Complete execution brief",
        {
            "company_url": "https://acme.example",
            "target_role": "CISO",
            "our_product": "Automated cloud threat detection",
        },
        current_date="2026-07-21",
    )
    assert "2025 2026" in description
    assert "2024 2025" not in description
    assert "information security" in description
    assert "risk" in description
    assert "privacy" in description
    assert "Automated cloud threat detection" in description
    assert "Source Evidence Ledger" in description
    assert "not confidently identified" in description


@pytest.mark.parametrize(
    ("company_url", "target_role", "product"),
    [
        ("https://acme.example", "CISO", "Cloud threat detection"),
        ("https://globex.example", "VP Sales", "Revenue intelligence"),
        ("https://initech.example", "Head of Engineering", "Developer productivity analytics"),
    ],
)
def test_lead_intel_regression_fixtures_keep_company_buyer_and_product_executable(
    company_url, target_role, product,
):
    description = build_lead_intel_description(
        "Dated execution brief",
        {"company_url": company_url, "target_role": target_role, "our_product": product},
        current_date="2026-07-21",
    )
    assert company_url in description
    assert target_role in description
    assert product in description
    assert "2025 2026" in description
