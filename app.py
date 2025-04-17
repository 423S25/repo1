import os
from src.common.functions import helper
from user_agents import parse
import io
from PIL import Image
from functools import wraps

from flask import Flask, request, Response, render_template, redirect, abort, send_from_directory, url_for, make_response
from flask_wtf import FlaskForm
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
from flask_bcrypt import Bcrypt

from src.model.product import Product, InventorySnapshot, Category, StockUnit, db
from src.model.user import User, user_db
from src.common.forms import LoginForm, ProductAddForm, ProductUpdateAllForm, ProductUpdatePurchasedForm, ProductUpdateDonatedForm, parse_errors, htmx_errors, htmx_redirect, CategoryUpdateAllForm, CategoryAddForm, ProductAddInventoryForm, parse_stock_units, TimeFrameForm, parse_timeframe_form_errors
from src.common.email_job import EmailJob

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, static_url_path='', static_folder='static')

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

bcrypt = Bcrypt(app)

app.config['SECRET_KEY'] = os.environ.get("APP_SECRET_KEY", "default")
app.config["SESSION_PROTECTION"] = "strong"
UPLOAD_FOLDER = os.path.join("static", "images")
os.makedirs(UPLOAD_FOLDER, exist_ok=True) #NOTE: maybe remove when presistent storage gets added
app.config['UPLOADED_IMAGES'] = UPLOAD_FOLDER

def is_mobile():
    user_agent = parse(request.user_agent.string)
    return user_agent.is_mobile or user_agent.is_tablet

with db:
    db.create_tables([Category, Product, InventorySnapshot, StockUnit])

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
        if not current_user.is_authenticated or getattr(current_user, "username", None) != "admin":
            return abort(401, description="Only admins can access this resource")
        else:
           return func(*args, **kwargs)
    return wrapper

###
# Served HTML pages
###

# The index page with the main product table
@app.get("/")
@login_required #any user can access home page
def get_index():
    if is_mobile():
        return redirect('/mobile')
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
    return render_template(
        "index.html",
        product_list=products,
        user=current_user,
        categories=categories,
        current_category=category_id,
        levels=levels,
        flag=False
    )

# The filter function for the main table page. Re-serves index.html
@app.post("/filter")
@login_required
def post_filter():
    category_id = request.args.get('category_id')
    price = request.args.get('price')
    amount = request.args.get('amount')
    # Fills the days left for each product with product.get_days_until_out
    Product.fill_days_left()
    # I do not think it does urgency ranking anymore. just loads the products that fit the filters
    products = Product.urgency_rank(category_id, price, amount)
    categories = Category.all()
    levels = Product.get_low_products()
    return render_template("index.html",
                           product_list=products,
                           user=current_user,
                           categories=categories,
                           current_category=category_id,
                           current_price=price,
                           current_amount=amount,
                           levels=levels)

# The filter function for the main table page. Re-serves index.html
@app.get("/filter")
@login_required
def get_filter():
    category_id = request.args.get('category_id', '0')
    price = request.args.get('price', '0')
    amount = request.args.get('amount', '0')
    search_term = request.args.get('q', '')
    ideal = request.args.get('ideal', '0')
    # I do not think it does urgency ranking anymore. just loads the products that fit the filters
    products = Product.urgency_rank(category_id, price, amount, search_term, ideal)
    categories = Category.all()
    levels = Product.get_low_products()
    return render_template("table.html",
                           product_list=products,
                           user=current_user,
                           categories=categories,
                           current_category=category_id,
                           current_price=price,
                           current_amount=amount,
                           levels=levels,
                           ideal=ideal)

# The reports page for an overview of all products
@app.get("/reports")
@admin_required
def get_reports():
    Product.fill_days_left()
    products = Product.urgency_rank()
    categories = [{"id": c.id, "name": c.name, "total_inventory": 0, "color": c.color} for c in Category.all()]

    # Create a mapping from category ID to total inventory
    category_inventory = {c["id"]: 0 for c in categories}
    category_price = {c["id"]: 0 for c in categories}
    # Sum up inventory for each product's category
    for product in products:
        if product.category_id in category_inventory:
            category_inventory[product.category_id] += product.inventory
            category_price[product.category_id] += product.price

    # Update category objects with total inventory values
    colors = []
    for category in categories:
        category["total_inventory"] = category_inventory[category["id"]]
        category["price"] = category_price[category["id"]]
        colors.append(category["color"])
    data1 = helper.price_over_amount_inventory(helper)
    data2 = helper.convert_to_rgb(helper, colors)
    data3 = helper.ideal_over_amount_inventory(helper)
    chart_data = helper.get_inventory_chart_data(helper)
    return render_template(
        "reports_index.html",
        product_list=products,
        user=current_user,
        categories=categories,
        quant=[c["total_inventory"] for c in categories],
        price=[c["price"] for c in categories],
        value=request.args.get('value'),
        data1=data1,
        data2=data2,
        data3=data3,
        chart_data=chart_data,
        Flag = True
    )

