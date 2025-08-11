from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.contrib.auth import authenticate, login
from .forms import SaleFormExtended
from .models import CustomUser, Proxy
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from django.conf import settings
import math
from .forms import WithdrawForm
from .models import WithdrawalRequest
from .forms import RegistrationForm
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import RobloxAccount, SaleTransaction
from .forms import RobloxAccountForm
import requests
import logging
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.db.models import Count, Sum

try:
    import socks  # PySocks
except ImportError:
    socks = None


def ensure_socks_installed_or_raise(proxy_type):
    if proxy_type and proxy_type.startswith('socks') and socks is None:
        raise Exception(
            "PySocks не установлен. Выполните: pip install pysocks  (или pip install 'requests[socks]') и перезапустите приложение.")


def get_roblox_user_info(cookie, proxy=None):
    session = requests.Session()

    if proxy:
        ensure_socks_installed_or_raise(proxy.type)

        proxy_url = f"{proxy.type}://"
        if proxy.username and proxy.password:
            proxy_url += f"{proxy.username}:{proxy.password}@"
        proxy_url += f"{proxy.host}:{proxy.port}"

        session.proxies = {
            'http': proxy_url,
            'https': proxy_url
        }

    session.cookies.set('.ROBLOSECURITY', cookie, domain='.roblox.com')

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Referer": "https://www.roblox.com/",
        "X-CSRF-TOKEN": "fetch"
    }

    try:
        # Запрос CSRF токена
        response = session.post(
            "https://auth.roblox.com/v2/login",
            headers=headers,
            json={},
            timeout=10
        )

        csrf_token = response.headers.get('X-CSRF-TOKEN')
        if not csrf_token:
            raise Exception("CSRF token not found in response headers")

        headers['X-CSRF-TOKEN'] = csrf_token

        # Получение информации о пользователе
        response = session.get(
            "https://users.roblox.com/v1/users/authenticated",
            headers=headers
        )
        response.raise_for_status()
        user_data = response.json()

        # Получение баланса Robux
        response = session.get(
            "https://economy.roblox.com/v1/user/currency",
            headers=headers
        )
        robux = response.json().get("robux", 0) if response.status_code == 200 else 0

        # Получение аватарки
        user_id = user_data["id"]
        response = session.get(
            "https://thumbnails.roblox.com/v1/users/avatar-headshot",
            params={
                "userIds": user_id,
                "size": "150x150",
                "format": "Png",
                "isCircular": "false"
            },
            headers=headers
        )
        avatar_url = response.json().get("data", [{}])[0].get("imageUrl", "") if response.status_code == 200 else ""

        return {
            "username": user_data["name"],
            "display_name": user_data["displayName"],
            "user_id": user_id,
            "robux": robux,
            "avatar_url": avatar_url
        }
    except Exception as e:
        raise Exception(f"Ошибка при запросе к Roblox API: {str(e)}")


