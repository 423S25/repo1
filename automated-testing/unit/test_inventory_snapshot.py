import pytest
from app import app
from src.model.product import Product, Category, InventorySnapshot

@pytest.fixture(autouse=True)
def setup_inventory():
    cat = Category.add_category("cleaning supplies", "test-color")
    Product.add_product("clorox wipes", 5, cat.get_id(), 5.00, "tubes", 10, False, None)
    Product.add_product("lysol", 1, cat.get_id(), 3.00, "bottles", 30, False, None)
    Product.add_product("dish soap", 10, cat.get_id(), 5.00, "bottles", 10, False, None)
    yield cat
    Category.delete_category(cat.get_id())

def test_list_snapshots(setup_inventory: Category):
    snapshots = InventorySnapshot.all()
    assert len(snapshots) == 3
    assert snapshots[0].inventory == 5
    assert snapshots[1].inventory == 1
    assert snapshots[2].inventory == 10

def test_create_snapshot(setup_inventory: Category):
    p = Product.get_product("lysol")
    InventorySnapshot.create_snapshot(p.get_id(), 2)
    snapshots = InventorySnapshot.all_of_product(p.get_id())
    assert snapshots[0].inventory == 2
    assert snapshots[1].inventory == 1

def test_delete_snapshot(setup_inventory: Category):
    p = Product.get_product("lysol")
    InventorySnapshot.delete_snapshots_for_product(p.get_id())
    assert len(InventorySnapshot.all_of_product(p.get_id())) == 0
    