# The search function for the main table page. Re-serves index.html
@app.get("/search")
def get_search():
    category_id = request.args.get('category_id', default=0, type=int)
    search_term = request.args.get('q', '')
    if search_term:
        products = Product.search(search_term)
    else:
        products = Product.all()
    categories = Category.all()
    return render_template("table.html",
        product_list=products,
        user=current_user,
        categories=categories,
        current_category=category_id
    )

# The individual page for each product
@app.get("/<int:product_id>")
@login_required #any user can access this page
def get_product_page(product_id: int):
    if is_mobile():
        return redirect("/mobile")

    if product_id is None:
        return abort(404, description=f"Could not find product id")
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f"Could not find product {product_id}")

    product_list = Product.search_filter_and_sort(product_force_first=product_id, product_sort_method='alpha_a_z')
    hidden_count = 0
    if len(product_list) > 10:
        hidden_count = len(product_list) - 10
        product_list = product_list[0:10]
    stock_units_with_counts = StockUnit.all_of_product_with_count(product)
    all_time_snapshots = InventorySnapshot.all_of_product(product_id)

    # usage = product.get_usage_per_day()
    # days_until_out = product.get_days_until_out(usage)

    dates: list[str] = [rs.timestamp.strftime('%Y-%m-%d') for rs in all_time_snapshots]
    prices: list[str] = [rs.get_average_price() for rs in all_time_snapshots]
    counts: list[str] = [rs.individual_inventory for rs in all_time_snapshots]

    categories = [
        Category.ALL_PRODUCTS_PLACEHOLDER,
        *Category.all_alphabetized()
    ]

    return render_template(
        "inventory_history.html",
        product_list=product_list,
        filepath=product.image_path,
        stock_units_with_counts=stock_units_with_counts,
        product=product,
        lifetime_donated=product.lifetime_donated,
        lifetime_purchased=product.lifetime_purchased,
        dates=dates,
        prices=prices,
        counts=counts,
        category_list=categories,
        table_mode='link',
        hidden_count=hidden_count
    )

###
# Served mobile HTML pages
###

# The mobile home page
@app.get("/mobile")
@login_required
def get_mobile_index():
    if not is_mobile():
        return redirect("/")
    categories = [
        Category.ALL_PRODUCTS_PLACEHOLDER,
        *Category.all_alphabetized()
    ]
    products = Product.alphabetized_of_category()
    products = list(sorted(products, key=lambda p: p.last_updated))
    return render_template("mobile_index.html", category_list=categories, product_list=products)

###
# Product data endpoints
###

@app.get("/product_lifetime/<int:product_id>")
def get_lifetime_of_product(product_id: int):
    if product_id is None:
        return abort(404, description=f"Could not find product id")
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f"Could not find product {product_id}")

    form = TimeFrameForm(request.args, meta={'csrf': False})
    errors, start, end = parse_timeframe_form_errors(form)

    if len(errors) == 0 and start is not None and end is not None:
        relevant_snapshots = InventorySnapshot.all_of_product_in_time_period(product_id, start, end)
        if len(relevant_snapshots) == 0:
            return make_response('No Data', 200)
        
        lifetime_donated = 0
        lifetime_purchased = 0
        for snapshot in relevant_snapshots:
            lifetime_donated += snapshot.added_donated
            lifetime_purchased += snapshot.added_purchased
        if lifetime_purchased + lifetime_donated == 0:
            return make_response('No Data', 200)
        
        return render_template('charts/lifetime_split.html', lifetime_donated=lifetime_donated, lifetime_purchased=lifetime_purchased)
    else:
        return htmx_errors(errors)

