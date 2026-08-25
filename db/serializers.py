import re
import json
from rest_framework import serializers
from .models import Product, Location, Manufacturer


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'code', 'description']


class ProductSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    location_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    image = serializers.ImageField(required=False, allow_null=True)
    package_image = serializers.ImageField(required=False, allow_null=True)
    manufacturer_info = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    supplier_info = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Product
        fields = [
            'id', 'barcode', 'name', 'description',
            'manufacturer_info', 'supplier_info',
            'image', 'package_image',
            'quantity', 'location', 'location_code',
            'purchase_price', 'purchase_currency',
            'selling_price', 'selling_currency',
            'parsed_extra_info', 'ai_barcode_analysis', 'ai_image_analysis',
            'created_at', 'updated_at'
        ]

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)

        for field_name in ['ai_barcode_analysis', 'ai_image_analysis']:
            val = data.get(field_name)
            if isinstance(val, str):
                try:
                    ret[field_name] = json.loads(val)
                except Exception:
                    ret[field_name] = {}
            elif isinstance(val, dict):
                ret[field_name] = val
        return ret

    def update(self, instance, validated_data):
        location_code = validated_data.pop('location_code', None)
        if location_code is not None:
            if location_code.strip():
                loc_obj, _ = Location.objects.get_or_create(code=location_code.strip().upper())
                instance.location = loc_obj
            else:
                instance.location = None
        return super().update(instance, validated_data)


class ScanInputSerializer(serializers.Serializer):
    barcode = serializers.CharField(required=True)
    location_code = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    manufacturer_info = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    supplier_info = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    image = serializers.ImageField(required=False, allow_null=True)
    package_image = serializers.ImageField(required=False, allow_null=True)
    quantity = serializers.IntegerField(default=1, min_value=1)

    purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    purchase_currency = serializers.CharField(max_length=3, default='EUR')

    selling_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    selling_currency = serializers.CharField(max_length=3, default='UAH')

    use_ai_barcode = serializers.BooleanField(default=False)
    use_ai_image = serializers.BooleanField(default=False)

    def validate_location_code(self, value):
        if value:
            code = value.strip().upper()
            if not re.match(r'^\d{1,3}-[A-Za-zА-Яа-я]\d{1,3}$', code):
                raise serializers.ValidationError("Формат комірки має бути 101-А01.")
            return code
        return value
