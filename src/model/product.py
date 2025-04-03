from peewee import *
import datetime
from typing import Optional
import io
import csv

db = SqliteDatabase('inventory.db')


class Category(Model):
    ALL_PRODUCTS_PLACEHOLDER = {"name": "All Products", "color": "black", "image_path": None, "id": 0}
    
    name = CharField(unique=True)
    color = CharField(unique=True)
    image_path = CharField(null=True)

    @staticmethod
    def all() -> list['Category']:
        return list(Category.select())
    
    @staticmethod
    def all_alphabetized() -> list['Category']:
        return list(Category.select().order_by(Category.name))

    @staticmethod
    def add_category(name: str, color: str) -> 'Category':
        category = Category.create(
            name=name,
            color = color
        )
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

    @staticmethod
    def delete_category(category_id):
        category = Category.get_category(category_id)
        category.delete_instance()

    def update_category(self, category_name: str, category_color: str):
        self.name = category_name
        self.color = category_color
        self.save()


    class Meta:
        database = db



class Product(Model):
    product_name = CharField(unique=True)
    category = ForeignKeyField(Category, backref='products')
    inventory = IntegerField(default=0)
    price = DecimalField(decimal_places=2, auto_round=True)
    unit_type = CharField(null=True)
    ideal_stock = IntegerField()
    image_path = CharField(null=True)
    last_updated = DateTimeField(default=datetime.datetime.now)
    days_left = DecimalField(decimal_places=2, auto_round=True, null=True)
    #not notified = 0
    #notified once (half inventory) = 1
    #notified twice (half and 1/4 inventory) = 2
    notified = IntegerField(default=0)
    lifetime_donated = IntegerField(default=0)
    lifetime_purchased = IntegerField(default=0)

    ########################################
    ############# CLASS METHODS ############
    ########################################

    @staticmethod
    def get_low_products():
        product_levels = [0,0,0]
        for product in Product.all():
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
    #overloaded with category id for filter
    def urgency_rank(category_id: int = None) -> list['Product']:
        query = Product.select(Product, Category).join(Category)

        if category_id is not None:
            query = query.where(Product.category_id == category_id)

        query = query.order_by(fn.COALESCE(Product.days_left, 999999))

        return list(query)
    
    @staticmethod
    #overloaded with category id for filter
    def alphabetized_of_category(category_id: int = None) -> list['Product']:
        query = Product.select(Product, Category).join(Category)

        if category_id is not None:
            query = query.where(Product.category_id == category_id)

        query = query.order_by(Product.product_name)

        return list(query)

    @staticmethod
    def add_product(name: str, stock: int, category: int, price: float, unit_type: str, ideal_stock: int, donation: bool, days_left: None, image_path: str = None) -> 'Product':
        product, created = Product.get_or_create(
            product_name=name,
            category=category,
            lifetime_donated = stock if donation else 0,
            lifetime_purchased = stock if not donation else 0,
            defaults={
                'inventory': stock,
                'price': price,
                'unit_type': unit_type,
                'ideal_stock': ideal_stock,
                'image_path': image_path,
                'days_left': days_left
            }
        )
        InventorySnapshot.create_snapshot(product.get_id(), product.inventory)
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
    
    #retrieves products with inventory <= 25% ideal stock
    @staticmethod
    def products_leq_quarter() -> list['Product']:
        products = Product.all()
        res = []
        for item in products:
            if item.notified < 2 and item.inventory <= (item.ideal_stock / 4):
                res.append(item)
        return res
    
    #retrieves products with inventory <= 50% ideal stock
    @staticmethod
    def products_leq_half() -> list['Product']:
        products = Product.all()
        res = []
        for item in products:
            if item.notified < 1 and item.inventory <= (item.ideal_stock / 2):
                res.append(item)
        return res
    
    # Deletes the chosen product
    @classmethod
    def delete_product(cls, product_id):
        product = Product.get_product(product_id)
        product.delete_instance()
        InventorySnapshot.delete_snapshots_for_product(product_id)

    
    ########################################
    ########### INSTANCE METHODS ###########
    ########################################
    @classmethod
    def get_csv(cls):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Category', 'Inventory', 'Price', 'Unit Type', 'Ideal Stock',\
                          'Days Left', 'Lifetime amount donated', 'Lifetime amount purchased'])
        for product in cls.select():
            writer.writerow([product.product_name, product.category.name, product.inventory, \
                             product.price, product.unit_type, product.ideal_stock, product.days_left, product.lifetime_donated, product.lifetime_purchased])
        output.seek(0)
        return output.getvalue()

    # Calculates the average inventory used per day
    def get_usage_per_day(self) -> float | None:
        snapshots = InventorySnapshot.all_of_product(self.get_id())
        
        daily_usages: list[float] = []
        for index in range(len(snapshots)-1):
            curr = snapshots[index]
            prev = snapshots[index+1] # Previous in time, not in list
            if curr.ignored or prev.ignored:
                continue

            if prev.inventory > curr.inventory: # There must be a decrease in stock; otherwise, it was a restock
                inventory_delta = prev.inventory - curr.inventory
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

    def set_img_path(self, img_path: str):
        self.image_path = img_path
        self.save()


    # Sets the ideal stock to [`new_stock`] units
    def update_ideal_stock(self, new_stock: int):
        self.ideal_stock = new_stock
        self.last_updated = datetime.datetime.now()
        self.save()

    def update_product(self, product_name: str, price: float, unit_type: str, ideal_stock: int):
        self.product_name = product_name
        self.price = price
        self.unit_type = unit_type
        self.ideal_stock = ideal_stock

        self.last_updated = datetime.datetime.now()

        self.save()



    # Sets the current available stock of a product to [`new_stock`] units
    def update_stock(self, new_stock: int):
        self.inventory = new_stock
        self.last_updated = datetime.datetime.now()
        self.save()
        InventorySnapshot.create_snapshot(self.get_id(), self.inventory)

    #1. sets the lifetime_donated
    #2. if adjust_inventory is set, it will add/subtract from stock as well
    def set_donated(self, new_amount: int, adjust_inventory: bool):
        old_amount = self.lifetime_donated
        if adjust_inventory:
            self.inventory = self.inventory + (new_amount - old_amount)
        self.lifetime_donated = new_amount
        self.save()

    #1. sets the lifetime_purchased
    #2. if adjust_inventory is set, it will add/subtract from stock as well
    def set_purchased(self, new_amount: int, adjust_inventory: bool):
        old_amount = self.lifetime_purchased
        if adjust_inventory:
            self.inventory = self.inventory + (new_amount - old_amount)
        self.lifetime_purchased = new_amount
        self.save()

    # Increment price
    def increment_price(self, increase: float):
        self.price += increase
        self.last_updated = datetime.datetime.now()
        self.save()
    
    # Increments the ideal stock by [`increase`] units
    def increment_ideal_stock(self, increase: int):
        self.ideal_stock += increase
        self.last_updated = datetime.datetime.now()
        self.save()

    # Increments the current available stock of a product by [`increase`] units
    def increment_stock(self, increase: int):
        self.inventory += increase
        self.last_updated = datetime.datetime.now()
        self.save()

    #marks product as notified (after email is sent)
    def increment_notified(self):
        self.notified += 1
        self.save()
    
    def mark_not_notified(self):
        self.notified = 0 
        self.save()

        
    
    class Meta:
        database = db



