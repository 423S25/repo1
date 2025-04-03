from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, BooleanField, validators
from flask_wtf import FlaskForm

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[validators.input_required()])
    password = PasswordField('Password', validators=[validators.input_required()])
    submit = SubmitField('Login')

class ProductAddForm(FlaskForm):
    product_name = StringField('Product Name', validators=[validators.input_required()])
    inventory = IntegerField('Inventory', validators=[validators.input_required()])
    ideal_stock = IntegerField('Ideal Stock', validators=[validators.input_required()])
    price = StringField('Price', validators=[validators.input_required()]) #string to allow '$' in entry
    unit_type = StringField('Unit Type', validators=[validators.input_required()])
    donation = BooleanField('Donation')
    category_id = IntegerField('Category Id', validators=[validators.input_required()])
    submit = SubmitField('Login')

def clean_price_to_float(val: str | None) -> float | None:
    if val is None:
        return None
    else:
        try:
            return float(val.replace('$', ''))
        except:
            return None

