from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    scan_page_view,
    products_page_view,
    ScanStockView,
    ProductListView,
    ProductDetailView
)

urlpatterns = [
    # Сторінка сканера
    path('', scan_page_view, name='scan_page'),

    # Окрема сторінка бази товарів
    path('products/', products_page_view, name='products_page'),

    # Авторизація JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # REST API ендпоінти
    path('api/scan/', ScanStockView.as_view(), name='api_scan_stock'),
    path('api/products/', ProductListView.as_view(), name='api_product_list'),
    path('api/products/<int:pk>/', ProductDetailView.as_view(), name='api_product_detail'),
]
