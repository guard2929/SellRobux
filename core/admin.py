from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.utils.html import format_html

from .models import CustomUser, Proxy, RobloxAccount, SaleTransaction, WithdrawalRequest
from .forms import EmailAuthForm, CustomUserCreationForm, CustomUserChangeForm

# Убедимся, что модель CustomUser не зарегистрирована дважды
if admin.site.is_registered(CustomUser):
    admin.site.unregister(CustomUser)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    list_display = ('email', 'is_staff', 'is_superuser', 'is_active')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )
    search_fields = ('email',)
    filter_horizontal = ()


@admin.register(Proxy)
class ProxyAdmin(admin.ModelAdmin):
    list_display = ('host', 'port', 'type', 'status', )
    list_filter = ('type', 'status')
    search_fields = ('host',)
    fieldsets = (
        (None, {
            'fields': ('host', 'port', 'type')
        }),
        ('Authentication', {
            'fields': ('username', 'password'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', )
        }),
    )


@admin.register(RobloxAccount)
class RobloxAccountAdmin(admin.ModelAdmin):
    list_display = ('username', 'user_email', 'robux_balance', 'robux_sold', 'last_updated','rate')
    ordering = ['-rate']
    list_filter = ('last_updated',)
    search_fields = ('username', 'user__email')
    readonly_fields = ('last_updated', 'robux_balance', 'robux_sold')
    fieldsets = (
        (None, {
            'fields': ('user', 'username')
        }),
        ('Balance', {
            'fields': ('robux_balance', 'robux_sold', 'rate')
        }),
        ('Security', {
            'fields': ('proxy',),
            'description': 'Security settings for account operations'
        }),
        ('Timestamps', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = 'User Email'

# Установим кастомную форму для входа в админку
admin.site.login_form = EmailAuthForm


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    # Поля для отображения в списке объектов
    list_display = (
        'id',
        'user_email',
        'username',
        'robux_amount',
        'get_cryptocurrency_display',  # Показывает читаемое значение cryptocurrency
        'dollar_amount',
        'wallet_address' ,  # Сокращённый кошелёк
        'status',
        'created_at',
        'processed_at',
        'admin_actions',
        'decrypted_cookie'
    )

    # Фильтры справа
    list_filter = ('status', 'cryptocurrency', 'created_at')
    # Поиск по полям
    search_fields = ('user_email', 'username', 'wallet_address')

    # Поля только для чтения в детальном просмотре
    readonly_fields = ('created_at', 'processed_at', 'user_email', 'username', 'robux_amount')

    # Группировка полей в детальном просмотре
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'user',
                'user_email',
                'username',
                'robux_amount',
            )
        }),
        ('Детали выплаты', {
            'fields': (
                'cryptocurrency',
                'dollar_amount',
                'wallet_address',
                'decrypted_cookie',
            )
        }),
        ('Статус', {
            'fields': (
                'status',
                'admin_note',
                'created_at',
                'processed_at',
            )
        }),
    )

    # Кастомные методы для отображения



    def admin_actions(self, obj):
        """Кнопки для быстрой смены статуса."""
        buttons = []
        if obj.status != 'approved':
            buttons.append(
                f'<a href="approve/{obj.id}/" style="background:green;padding:5px;color:white;">✓ Одобрить</a>'
            )
        if obj.status != 'rejected':
            buttons.append(
                f'<a href="reject/{obj.id}/" style="background:red;padding:5px;color:white;">✗ Отклонить</a>'
            )
        return format_html(' '.join(buttons))

    admin_actions.short_description = 'Действия'
    admin_actions.allow_tags = True  # Разрешает HTML-теги

    # Добавляем кастомные действия в список
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('approve/<int:pk>/', self.approve),
            path('reject/<int:pk>/', self.reject),
        ]
        return custom_urls + urls

    # Логика для одобрения
    def approve(self, request, pk):
        obj = WithdrawalRequest.objects.get(pk=pk)
        obj.status = 'approved'
        obj.save()
        return HttpResponseRedirect("../")

        # Логика для отклонения

    def reject(self, request, pk):
        obj = WithdrawalRequest.objects.get(pk=pk)
        obj.status = 'rejected'
        obj.save()
          # Возвращаем пользователя на страницу администрирования
        return HttpResponseRedirect("../")

