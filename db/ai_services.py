import os
import json
import base64
import logging
import io
import time
import re
from PIL import Image
import requests

logger = logging.getLogger(__name__)

raw_keys = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

MODELS_CASCADE = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

current_key_index = 0


def _call_gemini_api(payload: dict) -> dict:
    global current_key_index
    if not API_KEYS:
        logger.error("GEMINI_API_KEYS не налаштовано!")
        return {}

    total_keys = len(API_KEYS)
    headers = {"Content-Type": "application/json"}

    for model in MODELS_CASCADE:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt_key in range(total_keys):
            active_key = API_KEYS[current_key_index]
            url = f"{api_url}?key={active_key}"

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=35)

                if response.status_code == 429:
                    logger.warning(
                        f"⚠️ Модель {model} на ключі #{current_key_index + 1} вперлася в ліміт (429). Пауза 1.5с та перемикання..."
                    )
                    current_key_index = (current_key_index + 1) % total_keys
                    time.sleep(1.5)
                    continue

                if response.status_code in [400, 403, 404, 500, 502, 503]:
                    logger.warning(
                        f"⚠️ Модель {model} на ключі #{current_key_index + 1} повернула статус {response.status_code}. Перемикаємо..."
                    )
                    current_key_index = (current_key_index + 1) % total_keys
                    time.sleep(0.3)
                    continue

                if response.status_code != 200:
                    current_key_index = (current_key_index + 1) % total_keys
                    continue

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    current_key_index = (current_key_index + 1) % total_keys
                    continue

                parts = candidates[0].get("content", {}).get("parts", [])
                text_content = "".join([p.get("text", "") for p in parts if "text" in p]).strip()

                json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
                if json_match:
                    text_content = json_match.group(0)

                parsed_data = json.loads(text_content) if text_content else {}
                if parsed_data:
                    logger.warning(f"✅ Успішно отримано дані через {model} (ключ #{current_key_index + 1})")
                    return parsed_data

            except Exception as e:
                logger.error(f"Помилка з'єднання з Gemini API ({model}): {e}")
                current_key_index = (current_key_index + 1) % total_keys
                time.sleep(0.5)

    return {}


def _search_teplomaster(query: str) -> dict:
    """Прямий локальний пошук безпосередньо по teplo-master.com.ua"""
    if not query:
        return {}
    try:
        search_url = "https://teplo-master.com.ua/ua/search/"
        params = {"search": query.strip()}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(search_url, params=params, headers=headers, timeout=5)
        if res.status_code == 200 and "product-thumb" in res.text:
            logger.warning(f"🔍 Знайдено збіг на teplo-master.com.ua для запиту '{query}'")
            return {"site_context": res.text[:8000]}
    except Exception as e:
        logger.warning(f"Прямий запит до teplo-master пропущено: {e}")
    return {}


def _optimize_and_encode_image(uploaded_file, max_size=(1200, 1200)) -> str:
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img = img.convert('RGB')
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as err:
        logger.warning(f"Помилка оптимізації фото: {err}")
        uploaded_file.seek(0)
        return base64.b64encode(uploaded_file.read()).decode('utf-8')


