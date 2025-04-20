from peewee import *
import datetime
from typing import Optional, NamedTuple
import io
import csv
from dateutil.relativedelta import relativedelta
import json
import xml.etree.ElementTree as ET
import re
from dotenv import load_dotenv
import os

load_dotenv()

db = SqliteDatabase(os.environ.get("INVENTORY_DB_PATH", "inventory.db"))
CAT_ICONS_PATH = os.environ.get("CATEGORY_ICONS_PATH", "/data/category_icons/")
os.makedirs(CAT_ICONS_PATH, exist_ok=True)

class Category(Model):
    ALL_PRODUCTS_PLACEHOLDER = {"name": "All Products", "color": "black", "image_path": None, "id": 0}

    name = CharField(unique=True)
    color = CharField(unique=True)
    image_path = CharField(null=True)
    price = DecimalField(null=True)

    @staticmethod
    def all() -> list['Category']:
        return list(Category.select())

    @staticmethod
    def all_alphabetized() -> list['Category']:
        return list(Category.select().order_by(Category.name))

    @staticmethod
    def add_category(name: str, color: str, icon_path : str) -> 'Category':
        colored_icon_path = Category.change_svg_color(icon_path, color, name)
        category = Category.create(
            name=name,
            color = color,
            image_path = colored_icon_path)


        return category

    @staticmethod
    def get_category(name_or_id: str | int) -> Optional['Category']:
        try:
            if type(name_or_id) is str:
                return Category.get(Category.name == name_or_id)
            else:
                return Category.get_by_id(name_or_id)
        except DoesNotExist:
            return None


    @classmethod
    def get_by_color(cls, hex_code: str) -> Optional['Category']:
        return cls.get_or_none(cls.color == hex_code)

    @staticmethod
    def delete_category(category_id):
        category = Category.get_category(category_id)
        category.delete_instance()
        #delete products in category
        products = Product.select().where(Product.category == category_id)
        for prod in products:
            Product.delete_product(prod.get_id())

    def update_category(self, category_name: str, category_color: str):
        self.name = category_name
        self.color = category_color
        self.image_path = self.change_svg_color(self.image_path, category_color, category_name)
        self.save()

    @staticmethod
    def change_svg_color(input_svg: str, new_color: str, name : str):
        try:
            tree = ET.parse("static/" + input_svg)
        except FileNotFoundError:
            tree = ET.parse(input_svg)
        root = tree.getroot()

        namespace = {'svg': 'http://www.w3.org/2000/svg'}
        ET.register_namespace('', namespace['svg'])

        for style in root.findall(".//{http://www.w3.org/2000/svg}style"):
            if style.text:
                new_style_text = re.sub(r'#([0-9a-fA-F]{3,6})', new_color, style.text, flags=re.IGNORECASE)
                style.text = new_style_text

        output_path = CAT_ICONS_PATH + name + ".svg"
        #tree.write("static/" + output_path)
        tree.write(output_path)
        return output_path


    class Meta:
        database = db



# To hold data from the form before being added to the db
class StockUnitSubmission(NamedTuple):
    id: Optional[int]
    name: str
    multiplier: int
    price: float
    count: Optional[int]



