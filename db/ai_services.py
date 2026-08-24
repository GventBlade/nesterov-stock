import os
import json
import base64
import logging
import io
import time
from PIL import Image
import requests

logger = logging.getLogger(__name__)

# Зчитуємо пул ключів через кому
raw_keys = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

PRIMARY_MODEL = "gemini-3.7-flash"
FALLBACK_MODEL = "gemini-2.0-flash"

current_key_index = 0


def _call_gemini_api(payload: dict) -> dict:
    global current_key_index
    if not API_KEYS:
        logger.error("GEMINI_API_KEYS не налаштовано!")
        return {}

    total_keys = len(API_KEYS)
    headers = {"Content-Type": "application/json"}

    # Спершу пробуємо 3.7-flash, якщо перевантажена або вичерпана — переходимо на 2.0-flash
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]

    for model in models_to_try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for _ in range(total_keys):
            active_key = API_KEYS[current_key_index]
            url = f"{api_url}?key={active_key}"

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=45)

                # Перемикання на наступний ключ при ліміті (429) або перевантаженні (503, 500, 502)
                if response.status_code in [429, 500, 502, 503]:
                    logger.warning(
                        f"Модель {model} на ключі #{current_key_index + 1} повернула {response.status_code}. "
                        f"Перемикаємося на наступний ключ..."
                    )
                    current_key_index = (current_key_index + 1) % total_keys
                    time.sleep(0.3)
                    continue

                if response.status_code != 200:
                    logger.error(f"Gemini API помилка {response.status_code}: {response.text}")
                    break

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    break

                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

                if text_content.startswith("```"):
                    text_content = text_content.strip("`")
                    if text_content.startswith("json"):
                        text_content = text_content[4:].strip()

                return json.loads(text_content) if text_content else {}

            except Exception as e:
                logger.error(f"Помилка з'єднання з Gemini API ({model}, ключ #{current_key_index + 1}): {e}")
                current_key_index = (current_key_index + 1) % total_keys
                time.sleep(0.3)

    logger.error("Усі запити до Gemini API вичерпано (всі ключі та моделі зайняті або недоступні).")
    return {}


def _optimize_and_encode_image(uploaded_file, max_size=(1400, 1400)) -> str:
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img = img.convert('RGB')
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as err:
        logger.warning(f"Не вдалося оптимізувати через Pillow: {err}")
        uploaded_file.seek(0)
        return base64.b64encode(uploaded_file.read()).decode('utf-8')


def analyze_barcode_with_ai(barcode: str) -> dict:
    if not barcode:
        return {}

    prompt = f"""
    Ти експерт спеціалізованого складу опалювальної техніки.
    Специфікація складу: виключно ГАЗОВІ та ЕЛЕКТРИЧНІ опалювальні котли та ВСІ запчастини й розхідники до них (від ущільнювальних кілець, прокладок, мембран, сальників, датчиків NTC до плат керування, вентиляторів, газових клапанів SIT/Honeywell, теплообмінників, циркуляційних насосів та готових котлів).
    (Суворе обмеження: жодних твердопаливних котлів чи колонок).

    Штрихкод або артикул товару: "{barcode}".

    Поверни виключно валідний JSON у форматі:
    {{
        "brand": "Бренд (Baxi, Ariston, Vaillant, Protherm, Bosch, Viessmann, Ferroli, SIT, Honeywell, Zilmet тощо)",
        "article": "Заводський артикул або код деталі",
        "category": "Тип товару: 'Газовий котел', 'Електричний котел' або 'Запчастина котла'",
        "item_type": "Точний тип (наприклад: Плата керування, Прокладка, Теплообмінник вторинний, Газовий котел настінний)",
        "probable_name": "Повна комерційна назва українською мовою",
        "compatible_models": ["Моделі газових/електричних котлів, де застосовується"],
        "description": "Стислий технічний опис призначення"
    }}
    Тільки чистий JSON.
    """

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    return _call_gemini_api(payload)


def analyze_product_images_with_ai(image_file=None, package_image_file=None) -> dict:
    if not image_file and not package_image_file:
        return {}

    parts = []

    try:
        if image_file:
            img_b64 = _optimize_and_encode_image(image_file)
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": img_b64
                }
            })

        if package_image_file:
            pkg_b64 = _optimize_and_encode_image(package_image_file)
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": pkg_b64
                }
            })

        prompt = """
        Ти головний експерт-технік складу газових і електричних котлів та запчастин до них.
        На складі є тільки:
        - Газові котли та електричні котли.
        - Всі запчастини до них (ущільнення, мембрани, датчики NTC, плати, газові клапани, вентилятори, насоси, теплообмінники).

        Проаналізуй фото товару та маркування на шильдику/упаковці.
        Зчитай: назву, заводський артикул, бренд, тип деталі, сумісність з котлами, характеристики (kW, bar, V).

        Поверни JSON:
        {
            "brand": "Бренд",
            "article": "Артикул / Код деталі з шильдика",
            "category": "Газовий котел, Електричний котел або Запчастина котла",
            "item_type": "Конкретна деталь або тип котла",
            "probable_name": "Повна назва українською мовою з моделлю та брендом",
            "compatible_models": ["Перелік сумісних котлів"],
            "recognized_text": "Повний розпізнаний текст з маркування/шильдика",
            "description": "Технічний опис"
        }
        Тільки чистий JSON.
        """
        parts.append({"text": prompt})

        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }

        return _call_gemini_api(payload)
    except Exception as e:
        logger.error(f"Помилка обробки фото: {e}")
        return {}
