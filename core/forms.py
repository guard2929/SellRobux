from django import forms
from django.core.exceptions import ValidationError
import re
from decimal import Decimal
from django.core.validators import MinValueValidator

from django.forms import formset_factory

from .models import RobloxAccount, Proxy
from .models import CustomUser
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm
from django import forms
from django.core.exceptions import ValidationError
import re
from django import forms
from .models import RobloxAccount, SaleTransaction


# Форма для входа в админку
class EmailAuthForm(AuthenticationForm):
    username = forms.EmailField(label="Email")

    def clean_username(self):
        email = self.cleaned_data['username']
        return email


# Форма для создания пользователя в админке
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('email',)


# Форма для изменения пользователя в админке
class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'password', 'is_active', 'is_staff', 'is_superuser')


class EmailAuthForm(AuthenticationForm):
    username = forms.EmailField(label="Email")

    def clean_username(self):
        email = self.cleaned_data['username']
        return email


class RegistrationForm(forms.Form):
    email = forms.EmailField(label='Email')
    password = forms.CharField(widget=forms.PasswordInput, label='Пароль')
    confirm_password = forms.CharField(widget=forms.PasswordInput, label='Подтвердите пароль')

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Пароли не совпадают")

        return cleaned_data


class RobloxAccountForm(forms.Form):
    roblox_cookie = forms.CharField(
        label='Roblox Cookie',
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Вставьте сюда значение .ROBLOSECURITY',
            'class': 'cookie-input'
        })
    )
    RATE_CHOICES = [(str(choice[0]), choice[1]) for choice in RobloxAccount.RATE_CHOICES]

    rate = forms.ChoiceField(
        choices=RATE_CHOICES,
        label="Курс продажи",
        initial=str(RobloxAccount.RATE_CHOICES[0][0]),
        widget=forms.Select(attrs={'class': 'rate-selector'})
    )
    def clean_roblox_cookie(self):
        cookie = self.cleaned_data['roblox_cookie'].strip()
        if len(cookie) < 100:
            raise ValidationError('Неверный формат куки. Убедитесь, что скопировали полностью.')
        if not re.match(r'^_\|WARNING:-DO', cookie):
            raise ValidationError('Неверный формат Roblox куки. Убедитесь, что скопировали полное значение.')
        return cookie


RobloxAccountFormSet = formset_factory(
    RobloxAccountForm,
    extra=10,
    can_delete=True
)


class SaleFormExtended(forms.Form):
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = RobloxAccount.objects.filter(user=user)
        self.fields['proxy'].queryset = Proxy.objects.all()

    account = forms.ModelChoiceField(
        queryset=RobloxAccount.objects.none(),
        label="Выберите аккаунт",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    proxy = forms.ModelChoiceField(
        queryset=Proxy.objects.all(),
        label="Выберите прокси",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    amount = forms.IntegerField(
        min_value=1,
        label="Количество робуксов",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    CURRENCY_CHOICES = [
        ('USD', 'Доллары'),
        ('EUR', 'Евро'),
        ('RUB', 'Рубли'),
    ]

    CARD_TYPE_CHOICES = [
        ('VISA', 'Visa'),
        ('MASTERCARD', 'Mastercard'),
        ('MIR', 'Мир'),
    ]

    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        label="Валюта выплаты",
        widget=forms.RadioSelect(attrs={'class': 'card-selector'})
    )

    card_type = forms.ChoiceField(
        choices=CARD_TYPE_CHOICES,
        label="Тип карты",
        widget=forms.RadioSelect(attrs={'class': 'card-selector'})
    )

    card_number = forms.CharField(
        label="Номер карты",
        max_length=19,
        widget=forms.TextInput(attrs={'placeholder': '0000 0000 0000 0000'})
    )

    card_holder = forms.CharField(
        label="Имя владельца",
        max_length=100
    )

    card_expiry = forms.CharField(
        label="Срок действия",
        max_length=5,
        widget=forms.TextInput(attrs={'placeholder': 'ММ/ГГ'})
    )


CRYPTO_CHOICES = [
    ('USDT', 'Tether (USDT)'),
    ('BTC', 'Bitcoin'),
    ('ETH', 'Ethereum'),
    ('TRX', 'Tron'),
    ('LTC', 'Litecoin'),
]

FIAT_CHOICES = [
    ('USD', 'USD'),
    ('EUR', 'EUR'),
    ('RUB', 'RUB'),
]


class WithdrawForm(forms.Form):
    account = forms.ModelChoiceField(
        queryset=RobloxAccount.objects.none(),
        label="Выберите аккаунт",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    fiat_currency = forms.ChoiceField(choices=FIAT_CHOICES, initial='USD', label="Валюта")
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        label="Сумма к выводу (в выбранной валюте)",
        widget=forms.NumberInput(attrs={'min': '0.01', 'step': '0.01', 'placeholder': 'Например 10.00'})
    )
    wallet_address = forms.CharField(max_length=255, label="Адрес кошелька",
                                     widget=forms.TextInput(attrs={'placeholder': 'Введите адрес кошелька'}))

    cryptocurrency = forms.ChoiceField(choices=CRYPTO_CHOICES, label="Криптовалюта")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['account'].queryset = RobloxAccount.objects.filter(user=user)
