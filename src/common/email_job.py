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
    def send_email(products: list[Product], recipient: str):
        message = Mail(
            from_email=APP_EMAIL,
            to_emails=recipient,
            subject='Inventory is running low!',
            html_content = f'<strong>The following products are at or below 1/4 of their ideal stock!</strong> \
                 <ul> \
                 {''.join([f"<li>{p.product_name}</li>" for p in products])} \
                 </ul>')
        try:
            sg = SendGridAPIClient(KEY)
            response = sg.send(message)
            print(response.status_code)
        except Exception as e:
            print(e)

    @staticmethod
    def process_emails(admin_email: str):
        if admin_email and len(admin_email) > 0:
            products = Product.products_leq_quarter()
            if len(products) > 0:
                EmailJob.send_email(products, admin_email)
                for item in products:
                    item.mark_notified()