class Product(Model):
    product_name = CharField(unique=True)
    category = ForeignKeyField(Category, backref='products')
    inventory = IntegerField(default=0)
    inventory_breakdown = TextField(null=False) # [[stock_unit.id, count]]
    ideal_stock = IntegerField()
    price = FloatField(default=0)
    image_path = CharField(null=True)
    last_updated = DateTimeField(default=datetime.datetime.now)
    days_left = DecimalField(decimal_places=2, auto_round=True, null=True)
    # not notified = 0
    # notified once (half inventory) = 1
    # notified twice (half and 1/4 inventory) = 2
    notified = IntegerField(default=0)
    lifetime_donated = IntegerField(default=0)
    lifetime_purchased = IntegerField(default=0)

    ########################################
    ############# CLASS METHODS ############
    ########################################

    @staticmethod
    def get_low_products():
        product_levels = [0, 0, 0]
        for product in Product.all():
            if product.ideal_stock == 0:  # should never happen, but keeps the server from crashing
                continue
            if product.inventory / product.ideal_stock <= 0.25:
                product_levels[0] += 1
            elif (product.inventory / product.ideal_stock > 0.25) and (product.inventory / product.ideal_stock <= 0.5):
                product_levels[1] += 1
            else:
                product_levels[2] += 1
        return product_levels

    @staticmethod
    def all() -> list['Product']:
        return list(Product.select())

    @staticmethod
    def search(product: str = '') -> list['Product']:
        return list(Product.select().where(Product.product_name.ilike(f'%{product}%')))

    @staticmethod
    def search_filter_and_sort(
        product_name_fragment: str = '',
        product_category_id: int = 0,
        product_sort_method: str = None,
        product_force_first: int = None
    ) -> list['Product']:
        query = Product.select()

        if len(product_name_fragment) > 0:
            query = query.where(Product.product_name.ilike(f'%{product_name_fragment}%'))
        if product_category_id != 0:
            query = query.where(Product.category_id == product_category_id)

        products: list['Product'] = list(query)

        if product_sort_method == 'alpha_a_z' or (product_sort_method == 'best_match' and len(product_name_fragment) == 0):
            products = list(sorted(products, key=lambda p: p.product_name.lower()))
        elif product_sort_method == 'alpha_z_a':
            products = list(reversed(sorted(products, key=lambda p: p.product_name.lower())))
        elif product_sort_method == 'best_match':
            products = list(sorted(products, key=lambda p: p.product_name.lower().find(product_name_fragment.lower())))
        elif product_sort_method == 'lowest_stock':
            products = list(sorted(products, key=lambda p: float('inf') if p.ideal_stock == 0 else p.inventory / p.ideal_stock))
        elif product_sort_method == 'highest_stock':
            products = list(reversed(sorted(products, key=lambda p: 0 if p.ideal_stock == 0 else p.inventory / p.ideal_stock)))
        elif product_sort_method == 'most_recent':
            products = list(reversed(sorted(products, key=lambda p: p.last_updated)))
        else:  # default to least recent
            products = list(sorted(products, key=lambda p: p.last_updated))

        if product_force_first is not None and product_force_first > 0:
            try:
                index = list(map(lambda x: x.get_id(), products)).index(product_force_first)
                first_product = products[index]
                del products[index]
                products.insert(0, first_product)
            except: #not in list
                pass

        return products

    @staticmethod
    # overloaded with category id for filter
    def urgency_rank(category_id: str = None, price: str = None, amount: str = None, text: str = None, ideal: str = None,) -> list['Product']:
        query = Product.select(Product)
        if category_id == '0' or category_id is None:
            pass
        else:
            query = query.where(Product.category_id == category_id)
        if price is None or price == '0':
            pass
        else:
            if price == '1':
                query = query.where(Product.price <= 5)
            elif price == '2':
                query = query.where(10 >= Product.price > 5)
            elif price == '3':
                query = query.where(Product.price > 10)
        if amount is None or amount == '0':
            pass
        else:
            if amount == '1':
                filtered_ids = []
                for product in query:
                    ratio = product.inventory / product.ideal_stock
                    if ratio <= 0.25:
                        filtered_ids.append(product.id)
                query = Product.select().where(Product.id.in_(filtered_ids))
            elif amount == '2':
                filtered_ids = []
                for product in query:
                    ratio = product.inventory / product.ideal_stock
                    if ratio <= 0.5 and ratio > 0.25:
                        filtered_ids.append(product.id)
                query = Product.select().where(Product.id.in_(filtered_ids))
            elif amount == '3':
                filtered_ids = []
                for product in query:
                    ratio = product.inventory / product.ideal_stock
                    if ratio > 0.5:
                        filtered_ids.append(product.id)
                query = Product.select().where(Product.id.in_(filtered_ids))
        if ideal is None or ideal == '0':
            pass
        else:
            if ideal == '1':
                filtered_ids = []
                for p in query:
                    if p.ideal_stock <= 50:
                        filtered_ids.append(p.id)
                query = Product.select().where(Product.id.in_(filtered_ids))
            elif ideal == '2':
                filtered_ids = []
                for p in query:
                    if 50 < p.ideal_stock <= 100:
                        filtered_ids.append(p.id)
                query = Product.select().where(Product.id.in_(filtered_ids))
            elif ideal == '3':
                filtered_ids = []
                for p in query:
                    if p.ideal_stock > 100:
                        filtered_ids.append(p.id)
                query = Product.select().where(Product.id.in_(filtered_ids))
        if text is None or text == '':
            pass
        else:
            hold = []
            for p in query:
                if text in p.product_name:
                    hold.append(p.id)
            query = Product.select().where(Product.id.in_(hold))
        query = query.order_by(fn.COALESCE(Product.days_left, 999999))
        return list(query)



    @staticmethod
    # overloaded with category id for filter
    def alphabetized_of_category(category_id: int = None) -> list['Product']:
        query = Product.select(Product, Category).join(Category)

        if category_id is not None and category_id != 0:
            query = query.where(Product.category_id == category_id)

        query = query.order_by(Product.product_name)

        return list(query)

    @staticmethod
    def add_product(name: str, category: int, ideal_stock: int, days_left: float = None, image_path: str = None) -> 'Product':
        product, _created = Product.get_or_create(
            product_name=name,
            category=category,
            price=0,
            lifetime_donated=0,
            lifetime_purchased=0,
            defaults={
                'inventory': 0,
                'inventory_breakdown': '[]',
                'ideal_stock': ideal_stock,
                'image_path': image_path,
                'days_left': days_left
            }
        )

        product: Product = product
        individual_unit = StockUnit.add_stock_unit(
            product.get_id(),
            "Individual",
            0,
            1
        )

        inventory_breakdown = [[individual_unit.get_id(), 0]]
        product.inventory_breakdown = json.dumps(inventory_breakdown)
        product.save()

        return product

    # Fills the database with how many days till each product is out of stock
    @staticmethod
    def fill_days_left():
        products = Product.all()
        for product in products:
            days_left = product.get_days_until_out()
            if days_left == None:
                product.days_left = None
            else:
                product.days_left = days_left
            product.save()

    # Returns the information of the chosen product based on its product name or id
    @staticmethod
    def get_product(name_or_id: str | int) -> Optional['Product']:
        try:
            if type(name_or_id) is str:
                return Product.get(Product.product_name == name_or_id)
            else:
                return Product.get_by_id(name_or_id)
        except DoesNotExist:
            return None

    # retrieves products with inventory <= 25% ideal stock
    @staticmethod
    def products_leq_quarter() -> list['Product']:
        products = Product.all()
        res = []
        for item in products:
            if item.notified < 2 and item.inventory <= (item.ideal_stock / 4):
                res.append(item)
        return res

    # retrieves products with inventory <= 50% ideal stock
    @staticmethod
    def products_leq_half() -> list['Product']:
        products = Product.all()
        res = []
        for item in products:
            if item.notified < 1 and item.inventory <= (item.ideal_stock / 2):
                res.append(item)
        return res

    # Deletes the chosen product
    @staticmethod
    def delete_product(product_id):
        product = Product.get_product(product_id)
        if product is not None:
            product.delete_instance()
            InventorySnapshot.delete_snapshots_for_product(product_id)
            StockUnit.delete_stock_units_for_product(product_id)

    
    @classmethod
    def get_csv(cls):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Name', 'Category', 'Inventory', 'Ideal Stock',
            'Days Left', 'Lifetime amount donated', 'Lifetime amount purchased'
        ])
        for product in cls.select():
            product: Product = product
            writer.writerow([product.product_name, product.category.name, product.inventory, \
                             product.ideal_stock, product.days_left,
                             product.lifetime_donated, product.lifetime_purchased])
        output.seek(0)
        return output.getvalue()

    ########################################
    ########### INSTANCE METHODS ###########
    ########################################

    def time_since_last_updated(self) -> relativedelta:
        return relativedelta(datetime.datetime.now(), self.last_updated)
    
    def been_over_one_week_since_updated(self) -> relativedelta:
        delta = self.time_since_last_updated()
        return delta.weeks >= 1 or delta.months >= 1 or delta.years >= 1

    # Returns a human string for how long it has been since the product was updated (e.g., "2 days" or "1 week")
    def human_last_updated(self) -> str:
        delta = self.time_since_last_updated()
        if delta.months > 1: #allow things like "6 weeks"
            return f"{delta.months} months"
        if delta.weeks > 1: #allow things like "10 days"
            return f"{delta.weeks} weeks"
        elif delta.days > 0:
            return f"{delta.days} {'day' if delta.days == 1 else 'days'}"
        elif delta.hours > 0:
            return f"{delta.hours} {'hour' if delta.hours == 1 else 'hours'}"
        elif delta.minutes > 0:
            return f"{delta.minutes} {'minute' if delta.minutes == 1 else 'minutes'}"
        else:
            return f"{delta.seconds} {'second' if delta.seconds == 1 else 'seconds'}"

    # Calculates the average inventory used per day
    def get_usage_per_day(self) -> float | None:
        snapshots = InventorySnapshot.all_of_product(self.get_id())

        daily_usages: list[float] = []
        for index in range(len(snapshots) - 1):
            curr = snapshots[index]
            prev = snapshots[index + 1]  # Previous in time, not in list

            if prev.individual_inventory > curr.individual_inventory: # There must be a decrease in stock; otherwise, it was a restock
                inventory_delta = prev.individual_inventory - curr.individual_inventory
                day_delta = (curr.timestamp - prev.timestamp).total_seconds() / 86_400
                daily_usages.append(inventory_delta / day_delta)

        return None if len(daily_usages) == 0 else sum(daily_usages) / len(daily_usages)

    # Calculate the number of days until the product will run out
    # Take daily_usage if it was already calculated; if [`None`] is provided, then it will be recalculated
    def get_days_until_out(self, daily_usage: float = None) -> float | None:
        daily_usage = daily_usage if daily_usage is not None else self.get_usage_per_day()
        if daily_usage is None or abs(daily_usage) < 1e-4:
            return None
        else:
            return self.inventory / daily_usage

    def get_inventory_breakdown(self) -> list[list[int, int]]:
        try:
            return json.loads(self.inventory_breakdown)
        except:
            return []

    def set_img_path(self, img_path: str):
        self.image_path = img_path
        self.save()

    # Sets the ideal stock to [`new_stock`] units
    def update_ideal_stock(self, new_stock: int):
        self.ideal_stock = new_stock
        self.last_updated = datetime.datetime.now()
        self.save()

    def update_product(self, product_name: str, stock_unit_submissions: list[StockUnitSubmission], ideal_stock: int):
        individual_count, total_price = StockUnit.tally_stock_unit_submissions(stock_unit_submissions)
        stock_units = StockUnit.commit_stock_unit_submissions(self.get_id(), stock_unit_submissions)
        
        self.price = 0 if individual_count==0 else total_price / individual_count
        self.inventory = individual_count
        self.product_name = product_name
        self.ideal_stock = ideal_stock
        self.last_updated = datetime.datetime.now()
        inventory_breakdown = []
        for unit, submission in zip(stock_units, stock_unit_submissions):
            inventory_breakdown.append([unit.get_id(), submission.count or 0])
        self.inventory_breakdown = json.dumps(inventory_breakdown)
        self.save()



    # Add to the current available inventory of a product with the unit submissions
    def add_stock(self, stock_unit_submissions: list[StockUnitSubmission], donation: bool):
        StockUnit.commit_stock_unit_submissions(self.get_id(), stock_unit_submissions)

        added_individual_inventory, _ = StockUnit.tally_stock_unit_submissions(stock_unit_submissions)

        stock_units = StockUnit.all_of_product(self.get_id())
        stock_unit_ids = list(map(lambda x: x.id, stock_units))
        stock_unit_names = list(map(lambda x: x.name, stock_units))
        stock_count_map: dict[int, int] = {}
        total_individual_inventory = 0
        total_price = 0

        for unit_id, count in self.get_inventory_breakdown():
            stock_count_map[unit_id] = count
            index = stock_unit_ids.index(unit_id)
            total_individual_inventory += count * stock_units[index].multiplier
            total_price += count * stock_units[index].price
        
        for submission in stock_unit_submissions:
            index = stock_unit_names.index(submission.name)
            count = submission.count or 0
            total_individual_inventory += count * stock_units[index].multiplier
            total_price += count * stock_units[index].price
            stock_unit_id = stock_units[index].get_id()
            if stock_unit_id in stock_count_map:
                stock_count_map[stock_unit_id] += count
            else:
                stock_count_map[stock_unit_id] = count

        if donation:
            if self.lifetime_donated is None:
                self.lifetime_donated = 0
            self.lifetime_donated += added_individual_inventory
        else:
            if self.lifetime_purchased is None:
                self.lifetime_purchased = 0
            self.lifetime_purchased += added_individual_inventory

        self.inventory = total_individual_inventory
        self.price = 0 if total_individual_inventory==0 else total_price / total_individual_inventory
        self.inventory_breakdown = json.dumps([[k, v] for k, v in stock_count_map.items()])
        self.save()
        
        InventorySnapshot.create_snapshot(
            self.get_id(),
            total_individual_inventory,
            total_price,
            added_donated=added_individual_inventory if donation else 0,
            added_purchased=added_individual_inventory if not donation else 0
        )

    # Sets the current available stock of a product to match the stock units
    def update_stock(self, stock_unit_submissions: list[StockUnitSubmission]):
        individual_inventory, total_value = StockUnit.tally_stock_unit_submissions(stock_unit_submissions)
        stock_units = StockUnit.commit_stock_unit_submissions(self.get_id(), stock_unit_submissions)
        inventory_breakdown = []
        for unit, submission in zip(stock_units, stock_unit_submissions):
            inventory_breakdown.append([unit.get_id(), submission.count or 0])
        self.inventory_breakdown = json.dumps(inventory_breakdown)
        self.inventory = individual_inventory
        self.price = 0 if individual_inventory==0 else total_value / individual_inventory
        self.last_updated = datetime.datetime.now()
        self.save()
        InventorySnapshot.create_snapshot(self.get_id(), individual_inventory, total_value, added_donated=0, added_purchased=0)

    # marks product as notified (after email is sent)
    def increment_notified(self):
        self.notified += 1
        self.save()

    def mark_not_notified(self):
        self.notified = 0
        self.save()



    class Meta:
        database = db



