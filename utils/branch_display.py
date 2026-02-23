"""
Branch display name utilities.

Converts long branch names (60-91 chars) to short readable names.
Example: "ศูนย์บริการใบอนุญาตทำงานต่างจังหวัด จังหวัดสมุทรสาคร" -> "ศูนย์บริการ จ.สมุทรสาคร"
"""

import re
import streamlit as st


# Type prefix mapping
TYPE_PREFIX = {
    "SC": "ศูนย์บริการ",
    "OB": "แรกรับ",
    "MB": "โมบาย",
    "HQ": "สำนักงานใหญ่",
}


def _parse_branch_code(branch_code: str) -> dict:
    """Parse branch_code into components.

    Format: XXX-YY-Z-NNN (e.g., SKN-SC-L-001)
    HQ format: XXX-HQ-NNN (e.g., BKK-HQ-001)
    """
    parts = branch_code.split("-") if branch_code else []
    if len(parts) >= 2:
        return {
            "province": parts[0],
            "type": parts[1],
            "size": parts[2] if len(parts) >= 4 else None,
            "seq": parts[3] if len(parts) >= 4 else (parts[2] if len(parts) == 3 else None),
        }
    return {"province": branch_code, "type": "", "size": None, "seq": None}


def _extract_province_name(branch_name: str) -> str:
    """Extract province name from full branch name.

    Patterns:
    - "จังหวัดสมุทรสาคร" -> "สมุทรสาคร"
    - "จ.ชลบุรี" -> "ชลบุรี"
    - "กรุงเทพมหานคร" -> "กทม."
    """
    if not branch_name:
        return ""

    # BKK pattern
    if "กรุงเทพมหานคร" in branch_name:
        return "กทม."

    # Standard province patterns
    m = re.search(r"จังหวัด(\S+)", branch_name)
    if m:
        return m.group(1)

    m = re.search(r"จ\.(\S+)", branch_name)
    if m:
        return m.group(1)

    return ""


def _build_bkk_short_name(branch_code: str, branch_name: str) -> str:
    """Build short name for BKK SC centers (10 centers, must distinguish all).

    Mapping:
    BKK-SC-M-001 -> "ศูนย์บริการ กทม. (One Bangkok)"
    BKK-SC-M-002 -> "ศูนย์บริการ กทม. 1 (สจก. 2)"
    BKK-SC-M-003 -> "ศูนย์บริการ กทม. 2 (สจก. 5)"
    BKK-SC-S-001 -> "ศูนย์บริการ กทม. 5 (สจก. 9)"
    BKK-SC-S-002 -> "ศูนย์บริการ กทม. 6 (สจก. 10)"
    BKK-SC-S-003 -> "ศูนย์บริการ กทม. 4 (สจก. 7)"
    BKK-SC-S-004 -> "ศูนย์บริการ กทม. 3 (สจก. 3)"
    BKK-SC-S-005 -> "ศูนย์บริการ กทม. 5 Non-B (ไอที สแควร์)"
    BKK-SC-S-006 -> "ศูนย์บริการ กทม. 6 Non-B (พงษ์สุภี)"
    BKK-SC-S-007 -> "ศูนย์บริการ กทม. 3 Non-B (บิ๊กซี บางนา)"
    """
    is_non_b = "(Non-B)" in branch_name or "Non-B" in branch_name

    # Special case: One Bangkok
    if "one bangkok" in branch_name.lower():
        return "ศูนย์บริการ กทม. (One Bangkok)"

    # Extract BKK center number: "กรุงเทพมหานคร 5" -> "5"
    m = re.search(r"กรุงเทพมหานคร\s*(\d+)", branch_name)
    center_num = m.group(1) if m else ""

    # Extract qualifier from parentheses
    qualifier = ""
    if is_non_b:
        # For Non-B: extract the distinctive location name
        # BKK-SC-S-005: "(ไอที สแควร์ หลักสี่)" -> "ไอที สแควร์"
        # BKK-SC-S-006: "(อาคารพงษ์สุภี)" -> "พงษ์สุภี"
        # BKK-SC-S-007: "(บิ๊กซี บางนา)" -> "บิ๊กซี บางนา"
        parens = re.findall(r"\(([^)]+)\)", branch_name)
        for p in parens:
            if p == "Non-B" or "ขนาด" in p:
                continue
            qualifier = p
            # Clean up long location names
            if "ไอที สแควร์" in qualifier:
                qualifier = "ไอที สแควร์"
            elif "อาคารพงษ์สุภี" in qualifier or "พงษ์สุภี" in qualifier:
                qualifier = "พงษ์สุภี"
            break
        non_b_tag = " Non-B"
    else:
        non_b_tag = ""
        # For regular: extract สจก. number
        m2 = re.search(r"สจก\.\s*(\d+)", branch_name)
        if m2:
            qualifier = f"สจก. {m2.group(1)}"

    if center_num and qualifier:
        return f"ศูนย์บริการ กทม. {center_num}{non_b_tag} ({qualifier})"
    elif center_num:
        return f"ศูนย์บริการ กทม. {center_num}{non_b_tag}"
    else:
        return f"ศูนย์บริการ กทม.{non_b_tag}"


