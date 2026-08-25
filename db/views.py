from django.shortcuts import render, redirect
from django.db.models import F
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Product, Location
from .utils import parse_barcode_extra_info
from .ai_services import analyze_barcode_with_ai, analyze_product_images_with_ai
from .serializers import ProductSerializer, ScanInputSerializer


@login_required(login_url='/login/')
def scan_page_view(request):
    return render(request, 'scan.html')


@login_required(login_url='/login/')
def products_page_view(request):
    return render(request, 'products_list.html')


class ScanStockView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = ScanInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        barcode = str(data['barcode']).strip()
        location_code = data.get('location_code')
        user_name = data.get('name', '').strip()
        user_description = data.get('description', '').strip()
        manufacturer_info = data.get('manufacturer_info')
        supplier_info = data.get('supplier_info')
        image_file = data.get('image')
        package_image_file = data.get('package_image')
        quantity = data.get('quantity', 1)

        purchase_price = data.get('purchase_price')
        purchase_currency = data.get('purchase_currency', 'EUR')
        selling_price = data.get('selling_price')
        selling_currency = data.get('selling_currency', 'UAH')

        use_ai_barcode = data.get('use_ai_barcode', False)
        use_ai_image = data.get('use_ai_image', False)

        location_obj = None
        if location_code:
            location_obj, _ = Location.objects.get_or_create(code=str(location_code).strip().upper())

        parsed_info = parse_barcode_extra_info(barcode) or {}

        ai_barcode_data = {}
        if use_ai_barcode and barcode:
            ai_barcode_data = analyze_barcode_with_ai(barcode) or {}

        ai_image_data = {}
        if use_ai_image and (image_file or package_image_file):
            ai_image_data = analyze_product_images_with_ai(image_file, package_image_file) or {}

        # Формування тексту для поля опису, якщо воно порожнє
        generated_desc_blocks = []
        if ai_image_data:
            img_name = ai_image_data.get("probable_name", "")
            img_brand = ai_image_data.get("brand", "")
            img_art = ai_image_data.get("article", "")
            img_rec = ai_image_data.get("recognized_text", "")
            img_models = ", ".join(ai_image_data.get("compatible_models", []))
            img_desc = ai_image_data.get("description", "")

            block = f"【ШИЛЬДИК / ФОТО】\nНазва: {img_name}\nБренд: {img_brand} | Арт: {img_art}"
            if img_models:
                block += f"\nСумісні котли: {img_models}"
            if img_rec:
                block += f"\nШильдик: {img_rec}"
            if img_desc:
                block += f"\n{img_desc}"
            generated_desc_blocks.append(block)

        if ai_barcode_data:
            bc_name = ai_barcode_data.get("probable_name", "")
            bc_brand = ai_barcode_data.get("brand", "")
            bc_art = ai_barcode_data.get("article", "")
            bc_models = ", ".join(ai_barcode_data.get("compatible_models", []))
            bc_desc = ai_barcode_data.get("description", "")

            block = f"【ШТРИХКОД】\nВизначено: {bc_name}\nБренд: {bc_brand} | Арт: {bc_art}"
            if bc_models:
                block += f"\nСумісність: {bc_models}"
            if bc_desc:
                block += f"\n{bc_desc}"
            generated_desc_blocks.append(block)

        final_description = user_description or "\n\n".join(generated_desc_blocks)

        # Автозаповнення артикулу виробника з ШІ, якщо поле не заповнено вручну
        if not manufacturer_info:
            manufacturer_info = ai_image_data.get("article") or ai_barcode_data.get("article") or None

        product = Product.objects.filter(barcode=barcode).first()

        if product:
            if user_name:
                product.name = user_name

            if user_description:
                product.description = user_description
            elif not product.description and final_description:
                product.description = final_description

            if manufacturer_info:
                product.manufacturer_info = manufacturer_info
            if supplier_info:
                product.supplier_info = supplier_info

            if location_obj:
                product.location = location_obj
            if image_file:
                product.image = image_file
            if package_image_file:
                product.package_image = package_image_file
            if purchase_price is not None:
                product.purchase_price = purchase_price
                product.purchase_currency = purchase_currency
            if selling_price is not None:
                product.selling_price = selling_price
                product.selling_currency = selling_currency

            product.parsed_extra_info = parsed_info or {}

            if ai_barcode_data:
                product.ai_barcode_analysis = ai_barcode_data
            if ai_image_data:
                product.ai_image_analysis = ai_image_data

            product.quantity = F('quantity') + quantity
            product.save()
            product.refresh_from_db()
            created = False
        else:
            final_name = user_name if user_name else (
                ai_image_data.get("probable_name")
                or ai_barcode_data.get("probable_name")
                or f"Товар {barcode}"
            )
            product = Product.objects.create(
                barcode=barcode,
                name=final_name,
                description=final_description,
                manufacturer_info=manufacturer_info,
                supplier_info=supplier_info,
                image=image_file,
                package_image=package_image_file,
                quantity=quantity,
                location=location_obj,
                purchase_price=purchase_price,
                purchase_currency=purchase_currency,
                selling_price=selling_price,
                selling_currency=selling_currency,
                parsed_extra_info=parsed_info if parsed_info else {},
                ai_barcode_analysis=ai_barcode_data if ai_barcode_data else {},
                ai_image_analysis=ai_image_data if ai_image_data else {}
            )
            created = True

        return Response(ProductSerializer(product).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductListView(generics.ListCreateAPIView):
    queryset = Product.objects.select_related('location', 'manufacturer').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [OrderingFilter, SearchFilter]
    search_fields = [
        'name', 'barcode', 'description', 'location__code',
        'manufacturer_info', 'supplier_info'
    ]
    ordering_fields = ['name', 'created_at', 'quantity']
    ordering = ['-created_at']


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.select_related('location', 'manufacturer').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def put(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


def custom_logout_view(request):
    logout(request)
    return redirect('login')
