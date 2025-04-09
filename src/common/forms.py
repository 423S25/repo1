from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, BooleanField, validators, ColorField
from flask_wtf import FlaskForm
from flask import Response, make_response, redirect

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[validators.input_required()])
    password = PasswordField('Password', validators=[validators.input_required()])
    submit = SubmitField('Login')

class ProductUpdateAllForm(FlaskForm):
    product_name = StringField('Product Name', validators=[validators.input_required()])
    ideal_stock = IntegerField('Ideal Stock', validators=[validators.NumberRange(min=1)])
    price = StringField('Price', validators=[validators.input_required()]) #string to allow '$' in entry
    unit_type = StringField('Unit Type', validators=[validators.input_required()])
    submit = SubmitField('Submit')

class ProductAddForm(ProductUpdateAllForm):
    inventory = IntegerField('Inventory', validators=[validators.NumberRange(min=0)])
    donation = BooleanField('Donation', default=False)
    category_id = IntegerField('Category Id', validators=[validators.NumberRange(min=1)])

# also for mobile
class ProductUpdateInventoryForm(FlaskForm):
    _method = StringField('_method', validators=[validators.AnyOf(['PATCH', 'patch'])])
    stock = IntegerField('Stock', validators=[validators.NumberRange(min=0)])
    submit = SubmitField('Submit')

class ProductAddInventoryForm(ProductUpdateInventoryForm):
    donation = BooleanField('Donation', default=False)

class ProductUpdateDonatedForm(FlaskForm):
    donated_amount = IntegerField('Donated Amount', validators=[validators.NumberRange(min=0)])
    adjust_stock = BooleanField('Adjust Stock', default=False)
    submit = SubmitField('Submit')

class ProductUpdatePurchasedForm(FlaskForm):
    purchased_amount = IntegerField('Purchased Amount', validators=[validators.NumberRange(min=0)])
    adjust_stock = BooleanField('Adjust Stock', default=False)
    submit = SubmitField('Submit')

class CategoryAddForm(FlaskForm):
    category_name = StringField('Category Name', validators=[validators.input_required()])
    category_color = ColorField('Category Color', validators=[validators.input_required()])
    selected_icon = ColorField('Selected Icon', validators=[validators.input_required()])

class CategoryUpdateAllForm(FlaskForm):
    category_name = StringField('Category Name', validators=[validators.input_required()])
    category_color = ColorField('Category Color', validators=[validators.input_required()])



def clean_price_to_float(val: str | None) -> float | None:
    if val is None:
        return None
    else:
        try:
            price = float(val.replace('$', ''))
            return None if price is None or price < 0 else price
        except:
            return None

# Validates the form and makes the errors more human readable
def parse_errors(form: FlaskForm) -> list[str]:
    form.validate()
    errors_list: list[str] = []

    for field_name, error_msg_list in form.errors.items():
        human_field_name = getattr(form, field_name).label.text
        has_integer_error = False
        for error_msg in error_msg_list:
            if error_msg == 'This field is required.':
                errors_list.append(f'Field "{human_field_name}" is required')
            elif error_msg == 'Not a valid integer value.':
                has_integer_error = True
                errors_list.append(f'"{human_field_name}" must be an integer')
            elif 'Number must be at least ' in error_msg:
                if has_integer_error:
                    continue
                try:
                    amount_min = int(' '.split(error_msg)[-1].replace(' ', ''))
                    errors_list.append(f'"{human_field_name}" must be at least {amount_min}')
                except:
                    errors_list.append(error_msg)
            else:
                errors_list.append(error_msg)

    if 'Field "Selected Icon" is required' in errors_list:
        errors_list[errors_list.index('Field "Selected Icon" is required')] = "Please Select an Icon"

    return errors_list

def htmx_redirect(url: str) -> Response:
    response = make_response(url, 200)
    response.headers['HX-Redirect'] = url
    return response

def htmx_errors(errors: list[str]) -> Response:
    html = "<ul>" + "".join(f"<li>{error}</li>" for error in errors) + "</ul>"
    response = make_response(html, 400)
    response.headers['Content-Type'] = 'text/html'
    return response

