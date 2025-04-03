import os, secrets
from flask import Flask, request, Response, render_template, redirect, abort, url_for, make_response

from src.model.product import Category
from src.model.product import Product, InventorySnapshot, db
from src.model.user import User, user_db
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
from flask_bcrypt import Bcrypt

from src.common.forms import LoginForm, ProductAddForm, ProductUpdateInventoryForm, ProductUpdateAllForm, parse_errors, clean_price_to_float, htmx_errors, htmx_redirect
from src.common.email_job import EmailJob

from user_agents import parse
import io
from PIL import Image
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, static_url_path='', static_folder='static')

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

bcrypt = Bcrypt(app)

app.config['SECRET_KEY'] = secrets.token_urlsafe()
app.config['SECRET_KEY'] = "asdf"
app.config["SESSION_PROTECTION"] = "strong"
UPLOAD_FOLDER = os.path.join("static", "images")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOADED_IMAGES'] = UPLOAD_FOLDER

def is_mobile():
    user_agent = parse(request.user_agent.string)
    return user_agent.is_mobile or user_agent.is_tablet

with db:
    db.create_tables([Category, Product, InventorySnapshot])

with user_db:
    user_db.create_tables([User])

#used by flask-login
@login_manager.user_loader
def load_user(user_id):
    user = User.get_by_uid(user_id)
    return user
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

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user is None or current_user.username != 'admin':
            return abort(401, description='Only admins can access this resource')
        else:
           return func(*args, **kwargs)
    return wrapper



###
# Served HTML pages
###



# The index page with the main product table
@app.get("/")
@login_required #any user can access home page
def home():
    if is_mobile():
        return redirect('/mobile', 303)
    # Fills the days left for each product with product.get_days_until_out
    Product.fill_days_left()
    # Loads products in urgency order
    category_id = request.args.get('category_id', default=0, type=int)  # Default to 0 if no category is selected
    if category_id == 0:
        products = Product.urgency_rank()
    else:
        products = Product.urgency_rank(category_id)
    categories = Category.all()
    levels = Product.get_low_products()
    flag = False
    return render_template("index.html", product_list=products, user=current_user,
                           categories=categories, current_category=category_id, levels=levels, flag = flag)

# The reports page for an overview of all products
@app.get("/reports")
@login_required
def reports():
    Product.fill_days_left()
    products = Product.urgency_rank()
    categories = [{"id": c.id, "name": c.name, "total_inventory": 0} for c in Category.all()]

    # Create a mapping from category ID to total inventory
    category_inventory = {c["id"]: 0 for c in categories}

    # Sum up inventory for each product's category
    for product in products:
        if product.category_id in category_inventory:
            category_inventory[product.category_id] += product.inventory

    # Update category objects with total inventory values
    for category in categories:
        category["total_inventory"] = category_inventory[category["id"]]

    flag = True
    return render_template("reports_index.html", product_list=products, user=current_user, categories=categories, quant=[c["total_inventory"] for c in categories], flag=flag)

# The search function for the main table page. Re-serves index.html
@app.get("/search")
def search():
    category_id = request.args.get('category_id', default=0, type=int)
    search_term = request.args.get('q', '')
    if search_term:
        products = Product.search(search_term)
    else:
        products = Product.all()
    categories = Category.all()
    return render_template("table.html", product_list=products, user=current_user, categories=categories, current_category=category_id)

# The filter function for the main table page. Re-serves index.html
@app.post("/filter")
@login_required
def filter():
    category_id = int(request.form.get('category_id'))
    # Fills the days left for each product with product.get_days_until_out
    Product.fill_days_left()
    # Loads products in urgency order using where for category filter
    if category_id == 0:
        products = Product.urgency_rank()
    else:
        products = Product.urgency_rank(category_id)
    categories = Category.all()
    levels = Product.get_low_products()
    return render_template("index.html", product_list=products, user=current_user, categories=categories, current_category=category_id, levels=levels)

# The individual page for each product
@app.get("/<int:product_id>")
@login_required #any user can access this page
def inventory_history(product_id: int):

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
        user=current_user,
        filepath = product.image_path
    )