def analyze_barcode_with_ai(barcode: str) -> dict:
    if not barcode:
        return {}

    direct_match = _search_teplomaster(barcode)
    raw_html_hint = direct_match.get("site_context", "")

    if raw_html_hint:
        logger.warning(f"📍 [ДЖЕРЕЛО]: Знайдено прямо на teplo-master.com.ua для '{barcode}'")
    else:
        logger.warning(f"📍 [ДЖЕРЕЛО]: teplo-master не дав збігу. Внутрішня база ШІ для '{barcode}'")

    prompt = f"""
    Ти провідний експерт бази опалювальної техніки (газові, електричні котли та комплектуючі: плати, клапани, датчики, теплообмінники, насоси).
    Штрихкод або артикул товару: "{barcode}".

    {f"Дані з каталогу teplo-master: {raw_html_hint}" if raw_html_hint else ""}

    Сформуй технічні дані про цей товар.
    ВАЖЛИВО:
    1. У compatible_models вкажи сумісні котли (наприклад: "Roda Micra Duo CS24", "Romstal Habitat 20F / 25F").
    2. У compatible_parts вкажи повні найменування сумісних запчастин, вузлів та кодів взаємозамінних аналогів (наприклад: "Теплообмінник Roda Micra Duo CS24 (515001943)", "Теплообмінник Romstal Habitat 20F (515001943)").

    Поверни ВИКЛЮЧНО валідний JSON:
    {{
        "brand": "Бренд (Baxi, Vaillant, Ferroli, Ariston, Roda, Valmex тощо)",
        "article": "Заводський артикул / код",
        "category": "Газовий котел | Електричний котел | Запчастина котла",
        "item_type": "Тип деталі (напр. Первинний теплообмінник, Плата керування, Газовий клапан)",
        "probable_name": "Повна комерційна назва українською мовою з брендом і кодом",
        "compatible_models": ["Список сумісних моделей котлів"],
        "compatible_parts": ["Список сумісних запчастин, вузлів та кодів аналогів"],
        "description": "Технічний опис: призначення, розміри/матеріал, підключення, технічні параметри"
    }}
    Тільки чистий JSON.
    """

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1
        }
    }

    res = _call_gemini_api(payload)
    if res:
        res["source"] = "teplo-master.com.ua" if raw_html_hint else "Внутрішня база знань Gemini"
    return res


def analyze_product_images_with_ai(image_file=None, package_image_file=None) -> dict:
    if not image_file and not package_image_file:
        return {}

    parts = []

    try:
        if image_file:
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": _optimize_and_encode_image(image_file)
                }
            })

        if package_image_file:
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": _optimize_and_encode_image(package_image_file)
                }
            })

        prompt = """
        Ти провідний сервісний інженер опалювального обладнання.
        Твоя база обслуговує газові та електричні котли, а також комплектуючі (теплообмінники, плати, клапани, насоси, датчики).

        ЗАВДАННЯ:
        1. Зчитай маркування, заводський артикул, бренд, назви на шильдику чи упаковці.
        2. Якщо це ЗАПЧАСТИНА (наприклад, теплообмінник, газовий клапан, плата):
           - У "compatible_models" перелічи всі сумісні моделі газових/електричних котлів.
           - У "compatible_parts" перелічи повні назви сумісних запчастин, вузлів та коди взаємозамінних аналогів з артикулами.
        3. Якщо це ЦІЛИЙ КОТЕЛ:
           - У "compatible_models" вкажи модифікації цієї лінійки.
           - "compatible_parts" залиш порожнім масивом [].

        Поверни ВИКЛЮЧНО валідний JSON у форматі:
        {
            "brand": "Бренд",
            "article": "Заводський артикул / партномер",
            "category": "Газовий котел | Електричний котел | Запчастина котла",
            "item_type": "Тип деталі або котла",
            "probable_name": "Повна комерційна назва українською мовою з брендом і кодом",
            "compatible_models": ["Список сумісних моделей котлів"],
            "compatible_parts": ["Список сумісних запчастин, вузлів та кодів-аналогів"],
            "recognized_text": "Увесь розпізнаний текст з маркування/наклейки",
            "description": "Детальний технічний опис: призначення деталі, основні характеристики (розміри, матеріал, тип з'єднання, потужність)"
        }
        Тільки чистий JSON.
        """
        parts.append({"text": prompt})

        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "temperature": 0.1
            }
        }

        res = _call_gemini_api(payload)
        if res:
            res["source"] = "Візуальний аналіз фото (ШІ)"
        return res
    except Exception as e:
        logger.error(f"Помилка аналізу зображень: {e}")
        return {}
