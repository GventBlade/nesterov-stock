from rest_framework import serializers
from .models import Product, Location, Manufacturer


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'code', 'description']


class ProductSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Product
        fields = [
            'id', 'barcode', 'name', 'description', 'image', 'quantity', 'location',
            'purchase_price', 'purchase_currency',
            'selling_price', 'selling_currency',
            'parsed_extra_info', 'created_at', 'updated_at'
        ]


class ScanInputSerializer(serializers.Serializer):
    barcode = serializers.CharField(required=True)
    location_code = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    image = serializers.ImageField(required=False, allow_null=True) # 📸
    quantity = serializers.IntegerField(default=1, min_value=1)

    purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    purchase_currency = serializers.CharField(max_length=3, default='EUR')

    selling_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    selling_currency = serializers.CharField(max_length=3, default='UAH')
