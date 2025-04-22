import pytest
from app import app
from src.model.product import Product, Category, StockUnit, StockUnitSubmission

@pytest.fixture(autouse=True)
def setup_inventory():
    cat = Category.add_category("cleaning supplies", "test-color", "/icons/cat_icons/Cleaning.svg")
    
    products: list[Product] = [
        Product.add_product("clorox wipes", cat.get_id(), 10),
        Product.add_product("lysol", cat.get_id(), 30),
        Product.add_product("dish soap", cat.get_id(), 10)
    ]

    # Update the price and count to match the old test
    for index, product in enumerate(products):
        stock_unit_id = StockUnit.all_of_product(product_id=product.get_id())[0].get_id()
        submission = StockUnitSubmission(
            id=stock_unit_id,
            name="individual",
            multiplier=1,
            price=1,
            count=1 if index==0 else 10
        )
        product.update_stock([submission])

    yield cat
    Category.delete_category(cat.get_id())

#TODO: add more tests surrounding new unit type logic
def test_list_products(setup_inventory: Category):
    products = Product.all()
    assert len(products) == 3

def test_add_product(setup_inventory: Category):
    product: Product = Product.add_product("test1", setup_inventory.get_id(), 1)

    assert product.product_name == "test1"
    assert product.inventory == 0
    assert product.ideal_stock == 1
    assert product.lifetime_donated == 0

def test_update_product_stock(setup_inventory: Category):
    lysol = Product.get_product("lysol")
    individual = [StockUnitSubmission(None, "individual", 1, 1, 5)]
    lysol.update_stock(individual)
    assert lysol.inventory == 5

def test_update_product(setup_inventory: Category):
    lysol = Product.get_product("lysol")
    tubes = [StockUnitSubmission(None, "tubes", 5, 5, 5)]
    lysol.update_product("new lysol", tubes, 35)
    assert lysol.product_name == "new lysol"
    assert lysol.inventory == 25
    assert lysol.ideal_stock == 35

def test_delete_product(setup_inventory: Category):
    p = Product.get_product("dish soap")
    Product.delete_product(p.get_id())
    assert len(Product.all()) == 2

def test_product_levels(setup_inventory: Category):
    levels = Product.get_low_products()
    assert levels[0] == 1
    assert levels[1] == 1
    assert levels[2] == 1

def test_products_leq_quarter(setup_inventory: Category):
    products = Product.products_leq_quarter()
    assert len(products) == 1
    p = products[0]
    assert p.product_name == "clorox wipes"
    p.increment_notified() #simulate both emails being sent
    p.increment_notified()
    products = Product.products_leq_quarter()
    assert len(products) == 0

def test_products_leq_half(setup_inventory: Category):
    products = Product.products_leq_half()
    assert len(products) == 2
    p1 = products[0]
    p2 = products[1]
    assert p1.product_name == "clorox wipes"
    assert p2.product_name == "lysol"
    p1.increment_notified() #simulate email being sent
    p2.increment_notified()
    products_new = Product.products_leq_half()
    assert len(products_new) == 0

def test_add_stock(setup_inventory: Category):
    p = Product.get_product("lysol")
    individual = [StockUnitSubmission(None, "individual", 1, 1, 1)]
    p.add_stock(individual, True)
    assert p.inventory == 11
    assert p.lifetime_donated == 1
    p.add_stock(individual, False)
    assert p.inventory == 12
    assert p.lifetime_purchased == 1
    

    
    