# Admin settings page
@app.get("/settings")
@admin_required
def get_settings():
    if current_user.username != 'admin':
        return abort(401, description='Only admins can access admin settings')
    return render_template("settings.html", user=current_user)



###
# Served mobile HTML pages
###



# The mobile home page
@app.get("/mobile")
@login_required
def render_mobile_home_page():
    categories = [
        Category.ALL_PRODUCTS_PLACEHOLDER,
        *Category.all_alphabetized()
    ]
    return render_template("mobile_index.html", category_list=categories)

# The mobile category pages
@app.get("/mobile-category")
@login_required
def render_mobile_category_page():
    category_id = request.args.get('category_id', type=int)
    if category_id == Category.ALL_PRODUCTS_PLACEHOLDER['id']:
        category_id = None
    category = Category.ALL_PRODUCTS_PLACEHOLDER if category_id is None or category_id == 0 else Category.get_category(category_id)
    products = Product.alphabetized_of_category(category_id)
    return render_template("mobile_category.html", product_list=products, category=category)



###
# Login and logout POST endpoints
###



# Logout a user
@app.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))

# Login a user
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    next = request.args.get('next')
    errors = [] #used to display errors on the login page
    if form.validate_on_submit(): #makes sure form is complete
        user = User.get_by_username(form.username.data.lower())
        if user is None:
            errors.append("User not found")
            return render_template('security/login.html', form=form, errors=errors)
        correct_password = bcrypt.check_password_hash(user.password, form.password.data)
        if not correct_password:
            errors.append("Incorrect password")
            return render_template('security/login.html', form=form, errors=errors)
        login_success = login_user(user)
        if not login_success:
            errors.append("Login failed")
            return render_template('security/login.html', form=form, errors=errors)
        return redirect(next or url_for("home"))
    return render_template('security/login.html', form=form, errors=errors)

# Add a new email to updates for admin only
@app.post("/settings")
@admin_required
def update_settings():
    if current_user.username != 'admin':
        return abort(401, description='Only admins can access admin settings')
    email = request.form.get("email")
    User.get_by_username('admin').update_email(email)
    return redirect("/settings")



###
# Product CRUD endpoints
###



# Create a new product
@app.get('/product_add')
@admin_required
def product_add_form():
    form = ProductAddForm()
    categories = Category.all_alphabetized()
    return render_template('modals/product_add.html', form=form, categories=categories)

# Create a new product
@app.post('/product_add')
@admin_required
def product_add_action():
    form = ProductAddForm()
    form.validate()
    form_errors: list[str] = parse_errors(form)

    maybe_price_float = clean_price_to_float(form.price.data) #allow '$' in price field
    if maybe_price_float is None:
        form_errors.append('Price could not be converted to number')

    if not form.category_id.errors and Category.get_category(form.category_id.data) is None:
        form_errors.append(f'No category with id {form.category_id.data}')

    if len(form_errors) == 0: #add to database
        Product.add_product(request.form.get("product_name"),
            form.inventory.data,
            form.category_id.data,
            maybe_price_float,
            form.unit_type.data,
            form.ideal_stock.data,
            form.donation.data,
            None
        )
        Product.fill_days_left()
        EmailJob.process_emails(User.get_by_username('admin').email)
        return htmx_redirect('/')
    else:
        return htmx_errors(form_errors)

# Delete a product
@app.delete("/product_delete/<int:product_id>")
@admin_required
def delete(product_id: int):
    Product.delete_product(product_id)
    return redirect('/')

# Add an image for a product
@app.post("/product_upload_image/<int:product_id>")
@login_required
def upload_image(product_id: int):
    if 'file' not in request.files:
        return redirect('/' + str(product_id))

    file = request.files['file']
    product = Product.get_product(product_id)
    if file.filename == '':
        return redirect('/' + str(product_id))

    is_valid_image = True
    filename = file.filename
    try:
        img_stream = io.BytesIO(file.read())
        image = Image.open(img_stream)
        is_valid_image = image.verify() is None
    except:
        is_valid_image = False

    if is_valid_image:
        file.save(os.path.join(app.config['UPLOADED_IMAGES'], filename))
        product.set_img_path(filename)

    return redirect("/" + str(product_id))

