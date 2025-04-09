from src.model.product import Product
from flask import Response, make_response

class helper():

    def price_over_amount_inventory(self):
        products = Product.all()
        data = []
        for p in products:
            values = []
            values.append(p.price)
            values.append(p.inventory)
            values.append(p.product_name)
            data.append(values)
        return data

    def convert_to_rgb(self, colors):
        set = []
        for c in colors:
            c = c.lstrip('#')
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            fcgpt = (f"rgb({r}, {g}, {b})")
            set.append(str(fcgpt))
        # Return the RGB string in the desired format
        return list(set)

    def ideal_over_amount_inventory(self):
        products = Product.all()
        data = []
        for p in products:
            values = []
            values.append(p.inventory)
            values.append(p.ideal_stock)
            values.append(p.product_name)
            data.append(values)
        return data