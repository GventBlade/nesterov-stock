import io
from PIL import Image
from django.core.files.base import ContentFile
from django.db import models


class Location(models.Model):
    """Комірка / стелаж на складі (наприклад: 101-А1)"""
    code = models.CharField(max_length=50, unique=True, verbose_name="Код комірки")
    description = models.CharField(max_length=255, blank=True, verbose_name="Опис")

    def __str__(self):
        return self.code


class Manufacturer(models.Model):
    """Виробник (Ariston, Vaillant, Baxi тощо)"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Виробник")

    def __str__(self):
        return self.name


class Product(models.Model):
    """Товар / Запчастина"""
    CURRENCY_CHOICES = [
        ('EUR', 'EUR (€)'),
        ('USD', 'USD ($)'),
        ('UAH', 'UAH (₴)'),
    ]

    barcode = models.CharField(max_length=100, db_index=True, verbose_name="Штрихкод / EAN / DataMatrix")
    name = models.CharField(max_length=255, verbose_name="Назва товару")
    description = models.TextField(blank=True, default="", verbose_name="Опис / Додаткова інформація")

    # 📸 Опціональне фото товару
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name="Фото товару")

    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.SET_NULL, null=True, blank=True,
                                     verbose_name="Виробник")

    # Ціни та Валюти
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         verbose_name="Закупочна ціна")
    purchase_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='EUR',
                                         verbose_name="Валюта закупки")

    selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        verbose_name="Ціна для продажу")
    selling_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='UAH',
                                        verbose_name="Валюта продажу")

    # Локація та кількість
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="products",
                                 verbose_name="Комірка")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Кількість")

    # Додаткові атрибути
    release_year = models.PositiveIntegerField(null=True, blank=True, verbose_name="Рік випуску")
    parsed_extra_info = models.JSONField(default=dict, blank=True, verbose_name="Дані зі штрихкоду")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # 🎯 Автоматичне стиснення фото до 500x500px у WEBP
        if self.image and hasattr(self.image, 'file'):
            try:
                img = Image.open(self.image)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                # Обрізаємо/зменшуємо до 500x500 px
                img.thumbnail((500, 500))

                output = io.BytesIO()
                img.save(output, format='WEBP', quality=80, optimize=True)
                output.seek(0)

                filename = self.image.name.rsplit('.', 1)[0]
                self.image = ContentFile(output.read(), name=f"{filename}.webp")
            except Exception:
                pass

        if self.selling_price is None and self.purchase_price is not None:
            self.selling_price = self.purchase_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.barcode})"
