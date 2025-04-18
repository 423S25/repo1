import pytest
from app import app
from src.model.product import Product, Category, StockUnitSubmission

@pytest.fixture(autouse=True)
def setup_inventory():
    cleaning_supplies = Category.add_category("cleaning supplies", "test-color", "/icons/cat_icons/Cleaning.svg")
    bedding = Category.add_category("bedding", "test-color-2", "/icons/cat_icons/Hygiene.svg")
    individual1 = [StockUnitSubmission(None, "individual", 1, 1, 1)]
    individual2 = [StockUnitSubmission(None, "individual", 1, 1, 10)]
    Product.add_product("clorox wipes", individual1, cleaning_supplies.get_id(), 10, False, None)
    Product.add_product("lysol", individual1, cleaning_supplies.get_id(), 30, False, None)
    Product.add_product("dish soap", individual2, cleaning_supplies.get_id(), 10, False, None)
    Product.add_product("sleeping bags", individual2, bedding.get_id(), 10, False, None)
    Product.add_product("sheets", individual2, bedding.get_id(), 40, False, None)    
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