# Form to update stock only for a given product in product inventory_history.html
@app.get("/product_update_inventory/<int:product_id>")
@login_required
def load_update(product_id: int):
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f'No product found with id {product_id}')
    return render_template("modals/product_update_stock.html", product=product, form=ProductUpdateInventoryForm())

# Update inventory only for desktop
@app.post("/product_update_inventory/<int:product_id>")
@login_required #any user can update inventory
def update_inventory(product_id: int):
    if request.form.get('_method') == 'PATCH':
        form = ProductUpdateInventoryForm()
        form_errors = parse_errors(form)

        product = Product.get_product(product_id)
        if product is None:
            form_errors.append(f"Could not find product {product_id}")
        
        if len(form_errors) == 0:
            product.update_stock(form.stock.data)
            product.mark_not_notified()
            EmailJob.process_emails(User.get_by_username('admin').email)
            return htmx_redirect("/" + str(product_id))
        else:
            return htmx_errors(form_errors)
    else:
        return abort(405, description="Method Not Allowed")

@app.get("/product_update_inventory_mobile/<int:product_id>")
@login_required
def load_update_mobile(product_id: int):
    product = Product.get_product(product_id)
    return render_template("modals/product_update_stock_mobile.html", product=product, form=ProductUpdateInventoryForm())

# Update inventory only for mobile
@app.post("/product_update_inventory_mobile/<int:product_id>")
@login_required #any user can update inventory
def update_inventory_mobile(product_id: int):
    return update_inventory(product_id)

@app.get("/product_update_all/<int:product_id>")
@admin_required
def load_update_all(product_id: int):
    product = Product.get_product(product_id)
    return render_template("modals/product_update_all.html", product=product, form=ProductUpdateAllForm())

# Update any/all aspect of a product
@app.post("/product_update_all/<int:product_id>")
@admin_required
def update_all(product_id: int):
    if request.form.get('_method') == 'PATCH':
        form = ProductUpdateAllForm()
        form_errors = parse_errors(form)

        product = Product.get_product(product_id)
        if product is None:
            form_errors.append(f'No product found with id {product_id}')

        price = clean_price_to_float(form.price.data)
        if price is None:
            form_errors.append(f'Price "{form.price.data}" cound not be converted to a number')
        
        if len(form_errors) == 0:
            product_name = form.product_name.data
            unit_type = form.unit_type.data
            ideal_stock = form.ideal_stock.data

            product.update_product(product_name, float(price), unit_type, int(ideal_stock))
            Product.fill_days_left()
            product.mark_not_notified()
            EmailJob.process_emails(User.get_by_username('admin').email)
            return htmx_redirect("/" + str(product_id))
        else:
            return htmx_errors(form_errors)
    else:
        return abort(405, description="Method Not Allowed")

# Change a product's category
@app.route("/update_category/<int:category_id>", methods=["POST"])
@admin_required #admin only
def update_category(category_id: int):
    if request.form.get('_method') == 'PATCH':
        category = Category.get_category(category_id)
        if category is None:
            return abort(404, description=f"Could not find product {category.id}")

        category_name = request.form.get("category_name")
        category_color = request.form.get("category_color")
        category.update_category(category_name, category_color)

        return redirect("/", 303)
    else:
        return abort(405, description="Method Not Allowed")

# Update the lifetime donated amount and maybe updates stock as well
@app.route("/update_donated/<int:product_id>", methods=["POST"])
@admin_required
def update_donated(product_id: int):
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f'Cound not find product with id {product_id}')
    amount: int = int(request.form.get("donated_amount"))
    adjust_stock: bool = bool(request.form.get("adjust_stock"))
    diff: int = amount - product.lifetime_donated
    if adjust_stock and diff < 0 and -diff > product.inventory:
        return abort(400, description="action would produce a negative stock level") 
    product.set_donated(amount, adjust_stock)
    return redirect(f"/{product_id}")

