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
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

current_key_index = 0

TRUSTED_SITES = [
    "teplo-master.com.ua",
    "gazkomplekt.com.ua",
    "teplota.ua",
    "master-plus.com.ua",
    "teploarmatura.com"
]


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
                response = requests.post(url, headers=headers, json=payload, timeout=40)

                if response.status_code in [400, 403, 404, 429, 500, 502, 503]:
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
                text_content = ""
                for part in parts:
                    if "text" in part:
                        text_content += part["text"]

                text_content = text_content.strip()

                # Надійне вилучення чистого JSON
                json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
                if json_match:
                    text_content = json_match.group(0)

                parsed_data = json.loads(text_content) if text_content else {}
                if parsed_data:
                    logger.info(f"✅ Успішно отримано дані через {model}")
                    return parsed_data

            except Exception as e:
                logger.error(f"Помилка з'єднання з Gemini API ({model}): {e}")
                current_key_index = (current_key_index + 1) % total_keys
                time.sleep(0.3)

    return {}


def _search_teplomaster(query: str) -> dict:
    """Пріоритет #1: Прямий пошук по сайту магазину teplo-master.com.ua"""
    if not query:
        return {}
    try:
        search_url = "https://teplo-master.com.ua/ua/search/"
        params = {"search": query.strip()}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(search_url, params=params, headers=headers, timeout=6)
        if res.status_code == 200 and "product-thumb" in res.text:
            logger.info(f"🔍 Знайдено збіг безпосередньо на teplo-master.com.ua для запиту '{query}'")
            return {"site_context": res.text[:12000]}
    except Exception as e:
        logger.warning(f"Не вдалося виконати прямий запит до teplo-master: {e}")
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
        logger.warning(f"Помилка оптимізації фото: {err}")
        uploaded_file.seek(0)
        return base64.b64encode(uploaded_file.read()).decode('utf-8')


def analyze_barcode_with_ai(barcode: str) -> dict:
    if not barcode:
        return {}

    direct_match = _search_teplomaster(barcode)
    raw_html_hint = direct_match.get("site_context", "")

    prompt = f"""
    Ти головний експерт-технік бази опалювальної техніки (тільки ГАЗОВІ/ЕЛЕКТРИЧНІ котли та всі запчастини до них).
    Штрихкод або артикул товару: "{barcode}".

    {f"УВАГА: Ось вихідні дані пошуку з рідного сайту teplo-master.com.ua: {raw_html_hint}" if raw_html_hint else ""}

    ІЄРАРХІЯ ПОШУКУ ІНФОРМАЦІЇ ТА ОПИСУ:
    1. ПРІОРИТЕТ #1: Дані та детальний опис із сайту teplo-master.com.ua.
    2. ПРІОРИТЕТ #2 (якщо на teplo-master немає): Перевір інформацію з топ-сайтів запчастин та котлів:
       - gazkomplekt.com.ua (вибухові схеми та сумісність)
       - teplota.ua (описи та інструкції)
       - master-plus.com.ua (маркування та коди аналогів)
       - teploarmatura.com
    3. ПРІОРИТЕТ #3: Загальні каталоги виробників (Baxi, Vaillant, Ariston, Protherm, Viessmann, SIT, Honeywell, Ferroli тощо).

    Згенеруй максимально детальний і точний технічний опис: призначення, сумісні моделі котлів, технічні параметри (потужність, тиск, різьба/діаметр, напруга, кількість пластин якщо це теплообмінник).

    Поверни ВИКЛЮЧНО валідний JSON у такому форматі:
    {{
        "brand": "Бренд виробника",
        "article": "Точний заводський артикул/код",
        "category": "Газовий котел | Електричний котел | Запчастина котла",
        "item_type": "Тип деталі (Плата керування, Газовий клапан, Теплообмінник вторинний, Датчик NTC, Вентилятор тощо)",
        "probable_name": "Повна комерційна назва українською мовою з брендом і моделлю",
        "compatible_models": ["Перелік сумісних серій та моделей котлів"],
        "description": "Повний, розгорнутий технічний опис (як на teplo-master / gazkomplekt): призначення, технічні особливості, характеристики"
    }}
    Тільки чистий JSON.
    """

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "tools": [{"google_search": {}}],
        "generationConfig": {
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
        Твоя база обслуговує виключно:
        - Газові та електричні котли.
        - Усі комплектуючі (плати, клапани SIT/Honeywell, вторинні/первинні теплообмінники, вентилятори, датчики NTC, триходові, насоси Wilo/Grundfos, мембрани, ущільнення).

        ЗАВДАННЯ:
        1. Зчитай маркування, заводський артикул, логотип бренду, написи на шильдику чи заводській наклейці коробки.
        2. Знайди інформацію про цю деталь, надаючи найвищий пріоритет сайту teplo-master.com.ua, а далі сайтам gazkomplekt.com.ua, teplota.ua, master-plus.com.ua.
        3. Сформуй детальний опис товару, його призначення та повний список сумісних котлів.

        Поверни JSON:
        {
            "brand": "Бренд",
            "article": "Заводський артикул / код з шильдика",
            "category": "Газовий котел | Електричний котел | Запчастина котла",
            "item_type": "Точний тип деталі або котла",
            "probable_name": "Повна назва українською мовою з брендом та серією",
            "compatible_models": ["Список сумісних моделей котлів"],
            "recognized_text": "Увесь розпізнаний текст з маркування/наклейки",
            "description": "Детальний технічний опис: призначення деталі, основні характеристики (потужність, тиск, діаметри, опір)"
        }
        Тільки чистий JSON.
        """
        parts.append({"text": prompt})

        payload = {
            "contents": [{
                "parts": parts
            }],
            "tools": [{"google_search": {}}],
            "generationConfig": {
                "temperature": 0.1
            }
        }

        return _call_gemini_api(payload)
    except Exception as e:
        logger.error(f"Помилка аналізу зображень: {e}")
        return {}
