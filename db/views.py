from django.shortcuts import render
from django.db.models import F
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Product, Location
from .utils import parse_barcode_extra_info
from .serializers import ProductSerializer, ScanInputSerializer


def scan_page_view(request):
    return render(request, 'scan.html')


def products_page_view(request):
    return render(request, 'products_list.html')


class ScanStockView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser] # Підтримка файлів/фото

    def post(self, request):
        serializer = ScanInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        barcode = str(data['barcode']).strip()
        location_code = data.get('location_code')
        custom_name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        image_file = data.get('image') # 📸 Фото з Multipart
        quantity = data.get('quantity', 1)

        purchase_price = data.get('purchase_price')
        purchase_currency = data.get('purchase_currency', 'EUR')

        selling_price = data.get('selling_price')
        selling_currency = data.get('selling_currency', 'UAH')

        location_obj = None
        if location_code:
            location_obj, _ = Location.objects.get_or_create(code=str(location_code).strip().upper())

        parsed_info = parse_barcode_extra_info(barcode)
        product = Product.objects.filter(barcode=barcode).first()

        if product:
            if custom_name: product.name = custom_name
            if description: product.description = description
            if location_obj: product.location = location_obj
            if image_file: product.image = image_file # Оновлюємо/замінюємо фото
            if purchase_price is not None:
                product.purchase_price = purchase_price
                product.purchase_currency = purchase_currency
            if selling_price is not None:
                product.selling_price = selling_price
                product.selling_currency = selling_currency

            product.parsed_extra_info = parsed_info
            product.quantity = F('quantity') + quantity
            product.save()
            product.refresh_from_db()
            created = False
        else:
            product = Product.objects.create(
                barcode=barcode,
                name=custom_name or f"Товар {barcode}",
                description=description,
                image=image_file,
                quantity=quantity,
                location=location_obj,
                purchase_price=purchase_price,
                purchase_currency=purchase_currency,
                selling_price=selling_price,
                selling_currency=selling_currency,
                parsed_extra_info=parsed_info,
                release_year=parsed_info.get("parsed_attributes", {}).get("extracted_year")
            )
            created = True

        return Response(ProductSerializer(product).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductListView(generics.ListCreateAPIView):
    queryset = Product.objects.select_related('location', 'manufacturer').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [OrderingFilter, SearchFilter]
    search_fields = ['name', 'barcode', 'description', 'location__code']
    ordering_fields = ['name', 'created_at', 'quantity']
    ordering = ['-created_at']


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.select_related('location', 'manufacturer').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
