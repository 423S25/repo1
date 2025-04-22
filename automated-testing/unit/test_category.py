import pytest
from app import app
from src.model.product import Product, Category, StockUnitSubmission, StockUnit

@pytest.fixture(autouse=True)
def setup_inventory():
    cleaning_supplies = Category.add_category("cleaning supplies", "test-color", "/icons/cat_icons/Cleaning.svg")
    bedding = Category.add_category("bedding", "test-color-2", "/icons/cat_icons/Hygiene.svg")
    products: list[Product] = [
        Product.add_product("clorox wipes", cleaning_supplies.get_id(), 10),
        Product.add_product("lysol", cleaning_supplies.get_id(), 30),
        Product.add_product("dish soap", cleaning_supplies.get_id(), 10),
        Product.add_product("sleeping bags", bedding.get_id(), 10),
        Product.add_product("sheets", bedding.get_id(), 40)
    ]

    # Update the price and count to match the old test
    for index, product in enumerate(products):
        stock_unit_id = StockUnit.all_of_product(product_id=product.get_id())[0].get_id()
        submission = StockUnitSubmission(
            id=stock_unit_id,
            name="individual",
            multiplier=1,
            price=1,
            count=1 if index==0 or index==1 else 10
        )
        product.update_stock([submission])

    categories = []
    categories.append(cleaning_supplies)
    categories.append(bedding)
    yield
    new_cat_list = Category.all() #because we will update/delete new categories
    for cat in new_cat_list:
        Category.delete_category(cat.get_id())

def test_list_categories(setup_inventory: list['Category']):
    cats = Category.all()
    assert len(cats) == 2

def test_get_alphabetized(setup_inventory: list['Category']):
    cats = Category.all_alphabetized()
    assert len(cats) == 2
    assert cats[0].name == "bedding"
    assert cats[1].name == "cleaning supplies"

def test_add_category(setup_inventory: list['Category']):
    Category.add_category("test", "test-color-3", "/icons/cat_icons/Cleaning.svg")
    cat = Category.get_category("test")
    assert cat.name == "test"
    assert cat.color == "test-color-3"
    Category.delete_category(cat.get_id()) #delete because of unique constraints

def test_delete_category(setup_inventory: list['Category']):
    cat = Category.get_category("bedding")
    Category.delete_category(cat.get_id())
    assert len(Category.all()) == 1
    assert len(Product.all()) == 3 #products MUST get deleted too

def test_update_category(setup_inventory: list['Category']):
    cat = Category.get_category("bedding")
    cat.update_category("new bedding", "new-color")
    assert cat.name == "new bedding"
    assert cat.color == "new-color"

