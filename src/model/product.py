from peewee import *
import datetime
from typing import Optional



db = SqliteDatabase('inventory.db')



class Product(Model):
    product_name = CharField(unique=True)
    inventory = IntegerField(default=0)
    price = DecimalField(decimal_places=2, auto_round=True)
    unit_type = CharField(null=True)
    ideal_stock = IntegerField()
    image_path = CharField(null=True)
    last_updated = DateTimeField(default=datetime.datetime.now)
    days_left = DecimalField(decimal_places=2, auto_round=True, null=True)



    @staticmethod
    def all() -> list['Product']:
        return list(Product.select())

    @staticmethod
    def urgency_rank() -> list['Product']:
        UR = Product.select().order_by((fn.COALESCE(Product.days_left, 999999)))
        return list(UR)

    @staticmethod
    def add_product(name: str, stock: int, price: float, unit_type: str, ideal_stock: int, days_left: None ,image_path: str = None) -> 'Product':
        product, created = Product.get_or_create(
            product_name=name,
            defaults={
                'inventory': stock,
                'price': price,
                'unit_type': unit_type,
                'ideal_stock': ideal_stock,
                'image_path': image_path,
                'days_left': days_left
            }
        )
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



    # Deletes the chosen product
    @classmethod
    def delete_product(cls, product_id):
        product = Product.get_product(product_id)
        product.delete_instance()

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
    def create_snapshot(product_id: int, inventory: int) -> 'InventorySnapshot':
        snapshot = InventorySnapshot.create(
            product_id=product_id,
            inventory=inventory
        )
        return snapshot
    


    # Sets this snapshot to be ignored. For use if the entry was likely in error
    def ignore(self):
        self.ignored = True
        self.save()



    class Meta:
        database = db



