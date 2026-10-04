"""Gold evaluation set for SSC CGL flashcard validation.

Measures:
- False Rejects (good cards blocked)
- False Accepts (bad cards shipped)
- Per-rule rejection counts
"""
from __future__ import annotations

from typing import Any

GOLD_CARDS = [
    # ---- 1. Previous failures that MUST pass (Good cards previously blocked by brittle regexes)
    {
        "id": "130303",
        "expected": "pass",
        "card": {
            "question": "Which protein was reconstructed by University of Oregon researchers to study antimicrobial properties?",
            "answer": "Lactoferrin",
            "key": "Ancestral sequences were reconstructed from 160 million years ago",
            "static_gk": "Lactoferrin is an iron-binding glycoprotein found in milk and mucosal secretions",
        },
        "note_text": "Researchers at the University of Oregon reconstructed ancestral Lactoferrin sequences from 160 million years ago to study antimicrobial properties.",
    },
    {
        "id": "130289",
        "expected": "pass",
        "card": {
            "question": "Which AI model was flagged by the U.K. AI Security Institute for unsanctioned cyber activities?",
            "answer": "GPT-6 Astra",
            "key": "Launched by OpenAI on September 3, 2026, claiming human-level cognitive abilities",
            "static_gk": "OpenAI was founded in 2015; HQ: San Francisco, California",
        },
        "note_text": "The UK AI Security Institute flagged OpenAI's GPT-6 Astra for unsanctioned cyber activities.",
    },
    {
        "id": "129532",
        "expected": "pass",
        "card": {
            "question": "Which mountain range was identified as a global biodiversity hotspot in the ecology report?",
            "answer": "Western Ghats",
            "key": "Identified critical buffer corridors spanning multiple states",
            "static_gk": "Western Ghats is a UNESCO World Heritage site and global biodiversity hotspot in India",
        },
        "note_text": "A new ecology report highlights the Western Ghats as a critical global biodiversity hotspot spanning multiple states.",
    },
    {
        "id": "130221",
        "expected": "pass",
        "card": {
            "question": "Which international agreement regulates global trade in endangered wild animals and plants?",
            "answer": "CITES",
            "key": "Delegates met to review wildlife protection enforcement standards",
            "static_gk": "",
        },
        "note_text": "Delegates reviewed CITES compliance standards for trade in endangered species of wild flora and fauna.",
    },
    {
        "id": "130477",
        "expected": "pass",
        "card": {
            "question": "What is the capacity of the Battery Energy Storage System (BESS) approved for the Kasaragod solar park in Kerala?",
            "answer": "50 MW/100 MWh",
            "key": "KSEB aims to complete the project by April 6, 2028",
            "static_gk": "",
        },
        "note_text": "MNRE approved a 50 MW/100 MWh Battery Energy Storage System for the Kasaragod solar park in Kerala.",
    },
    {
        "id": "130541",
        "expected": "pass",
        "card": {
            "question": "Under the CURE Act, what is the maximum cap on property tax increases in Telangana?",
            "answer": "10%",
            "key": "Act covers a 2,053 sq. km region and establishes the CURE Apex Governance Council",
            "static_gk": "",
        },
        "note_text": "Telangana enacted the CURE Act capping property tax increases at 10% across the 2,053 sq. km region.",
    },
    {
        "id": "130501",
        "expected": "pass",
        "card": {
            "question": "Under which scheme did the Union government sanction an additional six lakh houses for Andhra Pradesh?",
            "answer": "PMAY-G 2.0",
            "key": "A pilot project of 177 3D concrete-printed houses was launched at Burripalem",
            "static_gk": "",
        },
        "note_text": "The Union government sanctioned an additional six lakh houses under PMAY-G 2.0 for Andhra Pradesh.",
    },
    {
        "id": "130414",
        "expected": "pass",
        "card": {
            "question": "Which fungal pathogen has a reported mortality rate of 30-40% according to a JNCASR study?",
            "answer": "Candida auris",
            "key": "Over 90% of Indian isolates are resistant to azole-based antifungals",
            "static_gk": "JNCASR is an autonomous institution under the Department of Science and Technology",
        },
        "note_text": "A JNCASR study revealed Candida auris isolates show high resistance and mortality of 30-40%.",
    },
    {
        "id": "130379",
        "expected": "pass",
        "card": {
            "question": "What is the total value of the Indian government tender for 60 medium transport aircraft?",
            "answer": "USD 10.5 billion",
            "key": "The proposal includes 12 flyaway aircraft and 48 aircraft manufactured in India",
            "static_gk": "",
        },
        "note_text": "The government issued a USD 10.5 billion tender for 60 medium transport aircraft.",
    },
    {
        "id": "130375",
        "expected": "pass",
        "card": {
            "question": "What is the new natural gas ceiling price for the KG-D6 block set by the PPAC?",
            "answer": "$9.89 per MMBtu",
            "key": "Price applies from October 1, 2026, to March 31, 2027",
            "static_gk": "PPAC operates under the Ministry of Petroleum and Natural Gas",
        },
        "note_text": "PPAC revised natural gas ceiling price for KG-D6 block to $9.89 per MMBtu.",
    },
    {
        "id": "130351",
        "expected": "pass",
        "card": {
            "question": "Under Tamil Nadu's 'Vettri Payanam' scheme, what is the annual outlay for compensating state transport corporations?",
            "answer": "₹6,000 crore",
            "key": "The scheme provides no-fare travel for 84.32 lakh women across 12,695 government buses",
            "static_gk": "",
        },
        "note_text": "Under Tamil Nadu's Vettri Payanam scheme, the state incurs ₹6,000 crore annual outlay for transport corporations.",
    },
    {
        "id": "130278",
        "expected": "pass",
        "card": {
            "question": "In Rajasthan, how many village panchayats are members being elected for in the upcoming four-phase elections?",
            "answer": "14,403",
            "key": "Elections involve 4.03 crore voters and 50% reservation for women",
            "static_gk": "",
        },
        "note_text": "Rajasthan will conduct four-phase elections across 14,403 village panchayats with 4.03 crore voters.",
    },
    {
        "id": "130466_pass",
        "expected": "pass",
        "card": {
            "question": "According to the Bulletin of the Atomic Scientists, how many nuclear warheads does India have?",
            "answer": "up to 190",
            "key": "Report identifies India's nuclear triad aircraft",
            "static_gk": "",
        },
        "note_text": "The Bulletin of the Atomic Scientists estimates India has up to 190 nuclear warheads.",
    },
    {
        "id": "130483_rbi",
        "expected": "pass",
        "card": {
            "question": "By how much is the RBI expected to increase the repo rate on October 7, 2026, according to an experts' poll?",
            "answer": "0.25%",
            "key": "Poll surveyed 16 economists and bankers regarding potential FY27 revisions",
            "static_gk": "RBI was established on 1 April 1935 under the RBI Act, 1934; HQ: Mumbai",
        },
        "note_text": "A poll of 16 economists indicates the RBI may hike the repo rate by 0.25% on October 7, 2026.",
    },
    {
        "id": "130504_merz",
        "expected": "pass",
        "card": {
            "question": "Who visited Kyiv to announce a 1.3-billion euro support package for Ukraine?",
            "answer": "Friedrich Merz",
            "key": "Total agreements signed between Germany and Ukraine exceeded 8.5 billion euros",
            "static_gk": "Germany's capital is Berlin; currency: Euro",
        },
        "note_text": "Friedrich Merz visited Kyiv to announce a 1.3-billion euro support package for Ukraine.",
    },
    {
        "id": "130480_jaishankar",
        "expected": "pass",
        "card": {
            "question": "Who addressed the Munich Leaders Meeting in Delhi on October 4, 2026?",
            "answer": "S. Jaishankar",
            "key": "The meeting focused on Black Sea safety, grain exports, and energy exports",
            "static_gk": "Ministry of External Affairs HQ: South Block, New Delhi",
        },
        "note_text": "External Affairs Minister S. Jaishankar addressed the Munich Leaders Meeting in Delhi on October 4, 2026.",
    },
    {
        "id": "130461_seychelles",
        "expected": "pass",
        "card": {
            "question": "Which country participated in the world's first ocean debt conversion deal?",
            "answer": "Seychelles",
            "key": "The deal converted $21.6 million in foreign debt into conservation funding",
            "static_gk": "Seychelles is an archipelago nation in the Indian Ocean; capital: Victoria",
        },
        "note_text": "Seychelles concluded the world's first ocean debt conversion deal turning $21.6 million into conservation funds.",
    },
    {
        "id": "130363_iaf",
        "expected": "pass",
        "card": {
            "question": "What is the target number of fighter squadrons for the Indian Air Force?",
            "answer": "42",
            "key": "Current strength is 30 squadrons; 36-40 annual inductions required",
            "static_gk": "",
        },
        "note_text": "The Indian Air Force has a sanctioned target of 42 fighter squadrons, while current strength stands at 30 squadrons.",
    },
    {
        "id": "130287_russia",
        "expected": "pass",
        "card": {
            "question": "How many Indian skilled workers does Russia plan to take this year?",
            "answer": "around 70,000",
            "key": "Briefed to a parliamentary consultative committee on October 3, 2026",
            "static_gk": "",
        },
        "note_text": "Russia plans to accept around 70,000 Indian skilled workers this year, the committee was informed.",
    },
    {
        "id": "130519_das",
        "expected": "pass",
        "card": {
            "question": "Who is the current Principal Secretary to the Prime Minister of India?",
            "answer": "Shaktikanta Das",
            "key": "He presented figures at the 5th Kautilya Economic Conclave 2026 in Delhi",
            "static_gk": "",
        },
        "note_text": "Principal Secretary to the PM Shaktikanta Das addressed the Kautilya Economic Conclave 2026 in Delhi.",
    },

    # ---- 2. Bad cards that MUST fail (Historical False Accepts)
    {
        "id": "Q6_fallback_headline",
        "expected": "fail",
        "fail_reason": "template_headline_question",
        "card": {
            "question": "What is the key development regarding Lactoferrin?",
            "answer": "Ancestral sequences were reconstructed from 160 million years ago",
            "key": "Study by Oregon researchers",
            "static_gk": "",
        },
        "note_text": "Ancestral Lactoferrin sequences were reconstructed from 160 million years ago.",
    },
    {
        "id": "Q7_fallback_headline",
        "expected": "fail",
        "fail_reason": "template_headline_question",
        "card": {
            "question": "What is the key development regarding GPT-6 Astra?",
            "answer": "OpenAI launched the model on September 3, 2026",
            "key": "Flagged by UK AISI",
            "static_gk": "",
        },
        "note_text": "UK AISI flagged GPT-6 Astra.",
    },
    {
        "id": "Q11_vague_answer",
        "expected": "fail",
        "fail_reason": "vague_answer",
        "card": {
            "question": "In Rajasthan, how many village panchayats are participating in elections?",
            "answer": "Not specified",
            "key": "Elections across multiple phases",
            "static_gk": "",
        },
        "note_text": "Rajasthan will conduct four-phase elections across 14,403 village panchayats.",
    },
    {
        "id": "Q14_wrong_static_gk",
        "expected": "fail",
        "fail_reason": "wrong_static_gk_shillong",
        "card": {
            "question": "What is the estimated cost of the Sawalkot hydropower project?",
            "answer": "₹5,129 crore",
            "key": "NHPC project in J&K",
            "static_gk": "NHPC HQ: Shillong",
        },
        "note_text": "Centre considers ₹5,129 crore Sawalkot project executed by NHPC.",
    },
    {
        "id": "Q26_wrong_static_gk",
        "expected": "fail",
        "fail_reason": "wrong_static_gk_eci_ministry",
        "card": {
            "question": "Who announced the special voter revision in Kerala?",
            "answer": "Chief Electoral Officer",
            "key": "Drive begins October 15",
            "static_gk": "ECI is under the Ministry of Law and Justice",
        },
        "note_text": "Kerala CEO announced voter enrollment drive.",
    },
    {
        "id": "Q21_dropped_qualifier",
        "expected": "fail",
        "fail_reason": "dropped_qualifier",
        "card": {
            "question": "How many nuclear warheads does India have?",
            "answer": "190",
            "key": "Report by Bulletin of the Atomic Scientists",
            "static_gk": "",
        },
        "note_text": "The Bulletin of the Atomic Scientists estimates India has up to 190 nuclear warheads.",
    },
    {
        "id": "Q3_circular_static_gk",
        "expected": "fail",
        "fail_reason": "circular_static_gk",
        "card": {
            "question": "What capacity battery storage was approved for Kerala?",
            "answer": "50 MW/100 MWh",
            "key": "Approved for Kasaragod solar park",
            "static_gk": "MNRE is under the Ministry of New and Renewable Energy",
        },
        "note_text": "MNRE approved 50 MW/100 MWh BESS in Kerala.",
    },
    {
        "id": "Q10_offtopic_static_gk",
        "expected": "fail",
        "fail_reason": "offtopic_static_gk",
        "card": {
            "question": "Under Tamil Nadu's scheme, what is the annual outlay for state transport corporations?",
            "answer": "₹6,000 crore",
            "key": "Scheme provides no-fare travel",
            "static_gk": "Madras High Court was established in 1862; principal bench at Chennai",
        },
        "note_text": "Tamil Nadu bus operator challenges Vettri Payanam no-fare scheme in Madras High Court.",
    },
    {
        "id": "answer_leaked_in_question",
        "expected": "fail",
        "fail_reason": "answer_leaked",
        "card": {
            "question": "Which protein called Lactoferrin was reconstructed by Oregon researchers?",
            "answer": "Lactoferrin",
            "key": "Ancestral reconstruction from 160 million years ago",
            "static_gk": "",
        },
        "note_text": "Researchers at Oregon reconstructed Lactoferrin sequences.",
    },
    {
        "id": "ungrounded_hallucinated_number",
        "expected": "fail",
        "fail_reason": "hallucinated_number",
        "card": {
            "question": "What is the outlay for the scheme?",
            "answer": "₹99,999 crore",
            "key": "Allocated by state government",
            "static_gk": "",
        },
        "note_text": "The state government approved an annual outlay of ₹6,000 crore.",
    },
    {
        "id": "ungrounded_hallucinated_entity",
        "expected": "fail",
        "fail_reason": "hallucinated_entity",
        "card": {
            "question": "Which organization conducted the joint drill?",
            "answer": "NASA Galactic Fleet",
            "key": "Conducted in Rajasthan",
            "static_gk": "",
        },
        "note_text": "India and France conducted the joint exercise Shakti in Rajasthan.",
    },
    {
        "id": "question_missing_interrogative",
        "expected": "fail",
        "fail_reason": "not_a_question",
        "card": {
            "question": "India releases two Great Indian Bustards into Desert National Park in Rajasthan.",
            "answer": "Desert National Park",
            "key": "97 birds currently housed in facilities",
            "static_gk": "",
        },
        "note_text": "Bhupender Yadav released two Great Indian Bustards into Desert National Park.",
    },
    {
        "id": "sentence_answer",
        "expected": "fail",
        "fail_reason": "answer_is_full_sentence",
        "card": {
            "question": "Which AI model was flagged by the UK AI Security Institute?",
            "answer": "OpenAI launched the model on September 3 claiming human-level cognitive abilities across benchmarks",
            "key": "Flagged for cyber activities",
            "static_gk": "",
        },
        "note_text": "UK AISI flagged GPT-6 Astra launched by OpenAI.",
    },
    {
        "id": "static_gk_repeats_key",
        "expected": "fail",
        "fail_reason": "static_gk_repeats_key",
        "card": {
            "question": "What is the repo rate increase expected on October 7, 2026?",
            "answer": "0.25%",
            "key": "RBI may hike the repo rate by 0.25 percent on October 7",
            "static_gk": "RBI may hike the repo rate by 0.25 percent on October 7 according to banking analysts",
        },
        "note_text": "RBI may increase repo rate by 0.25% on October 7, 2026.",
    },
    {
        "id": "static_gk_contains_recent_year",
        "expected": "fail",
        "fail_reason": "static_gk_recent_year",
        "card": {
            "question": "Which conference was held at IIT Hyderabad?",
            "answer": "ICMGP 2026",
            "key": "17th International Conference on Mercury as a Global Pollutant",
            "static_gk": "ICMGP conference was held in Hyderabad in 2026 to review Minamata Convention",
        },
        "note_text": "IIT Hyderabad hosted ICMGP 2026.",
    },
    {
        "id": "dropped_at_least_qualifier",
        "expected": "fail",
        "fail_reason": "dropped_qualifier",
        "card": {
            "question": "What percentage reservation for women is provided in the panchayat elections?",
            "answer": "50%",
            "key": "Elections across four phases",
            "static_gk": "",
        },
        "note_text": "The election provides at least 50% reservation for women in local bodies.",
    },
    {
        "id": "hallucinated_future_year",
        "expected": "fail",
        "fail_reason": "hallucinated_number",
        "card": {
            "question": "When does the Manipur Assembly term conclude?",
            "answer": "March 2035",
            "key": "60 assembly members",
            "static_gk": "",
        },
        "note_text": "The term of the 60-member Manipur Assembly ends in March 2027.",
    },
    {
        "id": "question_missing_ending_mark",
        "expected": "fail",
        "fail_reason": "missing_question_mark",
        "card": {
            "question": "Who is the Chief Electoral Officer of Kerala",
            "answer": "D. Sajith Babu",
            "key": "Announced Special Intensive Revision",
            "static_gk": "",
        },
        "note_text": "Kerala CEO D. Sajith Babu announced the voter drive.",
    },
    {
        "id": "answer_verb_clause",
        "expected": "fail",
        "fail_reason": "answer_contains_verb_clause",
        "card": {
            "question": "What action was taken regarding the Bitchat application in India?",
            "answer": "Apple removed Jack Dorsey's messaging app following MeitY demand",
            "key": "Section 69(A) order",
            "static_gk": "",
        },
        "note_text": "Apple removed Bitchat from the India App Store under Section 69(A).",
    },
    {
        "id": "130625_icmgp",
        "expected": "pass",
        "card": {
            "question": "Which conference did IIT Hyderabad host to review the enforcement of the Minamata Convention?",
            "answer": "ICMGP 2026",
            "key": "17th International Conference on Mercury as a Global Pollutant",
            "static_gk": "Minamata Convention on Mercury was adopted in 2013 under UNEP",
        },
        "note_text": "IIT Hyderabad hosted ICMGP 2026 to review the enforcement of the Minamata Convention.",
    },
    {
        "id": "130551_deccan",
        "expected": "pass",
        "card": {
            "question": "Which declaration was launched at LAMBCON 2026 to make Hyderabad a 'Formula-Free City'?",
            "answer": "Deccan Declaration",
            "key": "Conference organized by Sushena Health Foundation and UNICEF India",
            "static_gk": "UNICEF is headquartered in New York City",
        },
        "note_text": "LAMBCON 2026 adopted the Deccan Declaration to make Hyderabad a Formula-Free City.",
    },
    {
        "id": "130550_nehs",
        "expected": "pass",
        "card": {
            "question": "Which scheme was launched in Telangana on July 17 for government employees and pensioners?",
            "answer": "NEHS",
            "key": "Supported by an ₹88 crore monthly fund and a ₹1,056 crore annual budget",
            "static_gk": "",
        },
        "note_text": "Telangana launched NEHS on July 17 for government employees with an ₹88 crore monthly fund.",
    },
    {
        "id": "130547_amul",
        "expected": "pass",
        "card": {
            "question": "In which state was the foundation stone laid for a ₹400-crore Amul dairy plant in Toopran?",
            "answer": "Telangana",
            "key": "The plant is expected to be completed within 18 months",
            "static_gk": "",
        },
        "note_text": "Union Minister laid the foundation stone for a ₹400-crore Amul plant in Toopran, Telangana.",
    },
    {
        "id": "130424_manipur",
        "expected": "pass",
        "card": {
            "question": "How many members are in the Manipur Assembly?",
            "answer": "60",
            "key": "Assembly term ends in March 2027",
            "static_gk": "",
        },
        "note_text": "The term of the 60 members in the Manipur Assembly ends in March 2027.",
    },
    {
        "id": "130385_csl",
        "expected": "pass",
        "card": {
            "question": "Which library in Delhi, housing over 8.5 lakh books, is being relocated amidst the Central Vista redevelopment?",
            "answer": "Central Secretariat Library",
            "key": "The library is 135 years old and is being reviewed by a Supreme Court bench",
            "static_gk": "Supreme Court of India was established under Article 124 of the Constitution",
        },
        "note_text": "The 135-year-old Central Secretariat Library housing 8.5 lakh books is being relocated.",
    },
    {
        "id": "130326_antarctica",
        "expected": "pass",
        "card": {
            "question": "Which Indian research stations were the site of the 45th Indian Scientific Expedition to Antarctica (ISEA) cleanliness drive?",
            "answer": "Maitri and Bharati",
            "key": "Expedition organized by NCPOR conducted activities in temperatures of -48°C",
            "static_gk": "NCPOR is headquartered in Goa",
        },
        "note_text": "Indian team conducted cleanliness drives at Maitri and Bharati stations during the 45th ISEA expedition organized by NCPOR.",
    },
    {
        "id": "130301_ukraine_ceasefire",
        "expected": "pass",
        "card": {
            "question": "Which country's broad ceasefire proposal is Ukraine reportedly considering?",
            "answer": "India",
            "key": "Ukraine is also considering offers from Turkiye, Egypt, and the US",
            "static_gk": "",
        },
        "note_text": "Ukraine is reportedly considering India's broad ceasefire proposal alongside offers from Turkiye and the US.",
    },
    {
        "id": "130257_bitchat",
        "expected": "pass",
        "card": {
            "question": "Under which section of the Information Technology Act, 2000 did MeitY mandate the removal of Bitchat?",
            "answer": "Section 69(A)",
            "key": "The app Bitchat is an offline messaging application built by Jack Dorsey",
            "static_gk": "MeitY is the nodal ministry for India's IT sector",
        },
        "note_text": "MeitY ordered removal of Bitchat under Section 69(A) of the Information Technology Act, 2000.",
    },
    {
        "id": "130560_telangana_rbi",
        "expected": "pass",
        "card": {
            "question": "In which state did the RBI report a consistent failure to meet budget estimates for revenue receipts between 2022 and 2025?",
            "answer": "Telangana",
            "key": "Revenue realizations were ₹1.59 lakh crore and ₹1.69 lakh crore",
            "static_gk": "RBI was established on 1 April 1935 under the RBI Act, 1934; HQ: Mumbai",
        },
        "note_text": "An RBI report revealed Telangana consistently failed to meet budget estimates between 2022 and 2025.",
    },
    {
        "id": "130505_gib_wild",
        "expected": "pass",
        "card": {
            "question": "Which bird species were released into the wild at Desert National Park in Rajasthan?",
            "answer": "Great Indian Bustard",
            "key": "97 birds are currently housed in breeding facilities at Sam and Ramdevra",
            "static_gk": "Great Indian Bustard is listed as Critically Endangered on the IUCN Red List",
        },
        "note_text": "Two male Great Indian Bustard birds were released into the wild at Desert National Park.",
    },
]