@app.get("/product_price_history/<int:product_id>")
def get_price_history_of_product(product_id: int):
    if product_id is None:
        return abort(404, description=f"Could not find product id")
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f"Could not find product {product_id}")
    
    form = TimeFrameForm(request.args, meta={'csrf': False})
    errors, start, end = parse_timeframe_form_errors(form)

    if len(errors) == 0 and start is not None and end is not None:
        relevant_snapshots = InventorySnapshot.all_of_product_in_time_period(product_id, start, end)
        dates: list[str] = [rs.timestamp.strftime('%Y-%m-%d') for rs in relevant_snapshots]
        prices: list[str] = [rs.get_average_price() for rs in relevant_snapshots]
        return render_template(
            "charts/price_line_chart.html",
            prices=prices,
            dates=dates
        )
    else:
        return htmx_errors(errors)

@app.get("/product_inventory_history/<int:product_id>")
def get_inventory_history_of_product(product_id: int):
    if product_id is None:
        return abort(404, description=f"Could not find product id")
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f"Could not find product {product_id}")
    
    form = TimeFrameForm(request.args, meta={'csrf': False})
    errors, start, end = parse_timeframe_form_errors(form)

    if len(errors) == 0 and start is not None and end is not None:
        relevant_snapshots = InventorySnapshot.all_of_product_in_time_period(product_id, start, end)
        dates: list[str] = [rs.timestamp.strftime('%Y-%m-%d') for rs in relevant_snapshots]
        counts: list[str] = [rs.individual_inventory for rs in relevant_snapshots]
        return render_template(
            "charts/inventory_line_chart.html",
            counts=counts,
            dates=dates
        )
    else:
        return htmx_errors(errors)

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
        return redirect(next or url_for("get_index"))
    return render_template('security/login.html', form=form, errors=errors)

# Admin settings page
@app.get("/settings")
@admin_required
def get_settings():
    return render_template("settings.html", user=current_user)

# Add a new email to updates for admin only
@app.post("/settings")
@admin_required
def post_settings():
    email = request.form.get("email")
    if email is not None and email != '' and '@' in email:
        User.get_by_username('admin').update_email(email)
    return redirect("/settings")

#####
#
# PRODUCTS
#
#####

###
# Create/add product
###

# Create a new product
@app.get('/product_add')
@admin_required
def get_product_add():
    form = ProductAddForm()
    categories = Category.all_alphabetized()
    return render_template(
        'modals/product_add.html',
        form=form,
        categories=categories,
        stock_unit_list=[StockUnit.PLACEHOLDER],
    )

# Create a new product
@app.post('/product_add')
@admin_required
def post_product_add():
    form = ProductAddForm()
    form_errors = parse_errors(form)

    if not form.category_id.errors and Category.get_category(form.category_id.data) is None:
        form_errors.append(f'No category with id {form.category_id.data}')

    CATEGORY_MESSAGE = '"Category Id" must be an integer'
    if CATEGORY_MESSAGE in form_errors:
        form_errors[form_errors.index(CATEGORY_MESSAGE)] = 'Please select a category'

    stock_units = parse_stock_units(request.form, form_errors, True)

    if len(form_errors) == 0: #add to database
        Product.add_product(
            form.product_name.data,
            stock_units,
            form.category_id.data,
            form.ideal_stock.data,
            form.donation.data,
            None
        )
        Product.fill_days_left()
        EmailJob.process_emails(User.get_by_username('admin').email)
        return htmx_redirect('/')
    else:
        return htmx_errors(form_errors)

###
# Delete product
###

# Delete a product
@app.delete("/product_delete/<int:product_id>")
@admin_required
def post_delete_product(product_id: int):
    Product.delete_product(product_id)
    return htmx_redirect('/')

###
# Set image of product
###

# Add an image for a product
@app.post("/product_upload_image/<int:product_id>")
@login_required
def post_product_upload_image(product_id: int):
    if 'file' not in request.files:
        return make_response('No file in form', 400)

    file = request.files['file']
    product = Product.get_product(product_id)
    if file.filename == '':
        return make_response('Filename could not be found', 400)

    try:
        img = Image.open(io.BytesIO(file.read()))
        img.verify() # Verify it's an image
        file.seek(0) # Reset file pointer after reading

        filename = file.filename
        file.save(os.path.join(app.config['UPLOADED_IMAGES'], filename))
        product.set_img_path(filename)
        return htmx_redirect("../" + str(product_id))
    except:
        return make_response('File is not an image', 400)

