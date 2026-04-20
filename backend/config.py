"""Configuration: API keys, indicator registry, year ranges."""
import os
from typing import Any, Dict

# API keys — loaded from environment variables (no fallbacks)
CENSUS_API_KEY = os.getenv("CENSUS_API_KEY", "")
BLS_API_KEY = os.getenv("BLS_API_KEY", "")
BEA_API_KEY = os.getenv("BEA_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# Available year ranges per source
CENSUS_YEARS = [y for y in range(2010, 2025) if y != 2020]  # no ACS 1-year in 2020
CENSUS_5YR_YEARS = list(range(2010, 2025))  # ACS 5-year: 2010-2024 (latest available)
BLS_YEARS = list(range(2010, 2027))  # BLS has monthly data for current year; falls back from M13
BEA_YEARS = list(range(2010, 2025))
FRED_YEARS = list(range(2010, 2025))
QCEW_YEARS = list(range(2014, 2026))  # QCEW API: annual avgs 2014-2024, quarterly fallback 2025

PEP_YEARS = list(range(2010, 2024))  # PEP: components 2010-2019, charv pop 2020-2023

INDICATORS: Dict[str, Dict[str, Any]] = {
    # ================================================================
    # DEMOGRAPHICS
    # ================================================================
    "population": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01003_001E"],
        "label": "Total Population", "fmt": "#,##0",
        "category": "Demographics", "higher_is": "neutral", "change_type": "pct",
    },
    # ================================================================
    # AGE (DP05 — granular ACS buckets + median age)
    # ================================================================
    "median_age": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01002_001E"],
        "label": "Median Age", "fmt": "0.0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    # Age buckets use B01001 (Sex by Age) — stable variable codes across all ACS years.
    # Each bucket sums male + female components.
    "pop_under_5": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_003E", "B01001_027E"],
        "label": "Under 5", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_5_to_9": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_004E", "B01001_028E"],
        "label": "5–9", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_10_to_14": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_005E", "B01001_029E"],
        "label": "10–14", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_15_to_19": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_006E", "B01001_007E", "B01001_030E", "B01001_031E"],
        "label": "15–19", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_20_to_24": {
        "source": "census", "dataset": "acs1",
        "variables": [
            "B01001_008E", "B01001_009E", "B01001_010E",
            "B01001_032E", "B01001_033E", "B01001_034E",
        ],
        "label": "20–24", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_25_to_34": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_011E", "B01001_012E", "B01001_035E", "B01001_036E"],
        "label": "25–34", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_35_to_44": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_013E", "B01001_014E", "B01001_037E", "B01001_038E"],
        "label": "35–44", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_45_to_54": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_015E", "B01001_016E", "B01001_039E", "B01001_040E"],
        "label": "45–54", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_55_to_59": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_017E", "B01001_041E"],
        "label": "55–59", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_60_to_64": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_018E", "B01001_019E", "B01001_042E", "B01001_043E"],
        "label": "60–64", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_65_to_74": {
        "source": "census", "dataset": "acs1",
        "variables": [
            "B01001_020E", "B01001_021E", "B01001_022E",
            "B01001_044E", "B01001_045E", "B01001_046E",
        ],
        "label": "65–74", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_75_to_84": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_023E", "B01001_024E", "B01001_047E", "B01001_048E"],
        "label": "75–84", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_85_plus": {
        "source": "census", "dataset": "acs1",
        "variables": ["B01001_025E", "B01001_049E"],
        "label": "85+", "fmt": "#,##0",
        "category": "Age", "higher_is": "neutral", "change_type": "pct",
    },

    # ================================================================
    # RACE / ETHNICITY (B02001 + B03003 + DP05 for White Non-Hispanic)
    # ================================================================
    "pop_white": {
        "source": "census", "dataset": "acs1",
        "variables": ["B02001_002E"],
        "label": "White Alone", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_white_non_hispanic": {
        "source": "census", "dataset": "acs1",
        "variables": ["B03002_003E"],
        "label": "White, Not Hispanic", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_black": {
        "source": "census", "dataset": "acs1",
        "variables": ["B02001_003E"],
        "label": "Black / African American", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_aian": {
        "source": "census", "dataset": "acs1",
        "variables": ["B02001_004E"],
        "label": "American Indian / Alaska Native", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_asian": {
        "source": "census", "dataset": "acs1",
        "variables": ["B02001_005E"],
        "label": "Asian", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_nhpi": {
        "source": "census", "dataset": "acs1",
        "variables": ["B02001_006E"],
        "label": "Native Hawaiian / Pacific Islander", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_other_race": {
        "source": "census", "dataset": "acs1",
        "variables": ["B02001_007E"],
        "label": "Some Other Race", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_two_or_more": {
        "source": "census", "dataset": "acs1",
        "variables": ["B02001_008E"],
        "label": "Two or More Races", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },
    "pop_hispanic": {
        "source": "census", "dataset": "acs1",
        "variables": ["B03003_003E"],
        "label": "Hispanic / Latino", "fmt": "#,##0",
        "category": "Race / Ethnicity", "higher_is": "neutral", "change_type": "pct",
    },

    # ================================================================
    # INCOME
    # ================================================================
    "median_hh_income": {
        "source": "census", "dataset": "acs1",
        "variables": ["B19013_001E"],
        "label": "Median Household Income", "fmt": "$#,##0",
        "category": "Income", "higher_is": "better", "change_type": "pct",
    },
    "per_capita_income_census": {
        "source": "census", "dataset": "acs1",
        "variables": ["B19301_001E"],
        "label": "Per Capita Income", "fmt": "$#,##0",
        "category": "Income", "higher_is": "better", "change_type": "pct",
    },

    # ================================================================
    # POVERTY (derived)
    # ================================================================
    "poverty_denominator": {
        "source": "census", "dataset": "acs1",
        "variables": ["B17001_001E"],
        "label": "_poverty_denom", "fmt": "#,##0",
        "category": "_internal", "higher_is": "neutral", "change_type": "pct",
        "hidden": True,
    },
    "poverty_below": {
        "source": "census", "dataset": "acs1",
        "variables": ["B17001_002E"],
        "label": "Population Below Poverty", "fmt": "#,##0",
        "category": "Poverty", "higher_is": "worse", "change_type": "pct",
    },
    "poverty_rate": {
        "source": "derived",
        "requires": ["poverty_denominator", "poverty_below"],
        "label": "Poverty Rate (%)", "fmt": "0.0%",
        "category": "Poverty", "higher_is": "worse", "change_type": "pp",
    },

    # ================================================================
    # EDUCATIONAL ATTAINMENT (B15003, population 25+)
    # ================================================================
    "pop_25_plus": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_001E"],
        "label": "Population 25+", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "neutral", "change_type": "pct",
    },
    "edu_bachelors_plus": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"],
        "label": "Bachelor's Degree or Higher (25+)", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "better", "change_type": "pct",
    },
    "edu_bachelors_plus_pct": {
        "source": "derived",
        "requires": ["edu_bachelors_plus", "pop_25_plus"],
        "label": "% Bachelor's Degree or Higher (25+)", "fmt": "0.0%",
        "category": "Educational Attainment", "higher_is": "better", "change_type": "pp",
    },
    "edu_less_than_hs": {
        "source": "census", "dataset": "acs1",
        "variables": [
            "B15003_002E", "B15003_003E", "B15003_004E", "B15003_005E",
            "B15003_006E", "B15003_007E", "B15003_008E", "B15003_009E",
            "B15003_010E", "B15003_011E", "B15003_012E", "B15003_013E",
            "B15003_014E", "B15003_015E", "B15003_016E",
        ],
        "label": "Less than HS Diploma", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "worse", "change_type": "pct",
    },
    "edu_hs_graduate": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_017E", "B15003_018E"],
        "label": "HS Graduate / GED", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "neutral", "change_type": "pct",
    },
    "edu_some_college": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_019E", "B15003_020E"],
        "label": "Some College (No Degree)", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "neutral", "change_type": "pct",
    },
    "edu_associates": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_021E"],
        "label": "Associate's Degree", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "neutral", "change_type": "pct",
    },
    "edu_bachelors": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_022E"],
        "label": "Bachelor's Degree", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "better", "change_type": "pct",
    },
    "edu_masters": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_023E"],
        "label": "Master's Degree", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "better", "change_type": "pct",
    },
    "edu_professional": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_024E"],
        "label": "Professional Degree", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "better", "change_type": "pct",
    },
    "edu_doctorate": {
        "source": "census", "dataset": "acs1",
        "variables": ["B15003_025E"],
        "label": "Doctorate Degree", "fmt": "#,##0",
        "category": "Educational Attainment", "higher_is": "better", "change_type": "pct",
    },

    # ================================================================
    # INDUSTRY (CES supersectors — All Employees, thousands)
    # ================================================================
    "ind_mining_logging": {
        "source": "bls",
        "label": "Mining & Logging Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_construction": {
        "source": "bls",
        "label": "Construction Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_manufacturing": {
        "source": "bls",
        "label": "Manufacturing Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_trade_transport_util": {
        "source": "bls",
        "label": "Trade, Transportation & Utilities Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_wholesale_trade": {
        "source": "bls",
        "label": "Wholesale Trade Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_retail_trade": {
        "source": "bls",
        "label": "Retail Trade Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_transport_warehouse_util": {
        "source": "bls",
        "label": "Transportation, Warehousing & Utilities Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_information": {
        "source": "bls",
        "label": "Information Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_financial": {
        "source": "bls",
        "label": "Financial Activities Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_prof_business": {
        "source": "bls",
        "label": "Professional & Business Services Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_edu_health": {
        "source": "bls",
        "label": "Education & Health Services Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_leisure_hospitality": {
        "source": "bls",
        "label": "Leisure & Hospitality Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_other_services": {
        "source": "bls",
        "label": "Other Services Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },
    "ind_government": {
        "source": "bls",
        "label": "Government Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Industry", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },

    # ================================================================
    # EMPLOYMENT
    # ================================================================
    "labor_force_participation": {
        "source": "census", "dataset": "acs1/subject",
        "variables": ["S2301_C02_001E"],
        "label": "Labor Force Participation Rate", "fmt": "0.0%",
        "category": "Employment", "higher_is": "better", "change_type": "pp",
    },
    "civilian_labor_force": {
        "source": "census", "dataset": "acs1/profile",
        "variables": ["DP03_0003E"],
        "label": "Civilian Labor Force", "fmt": "#,##0",
        "category": "Employment", "higher_is": "better", "change_type": "pct",
    },
    "nonfarm_jobs": {
        "source": "bls",
        "series_prefix": "SMU", "series_suffix": "0000000001",
        "label": "Nonfarm Payroll Jobs (thousands)", "fmt": "#,##0.0",
        "category": "Employment", "higher_is": "better", "change_type": "pct",
        "geo_types": ["msa", "state"],
    },
    "qcew_employment": {
        "source": "qcew",
        "label": "Covered Employment (QCEW)", "fmt": "#,##0",
        "category": "Employment", "higher_is": "better", "change_type": "pct",
        "geo_types": ["msa", "state", "county"],
    },
    "unemployment_rate": {
        "source": "bls",
        "series_prefix": "LAUMT", "series_suffix": "000000003",
        "label": "Unemployment Rate (%)", "fmt": "0.0%",
        "category": "Employment", "higher_is": "worse", "change_type": "pp",
        "geo_types": ["msa", "state", "county"],
    },

    # ================================================================
    # HOUSING
    # ================================================================
    "median_home_value": {
        "source": "census", "dataset": "acs1",
        "variables": ["B25077_001E"],
        "label": "Median Home Value", "fmt": "$#,##0",
        "category": "Housing", "higher_is": "neutral", "change_type": "pct",
    },
    "median_rent": {
        "source": "census", "dataset": "acs1",
        "variables": ["B25064_001E"],
        "label": "Median Gross Rent", "fmt": "$#,##0",
        "category": "Housing", "higher_is": "worse", "change_type": "pct",
    },
    "homeownership_rate": {
        "source": "census", "dataset": "acs1/profile",
        "variables": ["DP04_0046PE"],
        "label": "Homeownership Rate", "fmt": "0.0%",
        "category": "Housing", "higher_is": "neutral", "change_type": "pp",
    },
    "vacancy_rate": {
        "source": "census", "dataset": "acs1/profile",
        "variables": ["DP04_0003PE"],
        "label": "Vacancy Rate", "fmt": "0.0%",
        "category": "Housing", "higher_is": "worse", "change_type": "pp",
    },
    "house_price_index": {
        "source": "fred",
        "fred_series": {
            "msa": "ATNHPIUS{cbsa}Q",
            "state": "{state_abbr}STHPI",
        },
        "label": "House Price Index (FHFA)", "fmt": "0.0",
        "category": "Housing", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa", "state"],
    },
    "building_permits": {
        "source": "fred",
        "display_source": "census",
        "fred_series": {
            "county": "BPPRIV{fips6}",
            "state": "{state_abbr}BPPRIV",
        },
        "label": "Building Permits", "fmt": "#,##0",
        "category": "Housing", "higher_is": "better", "change_type": "pct",
        "geo_types": ["county", "state"],
    },

    # ================================================================
    # HOUSING TYPE (B25024 — Units in Structure)
    # ================================================================
    "hu_single_family": {
        "source": "census", "dataset": "acs1",
        "variables": ["B25024_002E", "B25024_003E"],
        "label": "Single-Family Units", "fmt": "#,##0",
        "category": "Housing Type", "higher_is": "neutral", "change_type": "pct",
    },
    "hu_small_multi": {
        "source": "census", "dataset": "acs1",
        "variables": ["B25024_004E", "B25024_005E", "B25024_006E"],
        "label": "Small Multifamily (2-9 units)", "fmt": "#,##0",
        "category": "Housing Type", "higher_is": "neutral", "change_type": "pct",
    },
    "hu_large_multi": {
        "source": "census", "dataset": "acs1",
        "variables": ["B25024_007E", "B25024_008E", "B25024_009E"],
        "label": "Large Multifamily (10+ units)", "fmt": "#,##0",
        "category": "Housing Type", "higher_is": "neutral", "change_type": "pct",
    },
    "hu_mobile_other": {
        "source": "census", "dataset": "acs1",
        "variables": ["B25024_010E", "B25024_011E"],
        "label": "Mobile Home / Other", "fmt": "#,##0",
        "category": "Housing Type", "higher_is": "neutral", "change_type": "pct",
    },

    # ================================================================
    # MIGRATION (derived)
    # ================================================================
    "migration_from_state": {
        "source": "census", "dataset": "acs1",
        "variables": ["B07001_065E"],
        "label": "_migration_diff_state", "fmt": "#,##0",
        "category": "_internal", "higher_is": "neutral", "change_type": "pct",
        "hidden": True,
    },
    "migration_from_county": {
        "source": "census", "dataset": "acs1",
        "variables": ["B07001_049E"],
        "label": "_migration_diff_county", "fmt": "#,##0",
        "category": "_internal", "higher_is": "neutral", "change_type": "pct",
        "hidden": True,
    },
    "in_migration": {
        "source": "derived",
        "requires": ["migration_from_state", "migration_from_county"],
        "label": "Domestic In-Migration", "fmt": "#,##0",
        "category": "Migration", "higher_is": "better", "change_type": "pct",
    },
    "interstate_in_migration": {
        "source": "derived",
        "requires": ["migration_from_state"],
        "label": "Interstate In-Migration", "fmt": "#,##0",
        "category": "Migration", "higher_is": "better", "change_type": "pct",
    },
    "migration_to_state": {
        "source": "census", "dataset": "acs1",
        "variables": ["B07401_065E"],
        "label": "_migration_to_diff_state", "fmt": "#,##0",
        "category": "_internal", "higher_is": "neutral", "change_type": "pct",
        "hidden": True,
    },
    "migration_to_county": {
        "source": "census", "dataset": "acs1",
        "variables": ["B07401_049E"],
        "label": "_migration_to_diff_county", "fmt": "#,##0",
        "category": "_internal", "higher_is": "neutral", "change_type": "pct",
        "hidden": True,
    },
    "out_migration": {
        "source": "derived",
        "requires": ["migration_to_state", "migration_to_county"],
        "label": "Domestic Out-Migration", "fmt": "#,##0",
        "category": "Migration", "higher_is": "worse", "change_type": "pct",
    },
    "net_domestic_migration": {
        "source": "derived",
        "requires": ["in_migration", "out_migration"],
        "label": "Net Domestic Migration", "fmt": "#,##0",
        "category": "Migration", "higher_is": "better", "change_type": "pct",
    },

    # ================================================================
    # QUALITY OF LIFE
    # ================================================================
    "mean_commute_time": {
        "source": "census", "dataset": "acs1/subject",
        "variables": ["S0801_C01_046E"],
        "label": "Mean Commute Time (min)", "fmt": "0.0",
        "category": "Quality of Life", "higher_is": "worse", "change_type": "pct",
    },
    "pct_no_health_insurance": {
        "source": "census", "dataset": "acs1/subject",
        "variables": ["S2701_C05_001E"],
        "label": "% Uninsured", "fmt": "0.0%",
        "category": "Quality of Life", "higher_is": "worse", "change_type": "pp",
    },

    # ================================================================
    # BEA — Cost of Living
    # ================================================================
    "rpp": {
        "source": "bea", "table": {"msa": "MARPP", "state": "SARPP"}, "line": 1,
        "label": "Regional Price Parity", "fmt": "0.0",
        "category": "Cost of Living", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa", "state"],
    },

    # ================================================================
    # ECONOMY — GDP
    # BEA dropped MSA-level GDP from Regional API. MSA and micro GDP are
    # aggregated from county-level CAGDP2 data using CBSA→county mapping.
    # State and county GDP use CAGDP2 directly.
    # ================================================================
    "gdp": {
        "source": "bea",
        "table": "CAGDP2",
        "line": 1,  # All industry total
        "divisor": 1000,  # BEA reports in thousands → convert to millions
        "county_agg": True,  # MSA/micro GDP aggregated from county-level data
        "label": "GDP (millions of dollars)", "fmt": "#,##0",
        "category": "Economy", "higher_is": "better", "change_type": "pct",
        "geo_types": ["msa", "micro", "state", "county"],
    },
    "gdp_per_capita": {
        "source": "derived",
        "display_source": "bea",
        "requires": ["gdp", "population"],
        "label": "GDP per Capita", "fmt": "$#,##0",
        "category": "Economy", "higher_is": "better", "change_type": "pct",
        "geo_types": ["msa", "micro", "state", "county"],
    },

    # ================================================================
    # COST OF LIVING — COLI (static Q3 2025)
    # ================================================================
    "coli_composite": {
        "source": "coli",
        "label": "COLI Composite Index", "fmt": "0.0",
        "category": "Cost of Living", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa"],
    },

    # ================================================================
    # PEP — Population Estimates Program
    # ================================================================
    "pep_population": {
        "source": "pep",
        "variables": ["POP"],
        "label": "Population Estimate (PEP)", "fmt": "#,##0",
        "category": "Demographics", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa", "state", "county"],
    },
    "pep_births": {
        "source": "pep",
        "variables": ["BIRTHS"],
        "label": "Births", "fmt": "#,##0",
        "category": "Demographics", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa", "state", "county"],
    },
    "pep_deaths": {
        "source": "pep",
        "variables": ["DEATHS"],
        "label": "Deaths", "fmt": "#,##0",
        "category": "Demographics", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa", "state", "county"],
    },
    "pep_net_domestic_migration": {
        "source": "pep",
        "variables": ["DOMESTICMIG"],
        "label": "Net Domestic Migration (PEP)", "fmt": "#,##0",
        "category": "Migration", "higher_is": "better", "change_type": "pct",
        "geo_types": ["msa", "state", "county"],
    },
    "pep_net_international_migration": {
        "source": "pep",
        "variables": ["INTERNATIONALMIG"],
        "label": "Net International Migration", "fmt": "#,##0",
        "category": "Migration", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa", "state", "county"],
    },
    "pep_natural_change": {
        "source": "pep",
        "variables": ["NATURALCHG"],
        "label": "Natural Change (Births - Deaths)", "fmt": "#,##0",
        "category": "Demographics", "higher_is": "neutral", "change_type": "pct",
        "geo_types": ["msa", "state", "county"],
    },
}

VISIBLE_INDICATORS = [k for k, v in INDICATORS.items() if not v.get("hidden")]

# Ordered category list for consistent UI display
CATEGORY_ORDER = [
    "Demographics", "Employment", "Industry", "Economy", "Income",
    "Cost of Living", "Poverty", "Educational Attainment",
    "Housing", "Housing Type", "Migration",
    "Age", "Race / Ethnicity", "Quality of Life",
]
