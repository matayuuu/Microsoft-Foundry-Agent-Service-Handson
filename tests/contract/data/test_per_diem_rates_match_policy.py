"""Cross-check that travel_api.domain.rates (src/travel-api/**) exactly
mirrors the per-diem/lodging numbers published in the Japanese policy
Markdown (data/policies/03-hotels.md and 04-per-diem-meals.md).

The two workstreams intentionally do not share code at runtime (the API is
self-contained for clean containerization and does not read data/ at
runtime), so this regex-based comparison is the only thing preventing silent
numeric drift between the corpus and the API's deterministic fixtures.
"""

import re

TIER_TABLE_ROW = re.compile(
    r"^\|\s*(?P<tier>domestic_tier1|domestic_tier2|international_tier_a"
    r"|international_tier_b|international_tier_c)\s*\|[^|]*\|\s*"
    r"(?P<value1>[\d,]+)\s*円\s*\|(?:\s*(?P<value2>[\d,]+)\s*円\s*\|)?\s*$",
    re.MULTILINE,
)


def _parse_yen(value: str) -> int:
    return int(value.replace(",", ""))


def _parse_hotels_table(markdown_text: str) -> dict[str, int]:
    """Parses the single-column (lodging cap only) table in 03-hotels.md."""
    caps: dict[str, int] = {}
    for match in TIER_TABLE_ROW.finditer(markdown_text):
        caps[match.group("tier")] = _parse_yen(match.group("value1"))
    return caps


def _parse_per_diem_table(markdown_text: str) -> dict[str, dict[str, int]]:
    """Parses the two-column (meal allowance, lodging cap) table in
    04-per-diem-meals.md."""
    rates: dict[str, dict[str, int]] = {}
    for match in TIER_TABLE_ROW.finditer(markdown_text):
        rates[match.group("tier")] = {
            "meal_allowance": _parse_yen(match.group("value1")),
            "lodging_cap": _parse_yen(match.group("value2")),
        }
    return rates


def test_hotels_markdown_table_matches_rates_module(data_dir):
    from travel_api.domain.rates import PER_DIEM_TABLE

    hotels_text = (data_dir / "policies" / "03-hotels.md").read_text(encoding="utf-8")
    parsed = _parse_hotels_table(hotels_text)

    assert set(parsed) == set(PER_DIEM_TABLE)
    for tier, lodging_cap in parsed.items():
        assert lodging_cap == PER_DIEM_TABLE[tier]["lodging_cap"], (
            f"lodging_cap mismatch for {tier}: "
            f"markdown={lodging_cap} vs rates.py={PER_DIEM_TABLE[tier]['lodging_cap']}"
        )


def test_per_diem_markdown_table_matches_rates_module(data_dir):
    from travel_api.domain.rates import PER_DIEM_TABLE

    per_diem_text = (data_dir / "policies" / "04-per-diem-meals.md").read_text(encoding="utf-8")
    parsed = _parse_per_diem_table(per_diem_text)

    assert set(parsed) == set(PER_DIEM_TABLE)
    for tier, values in parsed.items():
        assert values == PER_DIEM_TABLE[tier], (
            f"per-diem mismatch for {tier}: markdown={values} vs rates.py={PER_DIEM_TABLE[tier]}"
        )


def test_day_trip_meal_allowance_matches_markdown(data_dir):
    from travel_api.domain.rates import DAY_TRIP_MEAL_ALLOWANCE

    per_diem_text = (data_dir / "policies" / "04-per-diem-meals.md").read_text(encoding="utf-8")
    domestic_match = re.search(r"国内日帰り:\s*([\d,]+)\s*円", per_diem_text)
    international_match = re.search(r"海外日帰り:\s*([\d,]+)\s*円", per_diem_text)

    assert domestic_match is not None, "could not find domestic day-trip allowance in markdown"
    assert international_match is not None, (
        "could not find international day-trip allowance in markdown"
    )
    assert _parse_yen(domestic_match.group(1)) == DAY_TRIP_MEAL_ALLOWANCE["domestic"]
    assert _parse_yen(international_match.group(1)) == DAY_TRIP_MEAL_ALLOWANCE["international"]


def test_hotels_and_per_diem_markdown_tables_agree_with_each_other(data_dir):
    """03-hotels.md explicitly claims to share lodging caps with
    04-per-diem-meals.md; verify that claim so the two markdown files
    themselves never drift, independent of the Python module."""
    hotels_text = (data_dir / "policies" / "03-hotels.md").read_text(encoding="utf-8")
    per_diem_text = (data_dir / "policies" / "04-per-diem-meals.md").read_text(encoding="utf-8")

    hotels_caps = _parse_hotels_table(hotels_text)
    per_diem_rates = _parse_per_diem_table(per_diem_text)

    assert set(hotels_caps) == set(per_diem_rates)
    for tier, cap in hotels_caps.items():
        assert cap == per_diem_rates[tier]["lodging_cap"], f"lodging cap mismatch for {tier}"


def test_known_cities_in_rates_module_match_a_declared_tier(data_dir):
    """Every city hardcoded in rates.py must resolve to one of the five
    tiers documented in the policy Markdown (no orphaned/undocumented tier
    names)."""
    from travel_api.domain.rates import _TIER_BY_CITY, PER_DIEM_TABLE

    hotels_text = (data_dir / "policies" / "03-hotels.md").read_text(encoding="utf-8")
    documented_tiers = set(_parse_hotels_table(hotels_text))

    assert set(PER_DIEM_TABLE) == documented_tiers
    assert set(_TIER_BY_CITY.values()) == documented_tiers
