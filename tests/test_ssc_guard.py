import pytest
from kit.ssc_guard import (
    SscInvalid,
    choose_static_gk,
    circular,
    relevant,
    static_gk_from_table,
    validate_qa,
)


def test_q7_headline_question_rejected():
    with pytest.raises(SscInvalid, match="headline template"):
        validate_qa("What is the key development regarding GPT-6 Astra:?", "OpenAI")


def test_q11_not_specified_rejected():
    with pytest.raises(SscInvalid, match="answer is vague"):
        validate_qa("In which state are elections being held for 14,403 village panchayats?", "Not specified")


def test_dropped_qualifier_rejected():
    note_text = "India possesses up to 190 nuclear warheads, according to the report."
    with pytest.raises(SscInvalid, match="drops the qualifier 'up to'"):
        validate_qa("How many nuclear warheads does India have?", "190", note_text=note_text)


def test_retained_qualifier_passes():
    note_text = "India possesses up to 190 nuclear warheads, according to the report."
    validate_qa("How many nuclear warheads does India have?", "Up to 190", note_text=note_text)


def test_by_what_percentage_passes():
    validate_qa(
        "By what percentage is the repo rate proposed to be increased by the RBI on October 7, 2026?",
        "0.25%",
    )


def test_circularity_check():
    assert circular("MNRE is under the Ministry of New and Renewable Energy") is True
    assert circular("MeitY is the nodal ministry for India's IT sector") is False
    assert circular("PPAC operates under the Ministry of Petroleum and Natural Gas") is False


def test_sawalkot_table_override_faridabad():
    line = static_gk_from_table(
        "What is the estimated cost of the Sawalkot hydropower project in J&K?",
        "₹5,129 crore",
        "Project is an NHPC initiative to generate 800 megawatts",
    )
    assert line == "NHPC is a PSU under the Ministry of Power; HQ: Faridabad"


def test_vettri_payanam_madras_hc_returns_blank():
    card = {
        "question": "In Tamil Nadu, what is the name of the scheme providing free travel for women?",
        "answer": "Vettri Payanam",
        "key": "State government allocates ₹6,000 crore annually to compensate transport corporations",
        "static_gk": "Madras High Court was established in 1862; principal bench at Chennai",
    }
    line, source = choose_static_gk(card, lambda s: True)
    assert line == ""
    assert source == "none"


def test_choose_static_gk_table_wins():
    card = {
        "question": "What is the repo rate announced by the RBI?",
        "answer": "6.5%",
        "key": "RBI announced hike",
        "static_gk": "Some gemma fact about RBI",
    }
    line, source = choose_static_gk(card, lambda s: True)
    assert "RBI was established on 1 April 1935" in line
    assert source == "table"


def test_choose_static_gk_gemma_unverified_kept_if_relevant_and_non_circular():
    card = {
        "question": "Which national park released two Great Indian Bustards?",
        "answer": "Desert National Park",
        "key": "Conservation initiative in Rajasthan",
        "static_gk": "Desert National Park is located in Rajasthan",
    }
    line, source = choose_static_gk(card, lambda s: True)
    assert line == "Desert National Park is located in Rajasthan"
    assert source == "gemma-unverified"
