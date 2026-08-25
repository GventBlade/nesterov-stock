import io
from PIL import Image
from django.core.files.base import ContentFile
from django.db import models


class Location(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Код комірки")
    description = models.CharField(max_length=255, blank=True, verbose_name="Опис")

    def __str__(self):
        return self.code


class Manufacturer(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Виробник")

    def __str__(self):
        return self.name


def optimize_image(img_field):
    if img_field and hasattr(img_field, 'file'):
        try:
            img = Image.open(img_field)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            img.save(output, format='WEBP', quality=90, optimize=True)
            output.seek(0)

            filename = img_field.name.rsplit('.', 1)[0]
            return ContentFile(output.read(), name=f"{filename}.webp")
        except Exception:
            return img_field
    return img_field


class Product(models.Model):
    CURRENCY_CHOICES = [
        ('EUR', 'EUR (€)'),
        ('USD', 'USD ($)'),
        ('UAH', 'UAH (₴)'),
    ]

    barcode = models.CharField(max_length=100, db_index=True, verbose_name="Штрихкод / QR / DataMatrix")
    name = models.CharField(max_length=255, verbose_name="Назва товару")
    description = models.TextField(blank=True, default="", verbose_name="Опис / Додаткова інформація")

    # 🔹 Номенклатурна інформація (Виробник та Постачальник)
    manufacturer_info = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Номенклатурна інформація виробника (Артикул / Партномер)"
    )
    supplier_info = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Номенклатурна інформація постачальника"
    )

    # 🔹 Фото 1: Товар
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name="Фото товару")

    # 🔹 Фото 2: Коробка / Шильдик / Маркування
    package_image = models.ImageField(upload_to='products/labels/', null=True, blank=True,
                                      verbose_name="Фото шильдика / коробки")

    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.SET_NULL, null=True, blank=True,
                                     verbose_name="Виробник")

    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         verbose_name="Закупочна ціна")
    purchase_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='EUR',
                                         verbose_name="Валюта закупки")

    selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        verbose_name="Ціна продажу")
    selling_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='UAH',
                                        verbose_name="Валюта продажу")

    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="products",
                                 verbose_name="Комірка")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Кількість")

    parsed_extra_info = models.JSONField(default=dict, blank=True, verbose_name="Базові дані зі штрихкоду")
    ai_barcode_analysis = models.JSONField(default=dict, blank=True, verbose_name="ШІ: Аналіз штрихкоду/артикулу")
    ai_image_analysis = models.JSONField(default=dict, blank=True, verbose_name="ШІ: Візуальний аналіз фото")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.image:
            self.image = optimize_image(self.image)
        if self.package_image:
            self.package_image = optimize_image(self.package_image)

        if self.selling_price is None and self.purchase_price is not None:
            self.selling_price = self.purchase_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.barcode})"
