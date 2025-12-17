from typing import List

from fastapi_mail import (
    ConnectionConfig,
    FastMail,
    MessageSchema,
    MessageType,
    NameEmail,
)

from ..config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    VALIDATE_CERTS=settings.VALIDATE_CERTS,
)


class EmailService:
    @staticmethod
    async def send_email(
        subject: str,
        recipients: List[NameEmail],
        body: str,
        subtype=MessageType.plain,
    ):
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            body=body,
            subtype=subtype,
        )
        fm = FastMail(conf)

        if settings.ENVIRONMENT == "dev":
            print("[DEBUG]", body)
        else:
            await fm.send_message(message)
