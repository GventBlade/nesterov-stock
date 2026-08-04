import json
from urllib.parse import urlparse, parse_qs

def parse_barcode_extra_info(barcode: str) -> dict:
    raw_data = str(barcode).strip()
    length = len(raw_data)
    is_num = raw_data.isdigit()

    attributes = {}
    barcode_format = "UNKNOWN"

    # 1. Перевірка, чи це JSON-код (часто шифрують у QR-кодах)
    if raw_data.startswith('{') and raw_data.endswith('}'):
        try:
            parsed_json = json.loads(raw_data)
            barcode_format = "QR_JSON_DATA"
            attributes["qr_type"] = "JSON"
            attributes["json_payload"] = parsed_json
            return {
                "raw_barcode": raw_data,
                "length": length,
                "is_numeric": False,
                "format": barcode_format,
                "parsed_attributes": attributes
            }
        except json.JSONDecodeError:
            pass

    # 2. Перевірка, чи це URL (QR-код із посиланням)
    if raw_data.startswith(('http://', 'https://')):
        barcode_format = "QR_URL"
        parsed_url = urlparse(raw_data)
        attributes["qr_type"] = "URL"
        attributes["domain"] = parsed_url.netloc
        attributes["path"] = parsed_url.path
        attributes["query_params"] = parse_qs(parsed_url.query)

    # 3. Обробка стандартних EAN-13 / UPC (12-13 цифр)
    elif length in (12, 13) and is_num:
        barcode_format = "STANDARD_EAN_UPC"
        ean13 = raw_data.zfill(13)
        prefix = ean13[:3]
        attributes["prefix"] = prefix

        if prefix == "482":
            attributes["country"] = "Україна 🇺🇦"
        elif prefix == "590":
            attributes["country"] = "Польща 🇵🇱"
        elif "800" <= prefix <= "839":
            attributes["country"] = "Італія 🇮🇹 (Ariston)"
        elif "400" <= prefix <= "440":
            attributes["country"] = "Німеччина 🇩🇪"
        elif "690" <= prefix <= "699":
            attributes["country"] = "Китай 🇨🇳"
        else:
            attributes["country"] = f"Країна (GS1: {prefix})"

    # 4. Обробка довгих серійних номерів (DataMatrix / Code-128)
    elif length >= 15:
        barcode_format = "DATAMATRIX_OR_SERIAL"
        attributes["serial_number"] = raw_data
        if is_num and length >= 10:
            attributes["article_code"] = raw_data[:7]

    else:
        barcode_format = "GENERIC_TEXT_OR_SHORT_CODE"

    return {
        "raw_barcode": raw_data,
        "length": length,
        "is_numeric": is_num,
        "format": barcode_format,
        "parsed_attributes": attributes
    }
