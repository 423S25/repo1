import os, secrets
from flask import Flask, request, Response, render_template, redirect, abort, flash, url_for

from src.model.product import Category
from src.model.product import Product, InventorySnapshot, db
from src.model.user import User, user_db
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
from flask_bcrypt import Bcrypt

from src.common.forms import LoginForm
from src.common.email_job import EmailJob

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, static_url_path='', static_folder='static')

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

bcrypt = Bcrypt(app)

app.config['SECRET_KEY'] = secrets.token_urlsafe()
#app.config['SECRET_KEY'] = "asdf"
app.config["SESSION_PROTECTION"] = "strong"
UPLOAD_FOLDER = os.path.join("static", "images")
app.config['UPLOADED_IMAGES'] = UPLOAD_FOLDER


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

@app.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    next = request.args.get('next')
    errors = [] #used to display errors on the login page
    if form.validate_on_submit(): #makes sure form is complete
        user = User.get_by_username(form.username.data)
        if user is None:
            errors.append("User not found.")
            return render_template('security/login.html', form=form, errors=errors)
        correct_password = bcrypt.check_password_hash(user.password, form.password.data)
        if not correct_password:
            errors.append("Incorrect password.")
            return render_template('security/login.html', form=form, errors=errors)
        login_success = login_user(user)
        if not login_success:
            errors.append("Login failed")
            return render_template('security/login.html', form=form, errors=errors)
        return redirect(next or url_for("home"))
    return render_template('security/login.html', form=form, errors=errors)

@app.get("/")
@login_required #any user can access home page
def home():
    # Fills the days left for each product with product.get_days_until_out
    Product.fill_days_left()
    # Loads products in urgency order
    category_id = request.args.get('category_id', default=0, type=int)  # Default to 0 if no category is selected
    if category_id == 0:
        products = Product.urgency_rank()
    else:
        products = Product.urgency_rank(category_id)
    categories = Category.all()
    return render_template("index.html", product_list=products, user=current_user, categories=categories, current_category=category_id)

@app.get("/reports")
@login_required
def reports():
    Product.fill_days_left()
    products = Product.urgency_rank()
    return render_template("reports_index.html", product_list=products, user=current_user)


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


@app.post("/upload/<int:product_id>")
@login_required
def upload_image(product_id: int):
    if 'file' not in request.files:
        return redirect('/' + str(product_id))

    file = request.files['file']
    product = Product.get_product(product_id)
    if file.filename == '':
        return redirect('/' + str(product_id))
    filename = file.filename
    product.set_img_path(filename)

    file.save(os.path.join(app.config['UPLOADED_IMAGES'], filename))
    return redirect("/" + str(product_id))


@app.get("/add")
@login_required
def get_add():
    #only admin can add products
    if current_user.username != 'admin':
        return abort(401, description='Only admins can add products')
    return render_template("add_form.html")



@app.route("/add", methods=["POST"])
@login_required
def add():
    #only admin can add products
    if current_user.username != 'admin':
        return abort(401, description='Only admins can add products')
    if Product.get_product(request.form.get("product_name")) is None and request.form.get("category_id") != '':
        Product.add_product(request.form.get("product_name"), \
                            int(request.form.get("inventory")), \
                            int(request.form.get("category_id")), \
                            float(request.form.get("price")), \
                            request.form.get("unit_type"), \
                            int(request.form.get("ideal_stock")), \
                            bool(request.form.get("donation")),
                            None)

        Product.fill_days_left()
        EmailJob.process_emails(User.get_by_username('admin').email)
        return redirect("/")
    else:
        abort(400)


@app.delete("/delete/<int:product_id>")
@login_required
def delete(product_id: int):
    #only admin can delete products
    #TODO: display message or page to user when encountering 401 error
    if current_user.username != 'admin':
        return abort(401, description='Only admins can delete products')
    Product.delete_product(product_id)
    products = Product.urgency_rank()
    categories = Category.all()
    category_id = request.args.get('category_id', default=0, type=int)
    return render_template("index.html", product_list=products, user=current_user, categories=categories, current_category=category_id)

@app.delete("/delete_category/<int:category_id>")
def delete_category(category_id: int):
    #only admin can delete products
    if current_user.username != 'admin':
        return abort(401, description='Only admins can delete products')
    Category.delete_category(category_id)
    products = Product.urgency_rank()
    categories = Category.all()
    category_id = request.args.get('category_id', default=0, type=int)
    return render_template("index.html", product_list=products, user=current_user, categories=categories, current_category=category_id)