class StockUnit(Model):
    PLACEHOLDER = {
        "product_id": None,
        "id": None,
        "name": "Individual",
        "price": None,
        "multiplier": 1
    }
    
    product_id = ForeignKeyField(Product, backref='stockunits')
    name = CharField(null=False)
    price = DecimalField(decimal_places=2, auto_round=True)
    multiplier = IntegerField(null=False)
    
    @staticmethod
    def add_stock_unit(product_id: int, name: str, price: float, multiplier: int) -> 'StockUnit':
        return StockUnit.create(
            name=name,
            price=price,
            product_id=product_id,
            multiplier=multiplier
        )

    @staticmethod
    def get_stock_unit(name_or_id: str | int) -> Optional['StockUnit']:
        try:
            if type(name_or_id) is str:
                return StockUnit.get(StockUnit.name == name_or_id)
            else:
                return StockUnit.get_by_id(name_or_id)
        except DoesNotExist:
            return None
        
    @staticmethod
    def all_of_product(product_id: int) -> list['StockUnit']:
        return list(StockUnit.select().where(
            StockUnit.product_id==product_id
        ))
    
    @staticmethod
    def all_of_product_with_count(product_or_id: Product | int) -> list[list['StockUnit', int]]:
        if type(product_or_id) is int:
            product = Product.get_product(product_or_id)
        else:
            product = product_or_id
        stock_units = StockUnit.all_of_product(product.get_id())
        stock_units_with_counts = [[unit, 0] for unit in stock_units]
        stock_unit_ids = list(map(lambda x: x.get_id(), stock_units))
        for unit_id, count in product.get_inventory_breakdown():
            index = stock_unit_ids.index(unit_id)
            stock_units_with_counts[index][1] += count
        return stock_units_with_counts
    
    @staticmethod
    def delete_stock_units_for_product(product_id: int):
        StockUnit.delete().where(StockUnit.product_id == product_id).execute()
       
    @staticmethod
    def delete_stock_unit(name_or_id: str | int):
        stock_unit = StockUnit.get_stock_unit(name_or_id)
        if stock_unit is not None:
            stock_unit.delete_instance()

    # Tallies the total individual count and current price
    def tally_stock_unit_submissions(submitted_units: list[StockUnitSubmission]) -> tuple[int, float]:
        individual_count = 0
        total_cost = 0
        for unit in submitted_units:
            individual_count += (unit.count or 0) * unit.multiplier
            total_cost += (unit.count or 0) * unit.price
        return (individual_count, round(total_cost, 2))

    # Creates/updates the stock units and returns the new StockUnits
    def commit_stock_unit_submissions(product_id: int, submitted_units: list[StockUnitSubmission]) -> list['StockUnit']:
        collector = []
        for unit in submitted_units:
            if unit.id is None: #create new stock unit
                stock_unit = StockUnit.add_stock_unit(product_id, unit.name, unit.price, unit.multiplier)
                collector.append(stock_unit)
            else:
                live_unit = StockUnit.get_stock_unit(unit.id)
                live_unit.name = unit.name
                live_unit.price = unit.price
                live_unit.multiplier = unit.multiplier
                live_unit.save()
                collector.append(live_unit)
        return collector

    class Meta:
        database = db



