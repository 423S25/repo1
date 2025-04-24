import os

from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from src.model.product import Product

load_dotenv()

APP_EMAIL = "hrdc.inventory@gmail.com"
KEY = os.environ.get("SENDGRID_KEY")

class EmailJob():
    @staticmethod
    def send_urgent(products: list[Product], recipient: str):
        message = Mail(
            from_email=APP_EMAIL,
            to_emails=recipient,
            subject='URGENT! Inventory is almost out!',
            html_content = f'<strong>The following products are at or below 1/4 of their ideal stock!</strong> \
                 <ul> \
                 {''.join([f"<li>{p.product_name}</li>" for p in products])} \
                 </ul>')
        try:
            sg = SendGridAPIClient(KEY)
            response = sg.send(message)
            print('email response code', response.status_code)
        except Exception as e:
            print(e)

    @staticmethod
    def send_warning(products: list[Product], recipient: str):
        message = Mail(
            from_email=APP_EMAIL,
            to_emails=recipient,
            subject='Warning! Inventory is running low!',
            html_content = f'<strong>The following products are at or below 1/2 of their ideal stock!</strong> \
                 <ul> \
                 {''.join([f"<li>{p.product_name}</li>" for p in products])} \
                 </ul>')
        try:
            sg = SendGridAPIClient(KEY)
            response = sg.send(message)
            print('email response code', response.status_code)
        except Exception as e:
            print(e)

    @staticmethod
    def process_emails(admin_emails: list[str]):
        print(admin_emails)
        warnings = Product.products_leq_half()
        urgents = Product.products_leq_quarter()
        for admin_email in admin_emails:
            print(type(admin_email))
            if admin_email and len(admin_email) > 0:
                if len(warnings) > 0:
                    EmailJob.send_warning(warnings, admin_email)
                    for product in warnings:
                        product.increment_notified()
                if len(urgents) > 0:
                    EmailJob.send_urgent(urgents, admin_email)
                    for product in urgents:
                        product.increment_notified()