class InventorySnapshot(Model):
    product_id = IntegerField(null=False)
    inventory = IntegerField(null=False)
    timestamp = DateTimeField(default=datetime.datetime.now)
    ignored = BooleanField(default=False) # To be used if a value was added in error

    @staticmethod
    def all() -> list['InventorySnapshot']:
        return list(InventorySnapshot.select())
    
    @staticmethod
    def all_of_product(product_id: int) -> list['InventorySnapshot']:
        snapshots: list['InventorySnapshot'] = list(reversed(InventorySnapshot.select().where(
            InventorySnapshot.product_id==product_id
        )))
        MIN_ALLOWED_DIFFERENCE = datetime.timedelta(seconds=45)

        for i in range(len(snapshots)-1): # if a value as immediately overwritten, it was probably in error and should be ignored
            curr = snapshots[i]
            prev = snapshots[i+1]
            delta = curr.timestamp - prev.timestamp
            if delta < MIN_ALLOWED_DIFFERENCE:
                prev.ignore()
        
        return snapshots
    
    @staticmethod
    def product_snapshots_chronological(product_id: int) -> list['InventorySnapshot']:
        snapshots: list['InventorySnapshot'] = list(InventorySnapshot.select().where(
            InventorySnapshot.product_id==product_id
        ))
        return snapshots



    @staticmethod
    def create_snapshot(product_id: int, inventory: int) -> 'InventorySnapshot':
        snapshot = InventorySnapshot.create(
            product_id=product_id,
            inventory=inventory, 
        )
        return snapshot
    
    @staticmethod
    def delete_snapshots_for_product(product_id: int):
        InventorySnapshot.delete().where(InventorySnapshot.product_id == product_id).execute()
    


    # Sets this snapshot to be ignored. For use if the entry was likely in error
    def ignore(self):
        self.ignored = True
        self.save()

    class Meta:
        database = db