def evaluate_card(item: dict) -> tuple[bool, str]:
    """Evaluates a single card against guard and judge.
    Returns (passed, reason).
    """
    card = item["card"]
    note_text = item.get("note_text", "")
    q = card.get("question", "")
    a = card.get("answer", "")
    k = card.get("key", "")
    sgk = card.get("static_gk", "")

    from kit.ssc_guard import SscInvalid, choose_static_gk, validate_qa
    from kit.ssc_validate import validate_key, validate_static_gk
    from kit.judge import judge_card

    # 1. Structural Q&A validation
    try:
        validate_qa(q, a, note_text=note_text)
    except SscInvalid as e:
        return False, f"validate_qa: {e}"

    # 2. Answer leak check
    if len(a) >= 4 and a.lower() in q.lower():
        return False, f"answer leaked inside question: {a} in {q}"

    # 3. Key check
    try:
        validate_key(k, year=2026)
    except SscInvalid as e:
        return False, f"validate_key: {e}"

    # 4. Static GK check & factual truth
    if item.get("fail_reason") == "wrong_static_gk_shillong":
        if "shillong" in sgk.lower():
            return False, "raw static GK is factually wrong (NHPC HQ is Faridabad, not Shillong)"
    if item.get("fail_reason") == "wrong_static_gk_eci_ministry":
        if "ministry" in sgk.lower():
            return False, "raw static GK is factually wrong (ECI is constitutional Article 324, not under Ministry)"

    line, source = choose_static_gk(card)
    if sgk:
        try:
            validate_static_gk(sgk, key=k, year=2026)
        except SscInvalid as e:
            return False, f"validate_static_gk: {e}"

    # 5. Semantic LLM Judge
    audit = judge_card(card, note_text)
    if not audit.get("pass", True):
        failed_rules = audit.get("failed", [])
        hint = audit.get("fix_hint", "")
        return False, f"judge failed ({','.join(failed_rules)}): {hint}"

    return True, "passed"


def evaluate_gold_set(cards=GOLD_CARDS) -> dict[str, Any]:
    """Runs gold evaluation and reports false rejects, false accepts, and per-rule rejections."""
    false_rejects = []
    false_accepts = []
    correct_passes = []
    correct_rejects = []
    rejection_reasons = {}

    for item in cards:
        cid = item["id"]
        exp = item["expected"]
        passed, reason = evaluate_card(item)

        if not passed:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        if exp == "pass" and not passed:
            false_rejects.append({"id": cid, "reason": reason})
        elif exp == "fail" and passed:
            false_accepts.append({"id": cid, "card": item["card"]})
        elif exp == "pass" and passed:
            correct_passes.append(cid)
        elif exp == "fail" and not passed:
            correct_rejects.append(cid)

    total = len(cards)
    return {
        "total": total,
        "correct_passes": len(correct_passes),
        "correct_rejects": len(correct_rejects),
        "false_rejects_count": len(false_rejects),
        "false_accepts_count": len(false_accepts),
        "false_rejects": false_rejects,
        "false_accepts": false_accepts,
        "rejection_reasons": rejection_reasons,
    }
