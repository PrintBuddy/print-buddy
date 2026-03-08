from fastapi_mail import FastMail, ConnectionConfig, MessageSchema, MessageType, NameEmail
from email.mime.image import MIMEImage
import os

from ..schemas.user import UserBase
from .config import settings


config = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,  # type: ignore
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)


mail = FastMail(
    config=config
)


async def send_reset_email(user: UserBase, token: str) -> None:
    reset_link = f"{settings.PWD_RESET_URL}?token={token}"

    recipient_name = f"{user.name} {user.surname}"
    email_to = NameEmail(name=recipient_name, email=user.email)

    subject = "Password Reset Request"

    body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f6f8fa; margin: 0; padding: 0;">
            <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f6f8fa;">
                <tr>
                    <td align="center" style="padding: 40px 0;">
                        <table role="presentation" style="width: 100%; max-width: 500px; background: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <tr>
                                <td style="padding: 30px; text-align: center;">
                                    <img src="cid:logo" alt="Logo" style="width: 120px; margin-bottom: 20px;" />
                                    <h2 style="color: #333333; text-align: center;">Password Reset Request</h2>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 0 30px 30px 30px;">
                                    <p style="color: #555555; font-size: 15px;">
                                        Hello <strong>{user.name}</strong>,
                                    </p>
                                    <p style="color: #555555; font-size: 15px; line-height: 1.6;">
                                        We received a request to reset your password. If this was you, please click the button below to set a new password. 
                                        This link will expire in {settings.PWD_RESET_TIME_MIN} minute{"" if settings.PWD_RESET_TIME_MIN == 1 else "s"} for security reasons.
                                    </p>

                                    <div style="text-align: center; margin: 30px 0;">
                                        <a href="{reset_link}" 
                                           style="background-color: #007bff; color: white; text-decoration: none; 
                                                  padding: 12px 20px; border-radius: 6px; display: inline-block; font-weight: bold;">
                                            Reset Password
                                        </a>
                                    </div>

                                    <p style="color: #555555; font-size: 14px; line-height: 1.6;">
                                        If you didn’t request this, you can safely ignore this email.
                                    </p>

                                    <p style="color: #999999; font-size: 12px; text-align: center; margin-top: 40px;">
                                        — The {settings.PROJECT_NAME} Team
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
    </html>
    """


    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(BASE_DIR, "..", "assets", "logo.png")


    msg = MessageSchema(
        subject=subject,
        recipients=[email_to],
        body=body,
        subtype=MessageType.html,
        attachments=[
            {
                "file": logo_path,
                "headers": {
                    "Content-ID": "<logo>",
                    "Content-Disposition": "inline; filename=\"logo.png\""
                },
                "mime_type": "image",
                "mime_subtype": "png"
            }
        ]
    )

    await mail.send_message(msg)


async def send_toner_alert_email(recipients: list[str], alerts: list[dict]) -> None:
    """
    Send a low-toner warning email to all admin recipients.
    alerts: [{"printer_name": str, "markers": [{"name", "level", "low_level", ...}]}]
    """
    if not recipients or not alerts:
        return

    printer_rows = ""
    for alert in alerts:
        marker_rows = "".join(
            f"""
            <tr>
                <td style="padding: 4px 8px; color: #555555;">{m['name']}</td>
                <td style="padding: 4px 8px; color: #cc0000; font-weight: bold;">{m['level']}%</td>
                <td style="padding: 4px 8px; color: #888888;">{m['low_level']}%</td>
            </tr>"""
            for m in alert["markers"]
        )
        printer_rows += f"""
        <tr>
            <td colspan="3" style="padding: 10px 8px 4px 8px;">
                <strong style="color: #333333; font-size: 15px;">🖨 {alert['printer_name']}</strong>
            </td>
        </tr>
        {marker_rows}
        <tr><td colspan="3" style="padding: 6px;"></td></tr>"""

    body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f6f8fa; margin: 0; padding: 0;">
            <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f6f8fa;">
                <tr>
                    <td align="center" style="padding: 40px 0;">
                        <table role="presentation" style="width: 100%; max-width: 560px; background: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <tr>
                                <td style="padding: 30px; text-align: center;">
                                    <img src="cid:logo" alt="Logo" style="width: 120px; margin-bottom: 20px;" />
                                    <h2 style="color: #cc0000; text-align: center; margin: 0;">⚠ Low Toner Alert</h2>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 0 30px 30px 30px;">
                                    <p style="color: #555555; font-size: 15px;">
                                        The following printer(s) have one or more toner cartridges below the low-level threshold.
                                        Please replace the affected cartridges as soon as possible.
                                    </p>
                                    <table style="width: 100%; border-collapse: collapse; margin-top: 8px;">
                                        <thead>
                                            <tr style="background: #f0f0f0;">
                                                <th style="padding: 6px 8px; text-align: left; color: #333; font-size: 13px;">Cartridge</th>
                                                <th style="padding: 6px 8px; text-align: left; color: #333; font-size: 13px;">Level</th>
                                                <th style="padding: 6px 8px; text-align: left; color: #333; font-size: 13px;">Threshold</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {printer_rows}
                                        </tbody>
                                    </table>
                                    <p style="color: #999999; font-size: 12px; text-align: center; margin-top: 40px;">
                                        — The {settings.PROJECT_NAME} Team
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
    </html>
    """

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(BASE_DIR, "..", "assets", "logo.png")

    msg = MessageSchema(
        subject=f"[{settings.PROJECT_NAME}] Low Toner Alert",
        recipients=recipients,  # type: ignore
        body=body,
        subtype=MessageType.html,
        attachments=[
            {
                "file": logo_path,
                "headers": {
                    "Content-ID": "<logo>",
                    "Content-Disposition": "inline; filename=\"logo.png\""
                },
                "mime_type": "image",
                "mime_subtype": "png"
            }
        ]
    )

    await mail.send_message(msg)
