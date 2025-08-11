import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

# Ключ должен быть 16, 24 или 32 байта
AES_KEY = settings.MY_AES_KEY.encode()

def encrypt_cookie(plain_text: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(plain_text.encode(), AES.block_size))
    encrypted = base64.b64encode(cipher.iv + ct_bytes).decode()
    # Убедимся, что длина кратна 4
    pad_len = 4 - (len(encrypted) % 4)
    return encrypted + "=" * pad_len

def decrypt_cookie(enc_text: str) -> str:
    # Добавляем паддинг для корректной длины base64
    pad_len = 4 - (len(enc_text) % 4)
    enc_text += "=" * pad_len

    try:
        data = base64.b64decode(enc_text)
        iv = data[:16]
        ct = data[16:]
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(ct), AES.block_size).decode()
    except Exception as e:
        logger.error(f"Ошибка дешифровки куки: {str(e)}")
        return ''