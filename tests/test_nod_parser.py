"""Unit tests for the NOD parser.

These tests use *extracted text strings* as fixtures rather than real PDF
binaries. This keeps the test repo free of client documents and makes the
parser logic testable independent of pdfplumber's PDF extraction.

The text fixtures below are representative of the four document layouts the
parser was designed against:
  - Federal pleading (Western District of Texas)
  - Texas state pleading (judicial district + county)
  - Multi-deposition packet
  - Section-symbol (§) column table layout
"""
from __future__ import annotations

from backend.services.nod_parser import type_a_form, type_b_pleading


# --- Type B: legal pleading -----------------------------------------

FEDERAL_PLEADING = """\
UNITED STATES DISTRICT COURT
WESTERN DISTRICT OF TEXAS
SAN ANTONIO DIVISION
DELIA GARZA
Plaintiff,
vs. CIVIL ACTION NO.:25-cv-00598-OLG
HOME DEPOT U.S.A., INC. A/K/A
THE HOME DEPOT AND SHAWN
HERBER
Defendants.
PLAINTIFF'S NOTICE OF INTENTION TO TAKE ORAL / ZOOM DEPOSITION
OF HEATH THOMAS
Deponent: Heath Thomas
Date: Thursday April 30, 2026
Time: 1:30 p.m. (Central Time)
Location: Via Zoom (remote video conference)
Respectfully submitted,
BRAIN AND SPINE PERSONAL INJURY LAWYERS, PLLC
/s/ Steven A. Nunez
STEVEN A. NUNEZ
State Bar No. 24107206
"""

STATE_PLEADING = """\
CAUSE NO. 2021CI17153
DANIEL TREVINO
Plaintiff,
IN THE DISTRICT COURT
VS. 225TH JUDICIAL DISTRICT
YC PARTNERS LTD.
Defendant. OF BEXAR COUNTY, TEXAS
PLAINTIFF'S NOTICE OF INTENTION TO TAKE ORAL AND VIDEO TRIAL DEPOSITION
Please take notice that, on Tuesday, May 12, 2026 at 3:00 p.m. and continuing
will take the oral and video trial deposition of Yury Sless, M.D. (and/or YS
Orthopedics, PLLC) via remote video conference proceedings (Zoom).
Respectfully submitted,
LAW OFFICES OF ISRAEL GARCIA
By: /s/ Israel Garcia
Israel Garcia
Texas State Bar No. 24040950
"""


def test_detect_jurisdiction_federal():
    assert type_b_pleading.detect_jurisdiction(FEDERAL_PLEADING) == "federal"


def test_detect_jurisdiction_state():
    assert type_b_pleading.detect_jurisdiction(STATE_PLEADING) == "texas_state"


def test_detect_jurisdiction_other():
    assert type_b_pleading.detect_jurisdiction("just some random text") == "other"


def test_federal_case_identity():
    identity = type_b_pleading.extract_case_identity(FEDERAL_PLEADING)
    assert identity["case_number_value"] == "25-cv-00598-OLG"
    assert identity["case_number_label"] == "civil_action_no"
    assert identity["court_district"] == "Western District of Texas"
    assert identity["jurisdiction_type"] == "federal"


def test_state_case_identity():
    identity = type_b_pleading.extract_case_identity(STATE_PLEADING)
    assert identity["case_number_value"] == "2021CI17153"
    assert identity["case_number_label"] == "cause_no"
    assert identity["judicial_district"] == "225th Judicial District"
    assert identity["county"] == "Bexar County"


def test_federal_caption():
    caption = type_b_pleading.extract_caption(FEDERAL_PLEADING)
    assert caption is not None
    assert "DELIA GARZA" in caption
    assert "HOME DEPOT" in caption
    assert " vs. " in caption


def test_federal_deponent():
    deponents = type_b_pleading.extract_deponents(FEDERAL_PLEADING)
    assert "Heath Thomas" in deponents


def test_federal_date():
    assert type_b_pleading.extract_date(FEDERAL_PLEADING) == "2026-04-30"


