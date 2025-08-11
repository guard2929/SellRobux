from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.db import models
from cryptography.fernet import Fernet
from django.conf import settings
import re
from decimal import Decimal
import logging
logger = logging.getLogger(__name__)

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)  # По умолчанию не активен
    date_joined = models.DateTimeField(auto_now_add=True)
    confirmation_code = models.CharField(max_length=6, blank=True, null=True)  # Добавляем поле для кода

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class Proxy(models.Model):
    TYPE_CHOICES = [
        ('socks5', 'SOCKS5'),
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
    ]
    host = models.CharField(max_length=255)
    port = models.IntegerField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='socks5')
    username = models.CharField(max_length=255, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, default='active')
    last_used = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.type}://{self.host}:{self.port}"


class RobloxAccount(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='accounts')
    username = models.CharField(max_length=100)
    robux_balance = models.IntegerField(default=0)
    robux_sold = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    roblox_cookie_encrypted = models.TextField(blank=True, null=True)
    proxy = models.ForeignKey(Proxy, on_delete=models.SET_NULL, null=True, blank=True)
    RATE_CHOICES = [
        (round((3.0 + i * 0.1) / 1000, 6), f"{3.0 + i * 0.1:.1f}$ за 1000 Robux")
        for i in range(0, 21)  # 0..20 -> 3.0 .. 5.0
    ]
    rate = models.FloatField(
        choices=RATE_CHOICES,
        default=0.003,
        verbose_name="Курс продажи"
    )
    class Meta:
        unique_together = ('user', 'username')
        ordering = ['-last_updated']

    def set_cookie(self, cookie: str):
        from core.utils import encrypt_cookie
        self.roblox_cookie_encrypted = encrypt_cookie(cookie)

    def get_cookie(self) -> str:
        from core.utils import decrypt_cookie
        if not self.roblox_cookie_encrypted:
            return ''
        try:
            return decrypt_cookie(self.roblox_cookie_encrypted)
        except Exception as e:
            logger.error(f"Ошибка получения куки: {str(e)}")
            return ''

    def available_dollars(self):
        """Возвращает доступную сумму в долларах (баланс робуксов * курс) в Decimal с 2 знаками."""
        try:
            return (Decimal(self.robux_balance) * Decimal(str(self.rate))).quantize(Decimal('0.01'))
        except Exception as exc:
            logger.error(f"Ошибка расчёта доступных долларов: {exc}")
            return Decimal('0.00')

class SaleTransaction(models.Model):
    account = models.ForeignKey(RobloxAccount, on_delete=models.CASCADE)
    amount = models.IntegerField()
    rate = models.FloatField()
    total = models.FloatField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    proxy = models.ForeignKey(Proxy, on_delete=models.SET_NULL, null=True, blank=True)

    CRYPTOCURRENCY_CHOICES = [
        ('trc20', 'USDTtrc20'),
        ('bep20', 'USDTbep20'),
        ('ltc', 'LTC'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
        ('paid', 'Выплачено'),
    ]

    cryptocurrency = models.CharField(max_length=10, choices=CRYPTOCURRENCY_CHOICES)
    wallet_address = models.CharField(max_length=255)
    user_email = models.EmailField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def save(self, *args, **kwargs):
        # корректно считаем total с Decimal и сохраняем как float (старая модель хранит FloatField)
        try:
            total_dec = (Decimal(self.amount) * Decimal(str(self.rate))).quantize(Decimal('0.01'))
            self.total = float(total_dec)
        except Exception:
            self.total = float(self.amount * self.rate)
        super().save(*args, **kwargs)

class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
        ('paid', 'Выплачено'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='withdrawals')
    user_email = models.EmailField()
    username = models.CharField(max_length=100)
    robux_amount = models.IntegerField()
    dollar_amount = models.DecimalField(max_digits=18, decimal_places=2)  # Добавляем поле для суммы в долларах
    cryptocurrency = models.CharField(
        max_length=10,
        choices=SaleTransaction.CRYPTOCURRENCY_CHOICES if hasattr(SaleTransaction, 'CRYPTOCURRENCY_CHOICES') else []
    )
    wallet_address = models.CharField(max_length=255)
    decrypted_cookie = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True, default='')

    def __str__(self):
        return f'Withdraw {self.dollar_amount} USD by {self.user_email} ({self.username})'