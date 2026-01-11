from fastapi_mail import FastMail, ConnectionConfig
from app.core.config import settings

def get_mail_client() -> FastMail:
    conf = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,       # harus sama dengan Gmail
        MAIL_PASSWORD=settings.MAIL_PASSWORD,       # App Password 16 char, tanpa spasi
        MAIL_FROM=settings.MAIL_FROM,               # sama dengan akun Gmail
        MAIL_SERVER=settings.MAIL_SERVER,           # smtp.gmail.com
        MAIL_PORT=settings.MAIL_PORT,               # 587 untuk TLS
        MAIL_STARTTLS=settings.MAIL_STARTTLS,       # True
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,         # False
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True
    )
    return FastMail(conf)