def test_state_date():
    assert type_b_pleading.extract_date(STATE_PLEADING) == "2026-05-12"


def test_federal_time():
    assert type_b_pleading.extract_time(FEDERAL_PLEADING) == "1:30 PM"


def test_state_time():
    assert type_b_pleading.extract_time(STATE_PLEADING) == "3:00 PM"


def test_zoom_location_detection():
    loc = type_b_pleading.extract_location(FEDERAL_PLEADING)
    assert type_b_pleading.is_zoom_location(loc)


def test_signing_attorney_federal():
    signing = type_b_pleading.extract_signing_attorney(FEDERAL_PLEADING)
    assert signing.get("custodial_name") == "Steven A. Nunez"


def test_signing_attorney_state():
    signing = type_b_pleading.extract_signing_attorney(STATE_PLEADING)
    assert signing.get("custodial_name") == "Israel Garcia"


def test_ordinal_suffix():
    assert type_b_pleading._ordinal_suffix(1) == "st"
    assert type_b_pleading._ordinal_suffix(2) == "nd"
    assert type_b_pleading._ordinal_suffix(3) == "rd"
    assert type_b_pleading._ordinal_suffix(11) == "th"
    assert type_b_pleading._ordinal_suffix(225) == "th"
    assert type_b_pleading._ordinal_suffix(101) == "st"


# --- Multi-notice detection -----------------------------------------

MULTI_NOTICE = """\
CAUSE NO. C-1628-25-E
AMENDED NOTICE OF INTENTION TO TAKE ORAL DEPOSITION OF
ALFREDO MONTES NAVARRO AND DUCES TECUM
the oral deposition of ALFREDO MONTES NAVARRO, will be taken on May
7, 2026, commencing at 2:00 p.m., via Zoom.
AMENDED NOTICE OF INTENTION TO TAKE ORAL DEPOSITION OF
MARIA L. LOPEZ DE MARTINEZ AND DUCES TECUM
the oral deposition of MARIA L. LOPEZ DE MARTINEZ, will be taken on
May 7, 2026, commencing at 10:00 a.m., via Zoom.
"""


def test_multi_notice_sections_detected():
    sections = type_b_pleading.find_notice_sections(MULTI_NOTICE)
    assert len(sections) == 2


def test_single_notice_not_oversplit():
    # Federal pleading has one notice; must not be split into many
    sections = type_b_pleading.find_notice_sections(FEDERAL_PLEADING)
    assert len(sections) == 1


# --- Type A: firm form ----------------------------------------------

TYPE_A_FORM = """\
4/30/2026 Brain & Spine Personal Heath Thomas CR+Zoom
Court Reporting
Location: via Zoom Date: 4/30/2026
Deponent: Heath Thomas
Case/Style: Delia Garza v. Home Depot USA, INC., et al
CSR: Yes Sch Start Time:1:30 PM
Ordering Attorney:Steven A. Nunez Firm: Format: Delivery:
Brain & Spine Personal Injury Lawyers Original Standard
Address: Phone: (210) 999-5033 Email: E-Trans Rush Due:
service@brainspine-law.com
Copy Attorney: Karen M. Copy? Firm: Format: Delivery:
Alvarado Yes / No Brothers Alvarado Piazza & Cozort Original Standard
Odered by: Tiffany Netcher
"""


def test_type_a_detection():
    assert type_a_form.looks_like_type_a(TYPE_A_FORM)
    assert not type_a_form.looks_like_type_a("random unrelated text")


def test_type_a_extracts_deponent():
    result = type_a_form.parse(TYPE_A_FORM)
    assert result.get("deponent") == "Heath Thomas"


def test_type_a_extracts_date():
    result = type_a_form.parse(TYPE_A_FORM)
    assert result.get("form_date_raw") == "4/30/2026"


def test_type_a_extracts_start_time():
    result = type_a_form.parse(TYPE_A_FORM)
    assert result.get("form_start_time") == "1:30 PM"