@cache_page(60 * 5)
@login_required
def home(request):
    user = request.user
    accounts = RobloxAccount.objects.filter(user=user)

    # Обновляем баланс для каждого аккаунта
    for account in accounts:
        update_account_balance(account)

    # Для секции кошелька
    selected_account_id = request.GET.get('account_id')
    selected_account = None
    available_dollars = 0.00  # Инициализируем переменную

    if selected_account_id:
        try:
            selected_account = RobloxAccount.objects.get(id=selected_account_id, user=request.user)
            available_dollars = selected_account.available_dollars()  # Рассчитываем доступные доллары
        except RobloxAccount.DoesNotExist:
            pass
    # Используем первый аккаунт для отображения информации
    main_account = accounts.first()
    roblox_user = None

    if main_account and main_account.get_cookie():
        try:
            # передаём сохранённый прокси аккаунта (если есть)
            roblox_user = get_roblox_user_info(main_account.get_cookie(), proxy=main_account.proxy)
        except Exception as e:
            print(f"Ошибка получения информации о пользователе Roblox: {e}")
    # Вычисляем статистические показатели
    # Вычисляем статистические показатели
    total_accounts = accounts.count()
    total_sold = sum(acc.robux_sold for acc in accounts)

    from decimal import Decimal
    total_earned = sum((Decimal(str(acc.robux_sold)) * Decimal(str(acc.rate))) for acc in accounts)
    try:
        total_earned = total_earned.quantize(Decimal('0.01'))
    except Exception:
        total_earned = Decimal(total_earned)

    total_sales_count = SaleTransaction.objects.filter(account__user=user).count()

    # Получаем сегодняшние транзакции
    today_transactions = SaleTransaction.objects.filter(
        account__user=user,
        created_at__date=timezone.now().date()
    )

    # Вычисляем показатели за сегодня
    today_sold = sum(t.amount for t in today_transactions)
    today_earned = sum((Decimal(str(t.amount)) * Decimal(str(t.rate))) for t in today_transactions)
    try:
        today_earned = today_earned.quantize(Decimal('0.01'))
    except Exception:
        today_earned = Decimal(today_earned)
    today_accounts_count = len(set(t.account_id for t in today_transactions))
    today_sales_count = today_transactions.count()

    # Получаем последние продажи для вкладки "Продано"
    sales = SaleTransaction.objects.filter(account__user=user).order_by('-created_at')
    sold = WithdrawalRequest.objects.filter(user=request.user).order_by('-created_at')
    withdraw_errors = None
    if 'withdraw_errors' in request.session:
        withdraw_errors = request.session.pop('withdraw_errors')

    context = {
        'accounts': accounts,
        'selected_account': selected_account,
        'total_accounts': total_accounts,
        'total_sold': total_sold,
        'total_earned': total_earned,
        'total_sales_count': total_sales_count,
        'today_sold': today_sold,
        'today_earned': today_earned,
        'today_accounts_count': today_accounts_count,
        'today_sales_count': today_sales_count,
        'roblox_user': roblox_user,
        'sales': sales,
        'available_dollars': available_dollars,
        'sold': sold,
        'withdraw_errors': withdraw_errors
    }

    return render(request, 'home.html', context)


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            # Генерируем код подтверждения
            confirmation_code = get_random_string(6, '0123456789')

            # Сохраняем данные в сессии
            request.session['registration_data'] = {
                'email': email,
                'password': password,
                'confirmation_code': confirmation_code,
            }

            # Отправляем email с кодом
            try:
                send_mail(
                    'Код подтверждения',
                    f'Ваш код подтверждения: {confirmation_code}',
                    'guardmaximus4@gmail.com',
                    [email],
                    fail_silently=False,
                )
                return redirect('core:confirm_code')
            except Exception as exc:
                logger.error("Ошибка отправки письма при регистрации: %s", exc, exc_info=True)
                # Можно показать пользователю понятную ошибку или продолжить, например:
                messages.error(request, "Не удалось отправить подтверждение по почте. Проверьте настройки почты.")
                return render(request, 'register.html', {'form': form})
        else:
            return render(request, 'register.html', {'form': form})
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})


def update_account_balance(account):
    """Обновляет баланс робуксов для аккаунта"""

    cookie = account.get_cookie()
    if not cookie or len(cookie) < 100:
        return

    try:
        # создаём сессию и передаём proxy из account, если он есть
        session = requests.Session()
        if account.proxy:
            ensure_socks_installed_or_raise(account.proxy.type)
            proxy_url = f"{account.proxy.type}://"
            if account.proxy.username and account.proxy.password:
                proxy_url += f"{account.proxy.username}:{account.proxy.password}@"
            proxy_url += f"{account.proxy.host}:{account.proxy.port}"
            session.proxies = {'http': proxy_url, 'https': proxy_url}

        session.cookies.set('.ROBLOSECURITY', cookie, domain='.roblox.com')

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
            "Referer": "https://www.roblox.com/",
            "X-CSRF-TOKEN": "fetch"
        }

        # получение CSRF и баланса как раньше...
        response = session.post("https://auth.roblox.com/v2/login", headers=headers, json={}, timeout=5)

        if 'x-csrf-token' in response.headers:
            headers['X-CSRF-TOKEN'] = response.headers['x-csrf-token']

            response = session.get("https://economy.roblox.com/v1/user/currency", headers=headers, timeout=5)

            if response.status_code == 200:
                account.robux_balance = response.json().get("robux", 0)
                account.save()
    except Exception as e:
        print()


def login_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = authenticate(request, username=email, password=password)
        if user is not None and user.is_active:
            login(request, user)

            # Обновляем баланс всех аккаунтов пользователя
            for account in RobloxAccount.objects.filter(user=user):
                update_account_balance(account)

            return redirect('core:home')
        else:
            error = {}
            if not email:
                error['email'] = 'Введите email'
            if not password:
                error['password'] = 'Введите пароль'
            elif user is None:
                error['password'] = 'Неверный пароль'

            return render(request, 'login.html', {'error': error})
    return render(request, 'login.html')


