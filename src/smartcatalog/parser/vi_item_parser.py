import re
from fuzzywuzzy import process
from smartcatalog.loader.brand_loader import load_known_brands

def extract_explicit_brand(text, brand_list, threshold=85):
    """
    Only tries to fuzzy-match a brand if the text mentions something brand-like.
    It avoids matching entire lines that contain only 'tương đương' or no real brand names.
    """
    # Cut off anything after "hoặc tương đương" to focus on possible brand mention
    if "hoặc tương đương" in text.lower():
        target_part = text.lower().split("hoặc tương đương")[0]
    else:
        target_part = text.lower()

    brand_match, score = process.extractOne(target_part, brand_list)
    print(f"DEBUG: '{text}' → closest brand: {brand_match} ({score})")

    if score >= threshold:
        return brand_match
    return None


def parse_vietnamese_item(text):
    result = {
        "raw_text": text.strip(),
        "tool": None,
        "shape": None,
        "length_mm": None,
        "tip": None,
        "quantity": None,
        "brand": None,
        "coating_or_tip": None,
        "material": None,
        "handle_color": None,
        "product_category": None,
    }

    text_lc = text.lower()

    # Tool
    match_tool = re.match(r"([a-záàạảãâấầậăắằặẻẽêếềệểễôốồộổơớờợởỡưứừựửữđ\s\-]+)", text_lc)
    if match_tool:
        result["tool"] = match_tool.group(1).strip()

    if not result["tool"]:
        for keyword in ["kéo", "kẹp", "nhíp", "dao", "banh", "ống hút"]:
            if keyword in text_lc:
                result["tool"] = keyword
                break

    # Shape
    if "cong" in text_lc:
        result["shape"] = "cong"
    elif "thẳng" in text_lc:
        result["shape"] = "thẳng"

    # Length
    match_len = re.search(r"dài[^0-9]{0,10}(\d{2,4})\s*mm", text_lc)
    if match_len:
        result["length_mm"] = int(match_len.group(1))

    # Tip
    if "mũi tù" in text_lc:
        result["tip"] = "tù"
    elif "mũi nhọn" in text_lc:
        result["tip"] = "nhọn"

    # Quantity
    match_qty = re.search(r"(\d+)\s*(cái|bộ|chiếc)", text_lc)
    if match_qty:
        result["quantity"] = f"{match_qty.group(1)} {match_qty.group(2)}"

    # known_brands = [
    # # Primary brands from docx
    # "Amnotec", "Taenia",  # explicit from docx

    # # Tool-based known brands/models in doc
    # "Backhaus", "Foerster-Ballenger", "Metzenbaum", "Mayo", "Yankauer", "Poole", "Crile", "Crile-Rankin", 
    # "Allis", "Babcock", "De Bakey", "De Bakey-Pean Atraumata", "Gemini", "Doyen", "Cushing", "Waugh",
    # "Ribbon", "US-Army", "Parker-Langenbeck", "Richardson-Eastman", "Deaver", "Balfour", "Hegar-Mayo", 
    # "De Bakey Atraumata", "Mayo-Hegar", "Crafoord", "Coller", "Kocher-Ochsner",

    # # Other surgical manufacturers (global set)
    # "Stille", "Medicon", "Martin", "KLS Martin", "Aesculap", "Gimmi", "Lawton", "Sklar", "Chifa", 
    # "Paramount", "Braun", "B. Braun", "Zimmer", "Olympus", "Tuttnauer", "Stryker",

    # # Additional surgical tool names (model/family)
    # "Halstead", "Mosquito", "Kelly", "Pean", "Ochsner", "Spencer Wells", "Sims", "Hegar", "Halsey", 
    # "Heaney", "Hohmann", "Langenbeck", "Luer", "Mikulicz", "Noyes", "Olsen", "Parker", "Penfield", 
    # "Riley", "Senn", "Tilley", "Weitlaner", "Ziegler", "Dandy", "Frazier", "Hirschman", "Kerrison", 
    # "Luer-Lok", "Senn-Miller", "Jameson", "Koos", "Jacobson", "Caspar", "Herz", "Jackson",
    # "Kraus", "Alti", "Dejerine", "Troemmer", "Landolt", "Muehling", "Ragnell", "Collin", 
    # "Rampley", "Reverdin", "Rosen", "Reynolds", "Buck", "Townley", "Minimus", "Maximus", 
    # "Pachon", "Precisa", "Caroll", "Jaeger", "Kleinert-Kutz", "Bunnell", "Yasargil"
    # ]

    known_brands = load_known_brands()

    brand = extract_explicit_brand(text, known_brands)
    if brand:
        result["brand"] = brand

    # Coating
    if "supercut" in text_lc:
        result["coating_or_tip"] = "Supercut"
    elif "wave cut" in text_lc:
        result["coating_or_tip"] = "Wave Cut"
    elif "diamond" in text_lc:
        result["coating_or_tip"] = "Diamond"
    elif "tc" in text_lc:
        result["coating_or_tip"] = "TC"

    # Material
    if "thép không gỉ" in text_lc:
        result["material"] = "Stainless Steel"
    elif "titan" in text_lc:
        result["material"] = "Titanium"
    elif "nhựa" in text_lc:
        result["material"] = "Plastic"

    # Handle
    if "cán vàng" in text_lc or "mạ vàng" in text_lc:
        result["handle_color"] = "vàng"
    elif "cán đen" in text_lc:
        result["handle_color"] = "đen"
    elif "cán xanh" in text_lc:
        result["handle_color"] = "xanh"
    elif "cán nhám" in text_lc:
        result["handle_color"] = "nhám"

    # Category
    if "kéo" in text_lc:
        result["product_category"] = "Scissors"
    elif "kẹp" in text_lc:
        result["product_category"] = "Clamp"
    elif "nhíp" in text_lc:
        result["product_category"] = "Forceps"
    elif "banh" in text_lc:
        result["product_category"] = "Retractor"
    elif "dao mổ" in text_lc:
        result["product_category"] = "Scalpel"
    elif "ống hút" in text_lc:
        result["product_category"] = "Suction"

    return result


def batch_parse_vi_items(lines):
    return [parse_vietnamese_item(line) for line in lines]
