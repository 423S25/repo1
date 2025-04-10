import pytest
from app import app
from src.model.product import Product, Category, InventorySnapshot, StockUnitSubmission

@pytest.fixture(autouse=True)
def setup_inventory():
    cat = Category.add_category("cleaning supplies", "test-color", "/icons/cat_icons/Cleaning.svg")
    individual1 = [StockUnitSubmission(None, "individual", 1, 1, 1)]
    individual2 = [StockUnitSubmission(None, "individual", 1, 1, 10)]
    Product.add_product("clorox wipes", individual1, cat.get_id(), 10, False, None)
    Product.add_product("lysol", individual2, cat.get_id(), 30, False, None)
    Product.add_product("dish soap", individual2, cat.get_id(), 10, False, None)
    yield cat
    Category.delete_category(cat.get_id())

def test_list_snapshots(setup_inventory: Category):
    snapshots = InventorySnapshot.all()
    assert len(snapshots) == 3
    assert snapshots[0].individual_inventory == 1
    assert snapshots[1].individual_inventory == 10
    assert snapshots[2].individual_inventory == 10

def test_create_snapshot(setup_inventory: Category):
    p = Product.get_product("lysol")
    InventorySnapshot.create_snapshot(p.get_id(), 2, 5)
    snapshots = InventorySnapshot.all_of_product(p.get_id())
    assert snapshots[0].individual_inventory == 2
    assert snapshots[1].individual_inventory == 10
    assert snapshots[1].value_at_time == 10

def test_delete_snapshot(setup_inventory: Category):
    p = Product.get_product("lysol")
    InventorySnapshot.delete_snapshots_for_product(p.get_id())
    assert len(InventorySnapshot.all_of_product(p.get_id())) == 0
    