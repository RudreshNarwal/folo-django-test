from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


class EmailService:
    """A service for sending branded HTML emails."""

    PRIMARY_COLOR = "#0070EA"
    FONT_FAMILY = "'Open Sans', sans-serif"
    COMPANY_NAME = "FoloMoney"

    @staticmethod
    def _send_branded_email(recipient_email, subject, heading, body_html):
        """Helper to send a branded HTML email."""
        
        context = {
            'heading': heading,
            'body_html': body_html,
            'primary_color': EmailService.PRIMARY_COLOR,
            'font_family': EmailService.FONT_FAMILY,
            'company_name': EmailService.COMPANY_NAME,
        }
        
        # Using a simple HTML template string
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    background-color: #f4f4f4;
                }
                .email-container {
                    max-width: 600px;
                    margin: 20px auto;
                    background-color: #ffffff;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    font-family: {{ font_family }};
                }
                .email-header {
                    background-color: {{ primary_color }};
                    color: #ffffff;
                    padding: 30px;
                    text-align: center;
                }
                .email-header h1 {
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }
                .email-body {
                    padding: 30px 40px;
                    line-height: 1.6;
                    color: #333333;
                    font-size: 16px;
                }
                .email-footer {
                    background-color: #f4f4f4;
                    color: #888888;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                }
                .button {
                    display: inline-block;
                    padding: 12px 24px;
                    margin-top: 20px;
                    background-color: {{ primary_color }};
                    color: #ffffff;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: 600;
                }
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="email-header">
                    <h1>{{ company_name }}</h1>
                </div>
                <div class="email-body">
                    <h2>{{ heading }}</h2>
                    {{ body_html|safe }}
                </div>
                <div class="email-footer">
                    &copy; {{ "now"|date:"Y" }} {{ company_name }}. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        
        html_message = render_to_string(html_template, context)

        send_mail(
            subject=subject,
            message='',  # Plain text message (optional)
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
            html_message=html_message
        )

    @staticmethod
    def send_kyc_review_email(user):
        """Sends an email notifying the user that their KYC is under review."""
        subject = "Your FoloMoney KYC Status"
        heading = "We're On It!"
        
        body_html = f"""
        <p>Hello {user.first_name},</p>
        <p>Thank you for submitting your details. We are currently reviewing your KYC documents.</p>
        <p>Your account is active, and you can start exploring some of our features right away. We will notify you with a full update within the next 24-48 hours.</p>
        <p>Thank you for your patience.</p>
        <p>Best,<br>The {EmailService.COMPANY_NAME} Team</p>
        """
        
        EmailService._send_branded_email(user.email, subject, heading, body_html)

    @staticmethod
    def send_wallet_creation_success_email(user):
        """Sends an email upon successful wallet creation."""
        subject = "Welcome to Your FoloMoney Wallet!"
        heading = "Your Wallet is Ready!"
        
        body_html = f"""
        <p>Hello {user.first_name},</p>
        <p>Great news! Your FoloMoney wallet has been successfully created and is now active.</p>
        <p>You can now explore and enjoy all the features available in the app, from seamless transfers to easy payments.</p>
        <p>If you have any questions, don't hesitate to reach out to our support team.</p>
        <p>Happy spending!</p>
        <p>Best,<br>The {EmailService.COMPANY_NAME} Team</p>
        """
        
        EmailService._send_branded_email(user.email, subject, heading, body_html) 