# Update the lifetime purchased amount and maybe updates stock as well
@app.route("/update_purchased/<int:product_id>", methods=["POST"])
@admin_required
def update_purchased(product_id: int):
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f'Cannot find product with id {product_id}')
    amount: int = int(request.form.get("purchased_amount"))
    adjust_stock: bool = bool(request.form.get("adjust_stock"))
    diff: int = amount - product.lifetime_purchased
    if adjust_stock and diff < 0 and -diff > product.inventory:
        return abort(400, description="action would produce a negative stock level") 
    product.set_purchased(amount, adjust_stock)
    return redirect(f"/{product_id}")



###
# Category CRUD endpoints
###



# Create a new category
@app.route("/add_category", methods=["POST"])
@admin_required
def add_category():
    if Category.get_category(request.form.get("category_name")) is None:
        Category.add_category(request.form.get("category_name"), (request.form.get("category_color")))
    else:
        abort(400)
    return redirect("/")

# Delete a category
@app.delete("/delete_category/<int:category_id>")
@admin_required
def delete_category(category_id: int):
    Category.delete_category(category_id)
    products = Product.urgency_rank()
    categories = Category.all()
    category_id = request.args.get('category_id', default=0, type=int)
    levels = Product.get_low_products()
    return render_template("index.html", product_list=products, user=current_user, categories=categories, current_category=category_id, levels=levels)



###
# Downloads/Exports
###



@app.get("/export_csv")
@admin_required
def export_csv():
    csv_file = Product.get_csv()
    response = Response(csv_file, content_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=products.csv"
    return response



###
# Served modals
###



# Add new product modal for main table page
# @app.get("/add")
# @login_required
# def get_add():
#     #only admin can add products
#     if current_user.username != 'admin':
#         return abort(401, description='Only admins can add products')
#     return render_template("add_form.html")

# Form to update lifetime donated in product inventory_history.html
@app.get("/load_update_donated/<int:product_id>")
@admin_required
def load_update_donated(product_id: int):
    product = Product.get_product(product_id)
    return render_template("modals/update_donated.html", product=product)

# Form to update lifetime purchased in product inventory_history.html
@app.get("/load_update_purchased/<int:product_id>")
@admin_required
def load_update_purchased(product_id: int):
    product = Product.get_product(product_id)
    return render_template("modals/update_purchased.html", product=product)

# # Form to update stock only for a given product in product inventory_history.html
# @app.get("/load_update/<int:product_id>")
# @login_required
# def load_update(product_id: int):
#     product = Product.get_product(product_id)
#     return render_template("modals/update_stock.html", product=product)

# Form to update stock only on mobile for a given product in product mobile_category.html
# @app.get("/load_update_mobile/<int:product_id>")
# @login_required
# def load_update_mobile(product_id: int):
#     product = Product.get_product(product_id)
#     return render_template("modals/update_stock_mobile.html", product=product)

# Form to update any aspect of a product for admin only in product mobile_category.html
# @app.get("/load_update_all/<int:product_id>")
# @login_required
# def load_update_all(product_id: int):
#     if current_user.username != 'admin':
#         return abort(401, description='Only admins can access this feature.')
#     product = Product.get_product(product_id)
#     return render_template("modals/product_update_all.html", product=product)

# Form to add a new product for admin only in main table page
@app.get("/load_add")
@admin_required
def load_add():
    categories = Category.all()
    return render_template("modals/product_add.html", categories=categories)

# Form to add a new category for admin only in main table page
@app.get("/load_add_category")
@admin_required
def load_add_color():
    return render_template("modals/add_category.html")

# Form to edit a category for admin only in main table page
@app.get("/load_edit_category/<int:category_id>")
@admin_required
def load_edit_category(category_id: int):
    category = Category.get_category(category_id)
    return render_template("modals/edit_category.html", category=category)



with app.app_context():
    if not User.get_by_username('admin'):
        User.add_user('admin', bcrypt.generate_password_hash(os.environ.get("ADMIN_PASSWORD")))
    if not User.get_by_username('staff'):
        User.add_user('staff', bcrypt.generate_password_hash(os.environ.get("STAFF_PASSWORD")))
    if not User.get_by_username('volunteer'):
        User.add_user('volunteer', bcrypt.generate_password_hash(os.environ.get("VOLUNTEER_PASSWORD")))

if __name__ == '__main__':
    app.run(port=5000, debug=True)