from src.model.product import Product, InventorySnapshot, Category
from flask import Response, make_response
from collections import defaultdict
from datetime import datetime, timedelta
from calendar import monthrange

class Helper():

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

    def get_inventory_chart_data(self, colors):
        now = datetime.now()
        one_year_ago = now - timedelta(days=365)
        snapshots = (InventorySnapshot
            .select(InventorySnapshot, Product, Category)
            .join(Product)
            .join(Category)
            .where(InventorySnapshot.timestamp >= one_year_ago)
        )
        category_totals = defaultdict(lambda: defaultdict(int))
        all_month_keys = []
        for i in range(12):
            month_date = (now.replace(day=1) - timedelta(days=30 * i))
            key = month_date.strftime("%Y-%m")
            all_month_keys.append(key)
        all_month_keys = sorted(set(all_month_keys))
        for snap in snapshots:
            month_key = snap.timestamp.strftime("%Y-%m")
            category_name = snap.product.category.name
            category_totals[category_name][month_key] += snap.individual_inventory
        labels = [datetime.strptime(k, "%Y-%m").strftime("%b %Y") for k in all_month_keys]
        datasets = []
        for i, (category_name, data_by_month) in enumerate(category_totals.items()):
            data = [data_by_month.get(month_key, None) for month_key in all_month_keys]
            datasets.append({
                "label": category_name,
                "data": data,
                "backgroundColor": colors[i],
                "borderColor": colors[i],
                "fill": False
            })
        return {
            "labels": labels,
            "datasets": datasets
        }