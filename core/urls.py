from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views
from django.contrib import admin
from core.forms import EmailAuthForm

admin.site.login_form = EmailAuthForm
admin.site.login_template = 'admin/login.html'
app_name = 'core'
urlpatterns = [
    path('register/', views.register, name='register'),
    path('confirm/', views.confirm_code, name='confirm_code'),
    path('login/', views.login_view, name='login'),
    path('', views.home, name='home'),
    path('logout/', LogoutView.as_view(next_page='core:login'), name='logout'),
    path('accounts/', views.accounts, name='accounts'),
    path('admin/', admin.site.urls),
    path('resend_code/', views.resend_confirmation_code, name='resend_code'),
    path('wallet_withdraw/', views.wallet_withdraw, name='withdraw_wallet'),
    path('cancel_sale/<int:sale_id>/', views.cancel_sale, name='cancel_sale')
]
