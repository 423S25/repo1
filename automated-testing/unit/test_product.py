import pytest
from app import app
from src.model.product import Product, Category

@pytest.fixture(autouse=True)
def setup_inventory():
    cat = Category.add_category("cleaning supplies", "test-color", "/icons/cat_icons/Cleaning.svg")
    Product.add_product("clorox wipes", 5, cat.get_id(), 5.00, "tubes", 10, False, None)
    Product.add_product("lysol", 1, cat.get_id(), 3.00, "bottles", 30, False, None)
    Product.add_product("dish soap", 10, cat.get_id(), 5.00, "bottles", 10, False, None)
    yield cat
    Category.delete_category(cat.get_id())

def test_list_products(setup_inventory: Category):
    products = Product.all()
    assert len(products) == 3

def test_add_product(setup_inventory: Category):
    product = Product.add_product("test1", 1, setup_inventory.get_id(), 1, "test", 1, True, None)
    assert product.product_name == "test1"
    assert product.inventory == 1
    assert product.price == 1
    assert product.unit_type == "test"
    assert product.ideal_stock == 1
    assert product.lifetime_donated == 1

def test_update_product_stock(setup_inventory: Category):
    lysol = Product.get_product("lysol")
    lysol.update_stock(2)
    assert lysol.inventory == 2

def test_update_product(setup_inventory: Category):
    lysol = Product.get_product("lysol")
    lysol.update_product("new lysol", 5.00, "new bottles", 35)
    assert lysol.product_name == "new lysol"
    assert lysol.price == 5
    assert lysol.unit_type == "new bottles"
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
    assert p.product_name == "lysol"
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

def test_add_items(setup_inventory: Category):
    p = Product.get_product("lysol")
    p.add_items(10, True)
    assert p.inventory == 11
    assert p.lifetime_donated == 10
    p.add_items(10, False)
    assert p.inventory == 21
    assert p.lifetime_purchased == 11 #product was marked purchased when it was created
    

    
    


