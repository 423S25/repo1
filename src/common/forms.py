from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, BooleanField, validators
from flask_wtf import FlaskForm

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[validators.input_required()])
    password = PasswordField('Password', validators=[validators.input_required()])
    submit = SubmitField('Login')

class ProductAddForm(FlaskForm):
    product_name = StringField('Product Name', validators=[validators.input_required()])
    inventory = IntegerField('Inventory', validators=[validators.NumberRange(min=0)])
    ideal_stock = IntegerField('Ideal Stock', validators=[validators.NumberRange(min=1)])
    price = StringField('Price', validators=[validators.input_required()]) #string to allow '$' in entry
    unit_type = StringField('Unit Type', validators=[validators.input_required()])
    donation = BooleanField('Donation', default=False)
    category_id = IntegerField('Category Id', validators=[validators.NumberRange(min=1)])
    submit = SubmitField('Login')

def clean_price_to_float(val: str | None) -> float | None:
    if val is None:
        return None
    else:
        try:
            return float(val.replace('$', ''))
        except:
            return None

# Make the form more human readable
def parse_errors(form: FlaskForm) -> list[str]:
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

    return errors_list

def render_errors_as_html(errors: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{error}</li>" for error in errors) + "</ul>"