def test_type_a_extracts_ordering_attorney():
    result = type_a_form.parse(TYPE_A_FORM)
    assert result.get("ordering_attorney") == "Steven A. Nunez"


def test_type_a_csr_required():
    result = type_a_form.parse(TYPE_A_FORM)
    assert result.get("csr_required") is True


def test_split_email_stitching():
    # pdfplumber wraps long emails — verify they get rejoined
    wrapped = "Email: service@brainspine-law.co\nm\nNext line"
    fixed = type_a_form._stitch_split_email(wrapped)
    assert "service@brainspine-law.com" in fixed


# --- Two-firm signature block (the real Brain & Spine / Cukjati NOD) --

FEDERAL_PLEADING_TWO_FIRMS = """\
UNITED STATES DISTRICT COURT
WESTERN DISTRICT OF TEXAS
SAN ANTONIO DIVISION
DELIA GARZA
Plaintiff,
vs. CIVIL ACTION NO.:25-cv-00598-OLG
HOME DEPOT U.S.A., INC. A/K/A
THE HOME DEPOT AND SHAWN
HERBER
Defendants.
PLAINTIFF'S NOTICE OF INTENTION TO TAKE ORAL / ZOOM DEPOSITION
OF HEATH THOMAS
TO: Defendant, HOME DEPOT U.S.A., INC., by and through its attorney of record, Karen M.
Alvarado, BROTHERS, ALVARADO, PIAZZA & COZORT, P.C., 10333 Richmond, Suite
900, Houston, Texas 77042.
Deponent: Heath Thomas
Date: Thursday April 30, 2026
Time: 1:30 p.m. (Central Time)
Location: Via Zoom (remote video conference)
Respectfully submitted,
CUKJATI LAW FIRM, PLLC
Jacob D. Cukjati
State Bar No. 24101188
Curtis L. Cukjati, Of Counsel
State Bar No. 05207540
875 East Ashby Place, Ste. 1225
San Antonio, Texas 78212
-and-
BRAIN AND SPINE PERSONAL
INJURY LAWYERS OF SAN
ANTONIO, PLLC
/s/ Steven A. Nunez
STEVEN A. NUNEZ
State Bar No. 24107206
8620 N New Braunfels Ave, Ste. N 604
San Antonio, TX 78217-4000
ATTORNEYS FOR PLAINTIFF
DELIA GARZA
"""


def test_signing_firm_is_firm_above_signature_not_first_firm():
    """The signer's firm is the one directly above /s/, not the first
    firm listed. Here the signature block lists Cukjati Law Firm first,
    but Steven A. Nunez signs for Brain & Spine."""
    signing = type_b_pleading.extract_signing_attorney(FEDERAL_PLEADING_TWO_FIRMS)
    assert signing["custodial_name"] == "Steven A. Nunez"
    assert "Brain and Spine" in signing["requesting_party"]
    assert "Cukjati" not in signing["requesting_party"]


def test_extract_appearances_finds_every_attorney():
    appearances = type_b_pleading.extract_appearances(FEDERAL_PLEADING_TWO_FIRMS)
    by_name = {a["name"]: a for a in appearances}
    assert set(by_name) == {
        "Jacob D. Cukjati", "Curtis L. Cukjati",
        "Steven A. Nunez", "Karen M. Alvarado",
    }
    assert by_name["Steven A. Nunez"]["bar_number"] == "24107206"
    assert by_name["Steven A. Nunez"]["side"] == "plaintiff"
    assert by_name["Karen M. Alvarado"]["side"] == "defendant"
    assert "Brothers" in by_name["Karen M. Alvarado"]["firm"]
    # The signer's firm is corrected to the firm above the /s/.
    assert "Brain and Spine" in by_name["Steven A. Nunez"]["firm"]


def test_extract_all_firms():
    firms = type_b_pleading.extract_all_firms(FEDERAL_PLEADING_TWO_FIRMS)
    joined = " | ".join(firms)
    assert "Cukjati Law Firm" in joined
    assert "Brain and Spine" in joined
    assert "Brothers, Alvarado, Piazza & Cozort" in joined