###
# Set stock/inventory of product
###

# Form to update stock only for a given product in product inventory_history.html
@app.get("/product_update_inventory/<int:product_id>")
@admin_required
def get_product_update_inventory(product_id: int):
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f'No product found with id {product_id}')
    stock_units = StockUnit.all_of_product(product_id)
    stock_unit_ids = list(map(lambda x: x.get_id(), stock_units))
    stock_unit_counts = [0] * len(stock_units)
    for unit_id, count in product.get_inventory_breakdown():
        try:
            index = stock_unit_ids.index(unit_id)
            stock_unit_counts[index] = count
        except:
            pass
    return render_template(
        "modals/product_update_stock.html",
        product=product,
        form=FlaskForm(),
        stock_unit_list=stock_units,
        stock_unit_count_list=stock_unit_counts
    )

# Update inventory only for desktop
@app.post("/product_update_inventory/<int:product_id>")
@admin_required
def post_product_update_inventory(product_id: int):
    if request.form.get('_method') == 'PATCH':
        form = FlaskForm()
        form_errors = parse_errors(form)
        stock_units = parse_stock_units(request.form, form_errors, True)

        product = Product.get_product(product_id)
        if product is None:
            form_errors.append(f"Could not find product {product_id}")
        
        if len(form_errors) == 0:
            product.update_stock(stock_units)
            product.mark_not_notified()
            EmailJob.process_emails(User.get_by_username('admin').email)
            return htmx_redirect("/" + str(product_id))
        else:
            return htmx_errors(form_errors)
    else:
        return abort(405, description="Method Not Allowed")

# Form to add inventory whether purchased or donated only for a given product in product inventory_history.html
@app.get("/product_add_inventory/<int:product_id>")
@admin_required
def get_product_add_inventory(product_id: int):
    product = Product.get_product(product_id)
    if product is None:
        return abort(404, description=f'No product found with id {product_id}')
    stock_units = StockUnit.all_of_product(product_id)
    return render_template(
        "modals/product_add_stock.html",
        product=product,
        form=FlaskForm(),
        stock_unit_list=stock_units
    )

# Add inventory only for desktop
@app.post("/product_add_inventory/<int:product_id>")
@admin_required
def post_product_add_inventory(product_id: int):
    if request.form.get('_method') == 'PATCH':
        form = ProductAddInventoryForm()
        form_errors = parse_errors(form)
        stock_unit_submissions = parse_stock_units(request.form, form_errors, True)

        product = Product.get_product(product_id)
        if product is None:
            form_errors.append(f"Could not find product {product_id}")
        
        if len(form_errors) == 0:
            product.add_stock(stock_unit_submissions, form.donation.data)
            product.mark_not_notified()
            EmailJob.process_emails(User.get_by_username('admin').email)
            return htmx_redirect("/" + str(product_id))
        else:
            return htmx_errors(form_errors)
    else:
        return abort(405, description="Method Not Allowed")

@app.get("/product_update_inventory_mobile/<int:product_id>")
@login_required
def get_product_update_inventory_mobile(product_id: int):
    product = Product.get_product(product_id)
    return render_template(
        "modals/product_update_stock_mobile.html",
        product=product,
        form=FlaskForm(),
        stock_unit_list=StockUnit.all_of_product(product_id)
    )

# Update inventory only for mobile
@app.post("/product_update_inventory_mobile/<int:product_id>")
@login_required
def post_product_update_inventory_mobile(product_id: int):
    if request.form.get('_method') == 'PATCH':
        form = FlaskForm()
        form_errors = parse_errors(form)

        stock_unit_submissions = parse_stock_units(request.form, form_errors, True)

        product = Product.get_product(product_id)
        if product is None:
            form_errors.append(f"Could not find product {product_id}")
        
        if len(form_errors) == 0:
            product.update_stock(stock_unit_submissions)
            product.mark_not_notified()
            EmailJob.process_emails(User.get_by_username('admin').email)
            return htmx_redirect("/mobile")
        else:
            return htmx_errors(form_errors)
    else:
        return abort(405, description="Method Not Allowed")

###
# Update any/all aspects of product
###

