import pytest
try:
    from kit.ssc_validate import (SscInvalid, check_card_v4, filter_pointers, rank_pointers,
                                  validate_key, validate_static_gk)
except ImportError:
    from ssc_validate import (SscInvalid, check_card_v4, filter_pointers, rank_pointers,
                              validate_key, validate_static_gk)

Y = 2026


# ---- regression: the three failing notes
def test_q11_venue_pointer_is_dropped_and_envoy_ranks_first():
    pointers = [
        "Bay of Bengal Conversation: Event venue/context for the clarification",
        "Dinesh Trivedi: India's High Commissioner in Dhaka",
    ]
    kept = filter_pointers(pointers)
    assert len(kept) == 1 and kept[0].startswith("Dinesh Trivedi")
    assert rank_pointers(pointers, headline="High Commissioner clarifies Hasina arrival")[0] == kept[0]


def test_q24_hydraa_news_is_rejected_as_static_gk():
    with pytest.raises(SscInvalid, match="no permanent anchor"):
        validate_static_gk(
            "HYDRAA: Granted statutory roles against encroachments under CURE Act",
            key="Covers a 2,053 sq. km urban region", year=Y)


def test_q2_purpose_fused_with_deadline_is_rejected():
    with pytest.raises(SscInvalid, match="routine purpose"):
        validate_key("Project aims to mitigate power shortages during peak hours by April 6, 2028", Y)


def test_q2_attributed_deadline_passes():
    validate_key("KSEB aims to complete the project by April 6, 2028.", Y)
    validate_key("Peak-hour supply: battery storage shifts solar power to the evening.", Y)


# ---- controls: good static GK from the current PDF must still pass
@pytest.mark.parametrize("sgk", [
    "White Revolution (Operation Flood) was launched in 1970 by Dr. Verghese Kurien",
    "Indus Water Treaty was signed in 1960 between India and Pakistan; mediated by World Bank",
    "Reserve Bank of India was established on 1 April 1935 under the RBI Act, 1934; HQ: Mumbai",
    "NHPC is a public-sector undertaking under the Ministry of Power",
    "Article 243D of the Constitution provides a minimum 33% (one-third) reservation for women",
    "Capital of Germany: Berlin; Currency: Euro",
    "Madras High Court, Chennai, established in 1869, is the oldest High Court in India",
])
def test_good_static_gk_passes(sgk):
    validate_static_gk(sgk, key="unrelated key text", year=Y)


# ---- other guards
def test_static_gk_repeating_key_is_rejected():
    key = "FPIs sold a total of Rs 45,536 crore in equity in September"
    with pytest.raises(SscInvalid, match="repeats the KEY"):
        validate_static_gk(key + " as analysts watch yields", key=key, year=Y)


def test_recent_year_is_rejected():
    with pytest.raises(SscInvalid, match="current affairs"):
        validate_static_gk("Scheme launched in 2026 under the Ministry of Rural Development", year=Y)


def test_assembly_term_key_is_not_a_false_positive():
    validate_key("Assembly term ends in March 2027", Y)


def test_full_card_entry_point():
    card = {"question": "Who is the Chief Electoral Officer of Kerala?", "answer": "D. Sajith Babu",
            "key": "Announced drive to re-enroll 8.97 lakh voters removed during SIR",
            "static_gk": "Election Commission of India is established under Article 324 of the Constitution"}
    check_card_v4(card, Y)


@pytest.mark.parametrize("sgk", [
    "Minamata Convention on Mercury was adopted in 2013 under UNEP",
    "KMSCL is under Department of Health, Government of Kerala",
    "SEEDAP operates under Directorate of Skill Development",
    "Strait of Hormuz is a vital strait connecting the Persian Gulf and the Gulf of Oman",
    "Western Ghats is a UNESCO World Heritage site and global biodiversity hotspot in India",
    "Jennifer Doudna received the Nobel Prize in Chemistry in 2020 for CRISPR gene editing",
])
def test_new_anchors_pass(sgk):
    validate_static_gk(sgk, key="unrelated key text", year=Y)


def test_fallback_static_gk_lookup():
    from kit.ssc_validate import fallback_static_gk
    assert fallback_static_gk("SEBI proposed changes to CAS") is not None
    assert "SEBI Act, 1992" in fallback_static_gk("SEBI")
    assert "Department of Health" in fallback_static_gk("KMSCL debt")
    assert fallback_static_gk("unrelated random query") is None