def get_branch_short_name(branch_code: str, branch_name: str) -> str:
    """Convert long branch name to short readable display name.

    Args:
        branch_code: e.g. "SKN-SC-L-001"
        branch_name: Full Thai name from DB

    Returns:
        Short display name, e.g. "ศูนย์บริการ จ.สมุทรสาคร"
    """
    if not branch_code or not branch_name:
        return branch_name or branch_code or "-"

    parsed = _parse_branch_code(branch_code)
    btype = parsed["type"]
    province_code = parsed["province"]

    # HQ special case
    if btype == "HQ":
        return "สำนักงานใหญ่"

    # FTS special case
    if province_code == "FTS":
        return "ศูนย์กำกับและควบคุม"

    prefix = TYPE_PREFIX.get(btype, btype)

    # BKK SC: complex disambiguation needed
    if province_code == "BKK" and btype == "SC":
        return _build_bkk_short_name(branch_code, branch_name)

    # BKK MB
    if province_code == "BKK" and btype == "MB":
        return f"{prefix} กทม."

    # Extract province name
    province_name = _extract_province_name(branch_name)

    if not province_name:
        # Fallback to branch_code
        return f"{prefix} ({branch_code})"

    # Check for Non-B
    is_non_b = "(Non-B)" in branch_name or "Non-B" in branch_name

    # Provinces with multiple SC centers need qualifier
    # CBI: 3 SC (main, EEC, EEC Non-B)
    if province_code == "CBI" and btype == "SC":
        if "EEC" in branch_name:
            nb = " Non-B" if is_non_b else ""
            return f"{prefix} จ.{province_name} (EEC{nb})"
        else:
            return f"{prefix} จ.{province_name}"

    # RNG: 2 SC (main, สาขาศูนย์แรกรับ)
    if province_code == "RNG" and btype == "SC":
        if "สาขาศูนย์แรกรับ" in branch_name or "สาขา" in branch_name:
            return f"{prefix} จ.{province_name} (สาขาแรกรับ)"
        else:
            return f"{prefix} จ.{province_name}"

    # TAK: 2 SC (main, สาขาศูนย์แรกรับ)
    if province_code == "TAK" and btype == "SC":
        if "สาขาศูนย์แรกรับ" in branch_name or "สาขา" in branch_name:
            return f"{prefix} จ.{province_name} (สาขาแรกรับ)"
        else:
            return f"{prefix} จ.{province_name}"

    # Standard single-center province
    if is_non_b:
        return f"{prefix} จ.{province_name} (Non-B)"

    return f"{prefix} จ.{province_name}"


@st.cache_data(ttl=3600)
def get_branch_short_name_map() -> dict:
    """Get cached {branch_code: short_display_name} mapping from DB.

    Returns:
        dict mapping branch_code to short readable name
    """
    from database.connection import get_session
    from database.models import BranchMaster

    session = get_session()
    try:
        branches = session.query(
            BranchMaster.branch_code,
            BranchMaster.branch_name
        ).all()
        return {
            b.branch_code: get_branch_short_name(b.branch_code, b.branch_name)
            for b in branches
            if b.branch_code
        }
    finally:
        session.close()