@app.get("/product_update_all/<int:product_id>")
@admin_required
def get_product_update_all(product_id: int):
    product = Product.get_product(product_id)
    stock_units = StockUnit.all_of_product(product.get_id())
    stock_unit_ids = list(map(lambda x: x.get_id(), stock_units))
    stock_unit_counts = [0] * len(stock_units)
    for unit_id, count in product.get_inventory_breakdown():
        try:
            index = stock_unit_ids.index(unit_id)
            stock_unit_counts[index] = count
        except:
            pass
    return render_template(
        "modals/product_update_all.html",
        product=product,
        form=ProductUpdateAllForm(),
        stock_unit_list=stock_units,
        stock_unit_count_list=stock_unit_counts,
        stock_unit_count_hidden=True
    )

@app.post("/product_update_all/<int:product_id>")
@admin_required
def post_product_update_all(product_id: int):
    if request.form.get('_method') == 'PATCH':
        form = ProductUpdateAllForm()
        form_errors = parse_errors(form)

        product = Product.get_product(product_id)
        if product is None:
            form_errors.append(f'No product found with id {product_id}')

        possible_conflicing_product = Product.get_product(form.product_name.data)
        if product.product_name != form.product_name.data and possible_conflicing_product is not None:
            form_errors.append(f'Product already exists with name "{form.product_name.data}"')

        stock_units = parse_stock_units(request.form, form_errors, True)
        print(stock_units, request.form)
        
        if len(form_errors) == 0:
            product_name = form.product_name.data
            ideal_stock = form.ideal_stock.data

            product.update_product(product_name, stock_units, ideal_stock)
            Product.fill_days_left()
            product.mark_not_notified()
            EmailJob.process_emails(User.get_by_username('admin').email)
            return htmx_redirect("/" + str(product_id))
        else:
            return htmx_errors(form_errors)
    else:
        return abort(405, description="Method Not Allowed")

###
# Update lifetime stats of product
###

# Form to update lifetime donated in product inventory_history.html
@app.get("/product_update_donated/<int:product_id>")
@admin_required
def get_product_update_donated(product_id: int):
    product = Product.get_product(product_id)
    return render_template("modals/product_update_donated.html", product=product, form=ProductUpdateDonatedForm())

# Form to update lifetime purchased in product inventory_history.html
@app.get("/product_update_purchased/<int:product_id>")
@admin_required
def get_product_update_purchased(product_id: int):
    product = Product.get_product(product_id)
    return render_template("modals/product_update_purchased.html", product=product, form=ProductUpdatePurchasedForm())

# Update the lifetime donated amount and maybe updates stock as well
@app.post("/product_update_donated/<int:product_id>")
@admin_required
def post_product_update_donated(product_id: int):
    form = ProductUpdateDonatedForm()
    form_errors = parse_errors(form)

    product = Product.get_product(product_id)
    if product is None:
        form_errors.append(f'Cound not find product with id {product_id}')
    amount: int = form.donated_amount.data
    adjust_stock: bool = form.adjust_stock.data
    diff: int = amount - (product.lifetime_donated or 0) # product.lifetime_donated can be None
    if adjust_stock and diff < 0 and -diff > product.inventory:
        form_errors.append("Action would produce a negative stock level")

    if len(form_errors) == 0:
        product.set_donated(amount, adjust_stock)
        return htmx_redirect(f"/{product_id}")
    else:
        return htmx_errors(form_errors)

# Update the lifetime purchased amount and maybe updates stock as well
@app.post("/product_update_purchased/<int:product_id>")
@admin_required
def post_product_update_purchased(product_id: int):
    form = ProductUpdatePurchasedForm()
    form_errors = parse_errors(form)

    product = Product.get_product(product_id)
    if product is None:
        form_errors.append(f'Cannot find product with id {product_id}')
    
    amount: int = form.purchased_amount.data
    adjust_stock: bool = form.adjust_stock.data
    diff: int = amount - (product.lifetime_purchased or 0) # product.lifetime_donated can be None
    if adjust_stock and diff < 0 and -diff > product.inventory:
        form_errors.append("Action would produce a negative stock level")

    if len(form_errors) == 0:
        product.set_purchased(amount, adjust_stock)
        return htmx_redirect(f"/{product_id}")
    else:
        return htmx_errors(form_errors)

###
# Search and filter products
###

