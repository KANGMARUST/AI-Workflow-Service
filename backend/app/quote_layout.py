"""Read explicitly ordered quotation rows without calculating missing values."""
import re


NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
ROW = re.compile(rf"^(?P<name>.+?)\s+(?P<quantity>{NUMBER})\s+(?P<unit>[A-Za-z가-힣]+)\s+(?P<unit_price>{NUMBER})\s+(?P<amount>{NUMBER})(?:\s+(?P<remark>.*))?$")


def key(value):
    return re.sub(r"\s+", "", value).casefold()


def pdf_line_items(pages):
    """Only recognize the explicit NO/name/quantity/unit/price/amount layout.

    Repeated numbered rows across pages are one parent, while unnumbered priced
    rows remain components. Specifications without a price stay with their item.
    Return no replacement if a numbered row cannot be read unambiguously.
    """
    items, repeated, parent, current = [], {}, None, None
    for page_number, text in enumerate(pages, 1):
        active = False
        for line in text.splitlines():
            compact = key(line)
            if any(header in compact for header in ("품명수량단위단가금액", "品名數量單位單價金額", "品名數量單位單價金額")):
                active = True
                continue
            if not active:
                continue
            if "이하여백" in compact or "금액합계" in compact or compact.startswith("합계"):
                active = False
                continue
            numbered = re.match(r"^(\d+)\s+(.+)$", line)
            source = numbered[2] if numbered else line
            match = ROW.fullmatch(source.strip())
            if match:
                fields = match.groupdict()
                name = fields.pop("name").strip()
                remark = fields.pop("remark")
                if not numbered and parent is None:
                    return []
                identity = (numbered[1], key(name), *(fields[k] for k in ("quantity", "unit", "unit_price", "amount"))) if numbered else None
                old = repeated.get(identity)
                if old and old["raw_fields"]["source_page"] != page_number:
                    current = parent = old
                    old["raw_fields"].setdefault("repeated_on_pages", []).append(page_number)
                    continue
                raw = {"source_page": page_number, "source_line": line, "line_type": "standalone"}
                if remark:
                    raw["remark"] = remark
                item = {"item_name": name, "original_item_name": name, "specification": None,
                        **{k: v.replace(",", "") if k != "unit" else v for k, v in fields.items()}, "raw_fields": raw}
                if numbered:
                    repeated[identity] = item
                    parent = item
                else:
                    parent["raw_fields"]["line_type"] = "group"
                    raw.update(line_type="component", parent_item_name=parent["item_name"], included_in_parent=True)
                items.append(item)
                current = item
            elif numbered:
                # Avoid silently dropping a row with a missing or ambiguous numeric cell.
                return []
            elif current and re.match(r"^\s*[-•]", line) and not re.search(r"\(DESCRIPTION\)|\(AMOUNT\)", line):
                current["specification"] = "\n".join(filter(None, (current["specification"], line.strip())))
    return items


def apply_document_rows(extracted, document):
    rows = document.get("line_items")
    if not rows:
        return extracted
    result = dict(extracted)
    result["items"] = rows
    return result