@app.route("/update/inventory/<int:product_id>", methods=["POST"])
@login_required #any user can update inventory
def update_inventory(product_id: int):
    if request.form.get('_method') == 'PATCH':
        new_stock = request.form.get('stock', None, type=int)
        donation = request.form.get("donation", False)
        if new_stock is None or new_stock < 0:
            return abort(400, description="Stock count must be a positive integer")

        product = Product.get_product(product_id)
        if product is None:
            return abort(404, description=f"Could not find product {product_id}")
        
        product.update_stock(new_stock, donation)
        product.mark_not_notified()
        EmailJob.process_emails(User.get_by_username('admin').email)
        return redirect("/" + str(product_id), 303)
    else:
        return abort(405, description="Method Not Allowed")

@app.route("/update/<int:product_id>", methods=["POST"])
@login_required #admin only
def update_all(product_id: int):
    if current_user.username != 'admin':
        return abort(401, description='Only admins can delete products')

    if request.form.get('_method') == 'PATCH':
        product = Product.get_product(product_id)
        if product is None:
            return abort(404, description=f"Could not find product {product_id}")

        product_name = request.form.get("product_name")
        price = request.form.get("price")
        unit_type = request.form.get("unit_type")
        ideal_stock = request.form.get("ideal_stock")

        product.update_product(product_name, float(price), unit_type, int(ideal_stock))
        Product.fill_days_left()
        product.mark_not_notified()
        EmailJob.process_emails(User.get_by_username('admin').email)
        return redirect("/" + str(product_id), 303)
    else:
        return abort(405, description="Method Not Allowed")


@app.route("/update_category/<int:category_id>", methods=["POST"])
@login_required #admin only
def update_category(category_id: int):
    if current_user.username != 'admin':
        return abort(401, description='Only admins can delete products')

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





@app.route("/add_category", methods=["POST"])
@login_required
def add_category():
    #only admin can add products
    if current_user.username != 'admin':
        return abort(401, description='Only admins can add products')
    if Category.get_category(request.form.get("category_name")) is None:
        Category.add_category(request.form.get("category_name"), (request.form.get("category_color")))
    else:
        abort(400)
    return redirect("/")


@app.get("/export_csv")
@login_required
def export_csv():
    if current_user.username != 'admin':
        return abort(401, description='Only admin can export csv')
    csv_file = Product.get_csv()
    response = Response(csv_file, content_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=products.csv"
    return response

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
    print(category_id, '\n', type(category_id))
    return render_template("index.html", product_list=products, user=current_user, categories=categories, current_category=category_id)


#MODALS
@app.get("/load_update/<int:product_id>")
@login_required
def load_update(product_id: int):
    product = Product.get_product(product_id)
    return render_template("modals/update_stock.html",
                           product=product)

@app.get("/load_update_all/<int:product_id>")
@login_required
def load_update_all(product_id: int):
    if current_user.username != 'admin':
        return abort(401, description='Only admins can access this feature.')
    product = Product.get_product(product_id)
    return render_template("modals/update_all.html",
                           product=product)
@app.get("/load_add")
@login_required
def load_add():
    if current_user.username != 'admin':
        return abort(401, description='Only admins can add products')
    categories = Category.all()
    return render_template("modals/add.html", categories=categories)

@app.get("/load_add_category")
def load_add_color():
    return render_template("modals/add_category.html")
@app.get("/load_edit_category/<int:category_id>")
def load_edit_category(category_id: int):
    category = Category.get_category(category_id)
    return render_template("modals/edit_category.html", category=category)

@app.get("/settings")
@login_required
def get_settings():
    if current_user.username != 'admin':
        return abort(401, description='Only admins can access admin settings')
    return render_template("settings.html", user=current_user)

@app.post("/settings")
@login_required
def update_settings():
    if current_user.username != 'admin':
        return abort(401, description='Only admins can access admin settings')
    email = request.form.get("email")
    User.get_by_username('admin').update_email(email)
    return redirect("/settings")

with app.app_context():
    if not User.get_by_username('admin'):
        User.add_user('admin', bcrypt.generate_password_hash(os.environ.get("ADMIN_PASSWORD")))
    if not User.get_by_username('staff'):
        User.add_user('staff', bcrypt.generate_password_hash(os.environ.get("STAFF_PASSWORD")))
    if not User.get_by_username('volunteer'):
        User.add_user('volunteer', bcrypt.generate_password_hash(os.environ.get("VOLUNTEER_PASSWORD")))

if __name__ == '__main__':
    app.run(port=5000, debug=False)