@app.get("/product_search_filter_mobile")
@login_required
def get_product_search_filter_mobile():
    product_name_fragment = request.args.get('product_name')
    table_mode = request.args.get('table_mode')
    count_limit = request.args.get('count_limit')
    product_sort_method = request.args.get('product_sort_method')
    product_category_id = 0
    hidden_count = 0
    try:
        product_category_id = int(request.args.get('product_category_id'))
    except:
        pass
    if count_limit is not None:
        try:
            count_limit = int(count_limit)
        except:
            count_limit = None

    products = Product.search_filter_and_sort(product_name_fragment, product_category_id, product_sort_method)

    if count_limit is not None and len(products) > count_limit:
        hidden_count = len(products) - count_limit
        products = products[0:count_limit]

    return render_template(
        'mobile_table.html',
        product_list=products,
        table_mode=table_mode,
        hidden_count=hidden_count
    )

#####
#
# CATEGORIES
#
#####

###
# Create a new category
###

# Form to add a new category for admin only in main table page
@app.get("/category_add")
@admin_required
def get_category_add():
    icons = ["icons/cat_icons/Cleaning.svg", "icons/cat_icons/Hygiene.svg", "icons/cat_icons/Kitchen.svg", "icons/cat_icons/Paper.svg"]
    return render_template("modals/category_add.html", form=CategoryAddForm(), icons = icons)

# Create a new category
@app.post("/category_add")
@admin_required
def post_category_add():
    form = CategoryAddForm()
    form_errors = parse_errors(form)
    existing_category = Category.get_category(form.category_name.data)
    if existing_category is not None:
        form_errors.append(f'There already is a category with name "{form.category_name.data}"')

    possible_color_conflicting_category = Category.get_by_color(form.category_color.data)
    if possible_color_conflicting_category is not None:
        form_errors.append(f'Category "{possible_color_conflicting_category.name}" already exists with color "{form.category_color.data}"')

    if len(form_errors) == 0:
        Category.add_category(form.category_name.data, form.category_color.data, form.selected_icon.data)
        return htmx_redirect('/')
    else:
        return htmx_errors(form_errors)

###
# Update/change any/all fields of a category
###

# Form to edit a category for admin only in main table page
@app.get("/category_update/<int:category_id>")
@admin_required
def get_category_update(category_id: int):
    category = Category.get_category(category_id)
    return render_template("modals/category_update_all.html", category=category, form=CategoryUpdateAllForm())

# Change a product's category
@app.post("/category_update/<int:category_id>")
@admin_required
def post_category_update(category_id: int):
    if request.form.get('_method') == 'PATCH':
        form = CategoryUpdateAllForm()
        form_errors = parse_errors(form)

        category = Category.get_category(category_id)
        if category is None:
            form_errors.append(f"Could not find category {category_id}")

        possible_color_conflicting_category = Category.get_by_color(form.category_color.data)
        if possible_color_conflicting_category is not None and possible_color_conflicting_category.get_id() != category.get_id():
            form_errors.append(f'Category "{possible_color_conflicting_category.name}" already exists with color "{form.category_color.data}"')

        possible_conflicting_category = Category.get_category(form.category_name.data)
        if possible_conflicting_category is not None and possible_conflicting_category.get_id() != category.get_id():
            form_errors.append(f'Category already exists with name "{form.category_name.data}"')

        if len(form_errors) == 0:
            category_name = form.category_name.data
            category_color = form.category_color.data
            category.update_category(category_name, category_color)

            return htmx_redirect("/")
        else:
            return htmx_errors(form_errors)
    else:
        return abort(405, description="Method Not Allowed")

###
# Delete a category
###

# Delete a category
@app.delete("/category_delete/<int:category_id>")
@admin_required
def category_delete(category_id: int):
    Category.delete_category(category_id)
    return htmx_redirect('/')

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

@app.route("/data/category_icons/<path:filename>")
def serve_persisted_files(filename):
    return send_from_directory('/data/category_icons', filename)

with app.app_context():
    if not User.get_by_username('admin'):
        User.add_user('admin', bcrypt.generate_password_hash(os.environ.get("ADMIN_PASSWORD")))
    if not User.get_by_username('staff'):
        User.add_user('staff', bcrypt.generate_password_hash(os.environ.get("STAFF_PASSWORD")))
    if not User.get_by_username('volunteer'):
        User.add_user('volunteer', bcrypt.generate_password_hash(os.environ.get("VOLUNTEER_PASSWORD")))

if __name__ == '__main__':
    app.run(port=5000, debug=False)
