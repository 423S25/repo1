import pytest
from app import app
from src.model.product import Product, Category

@pytest.fixture(autouse=True)
def setup_inventory():
    cat = Category.add_category("cleaning supplies", "test-color")
    Product.add_product("clorox wipes", 5, cat.get_id(), 5.00, "tubes", 10, False, None)
    Product.add_product("lysol", 1, cat.get_id(), 3.00, "bottles", 30, False, None)
    Product.add_product("dish soap", 10, cat.get_id(), 5.00, "bottles", 10, False, None)
    yield cat
    Category.delete_category(cat.get_id())

def test_add_product(setup_inventory: Category):
    product = Product.add_product("test1", 1, setup_inventory.get_id(), 1, "test", 1, True, None)
    assert product.product_name == "test1"
    assert product.inventory == 1
    assert product.price == 1
    assert product.unit_type == "test"
    assert product.ideal_stock == 1
    assert product.lifetime_donated == 1