class InventorySnapshot(Model):
    product = ForeignKeyField(Product, backref='snapshots', on_delete='CASCADE')
    individual_inventory = IntegerField(null=False)
    value_at_time = DecimalField(decimal_places=2, auto_round=True)
    timestamp = DateTimeField(default=datetime.datetime.now)
    added_donated = IntegerField(null=False, default=0)
    added_purchased = IntegerField(null=False, default=0)

    @staticmethod
    def all() -> list['InventorySnapshot']:
        return list(InventorySnapshot.select())

    @staticmethod
    def all_of_product(product_id: int) -> list['InventorySnapshot']:
        return list(reversed(InventorySnapshot.select().where(
            InventorySnapshot.product == product_id
        )))

    @staticmethod
    def all_of_product_in_time_period(product_id: int, start_date: datetime.datetime, end_date: datetime.datetime) -> list['InventorySnapshot']:
        return list(InventorySnapshot.select().where(
            InventorySnapshot.product == product_id & InventorySnapshot.timestamp.between(start_date, end_date)
        ))

    @staticmethod
    def product_snapshots_chronological(product_id: int) -> list['InventorySnapshot']:
        return list(InventorySnapshot.select().where(
            InventorySnapshot.product == product_id
        ))

    @staticmethod
    def create_snapshot(product_id: int, inventory: int, price: float, added_donated: int, added_purchased: int) -> 'InventorySnapshot':
        return InventorySnapshot.create(
            product=product_id,
            individual_inventory=inventory,
            value_at_time=price,
            added_donated=added_donated,
            added_purchased=added_purchased
        )

    @staticmethod
    def delete_snapshots_for_product(product_id: int):
        InventorySnapshot.delete().where(InventorySnapshot.product == product_id).execute()

    def get_average_price(self) -> float:
        return 0 if self.individual_inventory==0 else self.value_at_time / self.individual_inventory

    class Meta:
        database = db

