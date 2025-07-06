from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template import Template, Context
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """A service for sending branded HTML emails."""

    PRIMARY_COLOR = "#0070EA"
    FONT_FAMILY = "'Open Sans', sans-serif"
    COMPANY_NAME = "FoloMoney"
    SUPPORT_EMAIL = "care@folomoney.com"

    @staticmethod
    def _send_branded_email(recipient_email, subject, heading, body_html, code=None):
        """Helper to send a branded HTML email using EmailMultiAlternatives for better SES support."""
        
        try:
            context_data = {
                'heading': heading,
                'body_html': body_html,
                'primary_color': EmailService.PRIMARY_COLOR,
                'font_family': EmailService.FONT_FAMILY,
                'company_name': EmailService.COMPANY_NAME,
                'support_email': EmailService.SUPPORT_EMAIL,
                'code': code,
            }
            
            # Improved HTML template with better email client compatibility
            html_template_string = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
                <title>{{ subject }}</title>
                <!--[if mso]>
                <noscript>
                    <xml>
                        <o:OfficeDocumentSettings>
                            <o:PixelsPerInch>96</o:PixelsPerInch>
                        </o:OfficeDocumentSettings>
                    </xml>
                </noscript>
                <![endif]-->
                <style type="text/css">
                    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
                    
                    body, table, td, p, a, li, blockquote {
                        -webkit-text-size-adjust: 100%;
                        -ms-text-size-adjust: 100%;
                    }
                    
                    table, td {
                        mso-table-lspace: 0pt;
                        mso-table-rspace: 0pt;
                    }
                    
                    img {
                        -ms-interpolation-mode: bicubic;
                        border: 0;
                        height: auto;
                        line-height: 100%;
                        outline: none;
                        text-decoration: none;
                    }
                    
                    body {
                        margin: 0 !important;
                        padding: 0 !important;
                        background-color: #ffffff;
                        font-family: 'Open Sans', Arial, sans-serif;
                        width: 100% !important;
                        height: 100% !important;
                    }
                    
                    .email-container {
                        max-width: 600px;
                        margin: 0 auto;
                        background-color: #ffffff;
                    }
                    
                    .email-header {
                        background-color: {{ primary_color }};
                        padding: 20px;
                        text-align: left;
                        border-radius: 12px 12px 0 0;
                    }
                    
                    .email-header h1 {
                        margin: 0;
                        color: #ffffff;
                        font-size: 24px;
                        font-weight: 700;
                        font-family: 'Open Sans', Arial, sans-serif;
                    }
                    
                    .email-body {
                        padding: 40px 30px;
                        text-align: center;
                        color: #333333;
                    }
                    
                    .email-body h2 {
                        font-size: 32px;
                        font-weight: 700;
                        margin: 0 0 20px;
                        color: #1a3a3a;
                        font-family: 'Open Sans', Arial, sans-serif;
                    }
                    
                    .email-body p {
                        font-size: 16px;
                        line-height: 1.5;
                        color: #555555;
                        margin-bottom: 20px;
                        font-family: 'Open Sans', Arial, sans-serif;
                    }
                    
                    .code {
                        font-size: 48px;
                        font-weight: 700;
                        letter-spacing: 10px;
                        margin: 20px 0;
                        color: #1a3a3a;
                        font-family: 'Open Sans', Arial, sans-serif;
                    }
                    
                    .email-footer {
                        background-color: #cfe2f3;
                        padding: 30px;
                        text-align: center;
                        border-radius: 0 0 12px 12px;
                    }
                    
                    .email-footer p {
                        font-size: 14px;
                        color: #888888;
                        margin: 0;
                        font-family: 'Open Sans', Arial, sans-serif;
                    }
                    
                    .email-footer a {
                        color: #ff6347;
                        text-decoration: none;
                        font-weight: 700;
                    }
                    
                    /* Mobile responsiveness */
                    @media screen and (max-width: 600px) {
                        .email-container {
                            width: 100% !important;
                            margin: 0 !important;
                        }
                        
                        .email-body {
                            padding: 20px !important;
                        }
                        
                        .email-body h2 {
                            font-size: 24px !important;
                        }
                        
                        .code {
                            font-size: 36px !important;
                            letter-spacing: 5px !important;
                        }
                    }
                </style>
            </head>
            <body>
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                        <td>
                            <div class="email-container">
                                <div class="email-header">
                                    <h1>{{ company_name }}</h1>
                                </div>
                                <div class="email-body">
                                    <h2>{{ heading }}</h2>
                                    {{ body_html|safe }}
                                    {% if code %}
                                        <div class="code">{{ code }}</div>
                                        <p>This code will expire in 10 minutes. If you didn't request this code, please ignore this email.</p>
                                    {% endif %}
                                </div>
                                <div class="email-footer">
                                    <p>Need help? Contact our support team at <a href="mailto:{{ support_email }}">{{ support_email }}</a></p>
                                    <p style="margin-top: 10px;">&copy; {% now "Y" %} {{ company_name }}. All rights reserved.</p>
                                </div>
                            </div>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
            
            template = Template(html_template_string)
            context = Context(context_data)
            html_message = template.render(context)
            
            # Create plain text version for better deliverability
            # Remove HTML tags for plain text version
            clean_body = body_html.replace('<p>', '').replace('</p>', '\n').replace('<br>', '\n')
            
            plain_text_message = f"""
            {heading}
            
            {clean_body}
            
            Need help? Contact our support team at {EmailService.SUPPORT_EMAIL}
            
            © {EmailService.COMPANY_NAME}. All rights reserved.
            """
            
            # Use EmailMultiAlternatives for better HTML email support
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email]
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send()
            
            logger.info(f"Email sent successfully to {recipient_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
            raise

    @staticmethod
    def send_kyc_review_email(user):
        """Sends an email notifying the user that their KYC is under review."""
        if not user.email:
            logger.warning(f"Cannot send KYC review email to user {user.id}: no email address")
            return
            
        subject = "Your FoloMoney KYC Status"
        heading = "We're Reviewing Your Info"
        
        body_html = f"""
        <p>Hello {user.first_name}, thank you for submitting your details. Your account is now active for you to explore.</p>
        <p>Your KYC documents are under review, and we'll notify you with an update within 24-48 hours.</p>
        """
        
        EmailService._send_branded_email(user.email, subject, heading, body_html)

    @staticmethod
    def send_wallet_creation_success_email(user):
        """Sends an email upon successful wallet creation."""
        if not user.email:
            logger.warning(f"Cannot send wallet creation email to user {user.id}: no email address")
            return
            
        subject = "Welcome to Your FoloMoney Wallet!"
        heading = "Your Wallet is Ready!"
        
        body_html = f"""
        <p>Great news, {user.first_name}!</p>
        <p>Your FoloMoney wallet has been successfully created. You can now explore all the features in the app, from seamless transfers to easy payments.</p>
        """
        
        EmailService._send_branded_email(user.email, subject, heading, body_html) 