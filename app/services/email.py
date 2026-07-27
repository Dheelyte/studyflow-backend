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
    async def send_welcome_email(user):
        template_body = {
            "name": user.first_name or "",
            "dashboard_url": settings.FRONTEND_DASHBOARD_URL
        }
        
        # Ensure we point to the correct template folder
        # We need to manually set the template folder here or globally
        conf.TEMPLATE_FOLDER = settings.TEMPLATE_FOLDER
        
        message = MessageSchema(
            subject=f"Welcome to {settings.APP_NAME}!",
            recipients=[user.email],
            template_body=template_body,
            subtype=MessageType.html,
        )
        
        fm = FastMail(conf)
        
        if settings.ENVIRONMENT == "dev":
            # In dev, we can print or still send if configured. 
            # For template rendering in dev without sending, we might need a different approach,
            # but FastMail.send_message handles it.
            # If we want to see the HTML in logs:
            print(f"[DEBUG] Sending Welcome Email to {user.email}")
            # fm.send_message will attempt to connect to SMTP. 
            # If we don't have SMTP in dev, we should skip or mock.
            if settings.MAIL_SERVER == "test":
                print("[DEBUG] Mock Welcome Email Sent")
            return

        await fm.send_message(message, template_name="welcome_email.html")

    @staticmethod
    async def send_password_reset_email(user, code: str):
        template_body = {
            "name": user.first_name or "",
            "code": code,
            "expires_minutes": settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES,
        }

        conf.TEMPLATE_FOLDER = settings.TEMPLATE_FOLDER

        message = MessageSchema(
            subject=f"Reset your {settings.APP_NAME} password",
            recipients=[user.email],
            template_body=template_body,
            subtype=MessageType.html,
        )

        fm = FastMail(conf)

        if settings.ENVIRONMENT == "dev":
            print(f"[DEBUG] Sending Password Reset Email to {user.email} (code: {code})")
            if settings.MAIL_SERVER == "test":
                print("[DEBUG] Mock Password Reset Email Sent")
            return

        await fm.send_message(message, template_name="password_reset_email.html")
