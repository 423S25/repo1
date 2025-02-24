from flask import Flask, request, Response, render_template, redirect, abort, flash
from src.model.product import Product, InventorySnapshot, db

app = Flask(__name__, static_url_path='', static_folder='static')

with db:
    db.create_tables([Product, InventorySnapshot])

# This hook ensures that a connection is opened to handle any queries
# generated by the request.
@app.before_request
def _db_connect():
    db.connect()


# This hook ensures that the connection is closed when we've finished
# processing the request.
@app.teardown_request
def _db_close(exc):
    if not db.is_closed():
        db.close()



#NOTE: my IDE made me do it this way, can change to app.get if broken
@app.get("/")
def home():
    # Fills the days left for each product with product.get_days_until_out
    Product.fill_days_left()

    # Loads products in urgency order
    products = Product.urgency_rank()
    return render_template("index.html", product_list=products)

@app.get("/inventory-history")
def inventory_history():
    product_id = request.args.get('product-id', None, type=int)
    if product_id is None: # TODO: have actual error page
        return abort(404, description=f"Could not find product id")

    product = Product.get_product(product_id)
    if product is None: # TODO: have actual error page
        return abort(404, description=f"Could not find product {product_id}")

    snapshots = InventorySnapshot.all_of_product(product_id)
    usage = product.get_usage_per_day()
    days_until_out = product.get_days_until_out(usage)

    return render_template(
        "inventory_history.html",
        product=product,
        snapshots=snapshots,
        snapshot_count=len(snapshots),
        daily_usage=round(usage, 1) if usage is not None else None,
        days_until_out=round(days_until_out) if days_until_out is not None else None,
    )


@app.get("/add")
def get_add():
    return render_template("add_form.html")


#Simple add, just adds stuff + 1 works with htmx
#TODO: make this a form
@app.route("/add", methods=["POST"])
def add():
    products = Product.all()
    if Product.get_product(request.form.get("product_name")) is None:
        Product.add_product(request.form.get("product_name"), int(request.form.get("inventory")), float(request.form.get("price")), request.form.get("unit_type"), int(request.form.get("ideal_stock")), None)
        Product.fill_days_left()
        return redirect("/")
    else:
        abort(400)





@app.delete("/delete/<int:product_id>")
def delete(product_id: int):
    Product.delete_product(product_id)
    products = Product.urgency_rank()
    return render_template("index.html", product_list=products)


@app.route("/update/inventory/<int:product_id>", methods=["PATCH"])
def update_inventory(product_id: int):
    new_stock = request.form.get('stock', None, type=int)
    if new_stock is None or new_stock < 0:
        return abort(400, description="Stock count must be a positive integer")

    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f"Could not find product {product_id}")

    product.update_stock(new_stock)

    return redirect("/", 303)



if __name__ == '__main__':

    app.run(port=5000, debug=True)