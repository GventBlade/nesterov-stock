from django.urls import path
from django.contrib.auth import views as auth_views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    scan_page_view,
    products_page_view,
    ScanStockView,
    ProductListView,
    ProductDetailView,
    custom_logout_view
)

urlpatterns = [
    # UI сторінки
    path('', scan_page_view, name='scan_page'),
    path('products/', products_page_view, name='products_page'),

    # Авторизація та Вихід
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', custom_logout_view, name='logout'),  # ✅ Залишаємо тільки вашу функцію

    # JWT токени
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # REST API CRUD
    path('api/scan/', ScanStockView.as_view(), name='api_scan_stock'),
    path('api/products/', ProductListView.as_view(), name='api_product_list'),
    path('api/products/<int:pk>/', ProductDetailView.as_view(), name='api_product_detail'),
]