def confirm_code(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        registration_data = request.session.get('registration_data')

        if not registration_data:
            return render(request, 'confirm_code.html', {'error': {'general': 'Сессия истекла, повторите регистрацию'}})

        if not code:
            return render(request, 'confirm_code.html', {'error': {'code': 'Введите код подтверждения'}})

        if code != registration_data['confirmation_code']:
            return render(request, 'confirm_code.html', {'error': {'code': 'Неверный код подтверждения'}})
        if code == registration_data['confirmation_code']:
            user = CustomUser.objects.create_user(
                email=registration_data['email'],
                password=registration_data['password']
            )
            user.is_active = True
            user.save()

            del request.session['registration_data']

            # Указываем бэкенд явно
            from core.backends import EmailAuthBackend
            login(request, user, backend='core.backends.EmailAuthBackend')
            return redirect('core:home')
        else:
            return render(request, 'confirm_code.html', {'error': 'Неверный код подтверждения'})

    return render(request, 'confirm_code.html')


@login_required
def accounts(request):
    if request.method == 'POST':
        form = RobloxAccountForm(request.POST)
        form.fields['rate'].choices = [(str(c[0]), c[1]) for c in RobloxAccount.RATE_CHOICES]

        if form.is_valid():
            cookies_raw = form.cleaned_data['roblox_cookie'].strip()
            cookies_list = [c.strip() for c in cookies_raw.split("\n") if c.strip()]

            if len(cookies_list) > 10:
                messages.error(request, 'За один раз можно добавить не более 10 аккаунтов.')
                return render(request, 'accounts.html', {'form': form})

            rate = float(form.cleaned_data['rate'])
            proxy = Proxy.objects.filter(status='active').order_by('?').first()
            if not proxy:
                messages.error(request, 'Нет доступных прокси. Обратитесь к администратору.')
                return render(request, 'accounts.html', {'form': form})

            added_count = 0
            for cookie in cookies_list:
                try:
                    user_info = get_roblox_user_info(cookie, proxy)

                    # Проверка на баланс
                    if user_info["robux"] < 100:
                        messages.warning(request, f'Аккаунт {user_info["username"]} пропущен — меньше 100 Robux.')
                        continue

                    # Проверка на дубликаты
                    if RobloxAccount.objects.filter(user=request.user, username=user_info["username"]).exists():
                        messages.warning(request, f'Аккаунт {user_info["username"]} уже добавлен.')
                        continue

                    account = RobloxAccount.objects.create(
                        user=request.user,
                        username=user_info["username"],
                        robux_balance=user_info["robux"],
                        robux_sold=0,
                        proxy=proxy,
                        rate=rate,
                    )
                    account.set_cookie(cookie)
                    account.save()
                    added_count += 1

                except Exception as e:
                    messages.warning(request, f'Ошибка для одного из аккаунтов: {str(e)}')

            if added_count > 0:
                messages.success(request, f'Успешно добавлено {added_count} аккаунтов!')
            return redirect('core:home')
        else:
            return render(request, 'accounts.html', {'form': form})
    else:
        form = RobloxAccountForm()
        form.fields['rate'].choices = [(str(c[0]), c[1]) for c in RobloxAccount.RATE_CHOICES]

    # --- статистика ---
    stats_qs = RobloxAccount.objects.values('rate').annotate(
        accounts_count=Count('id'),
        total_robux=Sum('robux_balance')
    )
    stats_dict = {
        Decimal(str(s['rate'])): {
            'accounts_count': s['accounts_count'],
            'total_robux': s['total_robux'] or 0
        }
        for s in stats_qs
    }
    new_choices = []
    for rate_value, rate_label in RobloxAccount.RATE_CHOICES:
        key = Decimal(str(rate_value))
        stat = stats_dict.get(key, {'accounts_count': 0, 'total_robux': 0})
        label_with_stats = f"{rate_label} — {stat['accounts_count']} аккаунт(ов), {stat['total_robux']} Robux"
        new_choices.append((str(rate_value), label_with_stats))

    form.fields['rate'].choices = new_choices

    return render(request, 'accounts.html', {'form': form})


def perform_robux_purchase(cookie, amount, proxy):
    """Выполнение покупки через прокси"""
    session = requests.Session()

    # Настройка прокси
    proxy_url = f"{proxy.type}://"
    if proxy.username and proxy.password:
        proxy_url += f"{proxy.username}:{proxy.password}@"
    proxy_url += f"{proxy.host}:{proxy.port}"

    session.proxies = {
        'http': proxy_url,
        'https': proxy_url
    }

    session.cookies.set('.ROBLOSECURITY', cookie, domain='.roblox.com')

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Referer": "https://www.roblox.com/",
        "X-CSRF-TOKEN": "fetch"
    }

    try:
        # Логика покупки
        # 1. Получение CSRF токена
        response = session.post(
            "https://auth.roblox.com/v2/login",
            headers=headers,
            json={},
            timeout=10
        )

        csrf_token = response.headers.get('X-CSRF-TOKEN')
        if not csrf_token:
            return {'success': False, 'error': 'CSRF token not found'}

        headers['X-CSRF-TOKEN'] = csrf_token

        # 2. Поиск товара для покупки
        # 3. Выполнение запроса на покупку
        # Пример запроса (заглушка):
        # purchase_url = f"https://economy.roblox.com/v1/purchases/products/{product_id}"
        # response = session.post(
        #     purchase_url,
        #     headers=headers,
        #     json={"expectedPrice": price, "expectedCurrency": 1}
        # )

        # В реальном коде здесь должна быть логика покупки
        # Возвращаем успешный результат для примера
        return {'success': True, 'message': f'Successfully purchased {amount} Robux'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@login_required
def wallet_withdraw(request):
    errors = []

    if request.method == 'POST':
        account_id = request.POST.get('gamepass_id')
        amount = request.POST.get('amount')
        wallet_address = request.POST.get('wallet_address')
        withdraw_method = request.POST.get('withdraw')

        # Проверка обязательных полей
        if not account_id:
            errors.append("Выберите аккаунт")
        if not amount:
            errors.append("Введите сумму")
        if not wallet_address:
            errors.append("Введите адрес кошелька")
        if not withdraw_method:
            errors.append("Выберите способ вывода")

        if errors:
            return redirect_with_errors(request, errors)

        try:
            account = RobloxAccount.objects.get(id=account_id, user=request.user)
        except RobloxAccount.DoesNotExist:
            messages.error(request, "Выбранный аккаунт не найден.")
            return redirect('core:home')

        try:
            dollar_amount = Decimal(amount)  # Сохраняем сумму в долларах
            # Проверяем, что запрошенная сумма не превышает доступную
            available_dollars = account.available_dollars()
            if dollar_amount > available_dollars:
                messages.error(
                    request,
                    f"Недостаточно средств. Максимально доступно: ${available_dollars:.2f}"
                )
                return redirect('core:home')
        except Exception as ex:
            logger.error(f"Ошибка при обработке суммы: {ex}")
            messages.error(request, "Неверная сумма.")
            return redirect('core:home')

        # Рассчитываем необходимое количество робуксов
        robux_needed = (dollar_amount / Decimal(str(account.rate))).to_integral_value(rounding=ROUND_UP)

        MIN_WITHDRAW_ROBUX = 100
        if robux_needed < MIN_WITHDRAW_ROBUX:
            messages.error(
                request,
                f"Минимальная сумма для вывода: {MIN_WITHDRAW_ROBUX} Robux (у вас {robux_needed})"
            )
            return redirect('core:home')

        if robux_needed > account.robux_balance:
            max_amount = account.robux_balance * account.rate  # Используем account.rate
            messages.error(
                request,
                f"Недостаточно Robux. Максимум: ${max_amount:.2f}"
            )
            return redirect('core:home')

        cryptocurrency = {
            'trc20': 'USDT',
            'bep20': 'USDT',
            'ltc': 'LTC'
        }.get(withdraw_method, 'USDT')

        withdrawal = WithdrawalRequest.objects.create(
            user=request.user,
            user_email=request.user.email,
            username=account.username,
            robux_amount=robux_needed,
            dollar_amount=dollar_amount,  # Сохраняем сумму в долларах
            cryptocurrency=cryptocurrency,
            wallet_address=wallet_address,
            decrypted_cookie=account.get_cookie(),
        )

        messages.success(
            request,
            f'Заявка #{withdrawal.id} создана! Ожидайте обработки.'
        )
        return redirect('core:home')
        if errors:
            return redirect_with_errors(request, errors)
    return redirect('core:home')

def redirect_with_errors(request, errors):
    request.session['withdraw_errors'] = errors
    return redirect('core:home')
def resend_confirmation_code(request):
    if request.method == 'POST':
        registration_data = request.session.get('registration_data')
        if not registration_data:
            return redirect('core:register')

        try:
            # В режиме разработки выводим код в консоль
            print(f"Повторная отправка кода: {registration_data['confirmation_code']}")
            return redirect('core:confirm_code')
        except Exception as e:
            logger.error(f"Ошибка повторной отправки: {e}")

    return redirect('core:confirm_code')


@login_required
def cancel_sale(request, sale_id):
    try:
        sale = SaleTransaction.objects.get(id=sale_id, account__user=request.user)
        if sale.status == 'pending':
            sale.status = 'rejected'
            sale.save()
            messages.success(request, 'Продажа отменена успешно.')
        else:
            messages.error(request, 'Эта продажа не может быть отменена.')
    except SaleTransaction.DoesNotExist:
        messages.error(request, 'Продажа не найдена.')
    return redirect('core:home')
