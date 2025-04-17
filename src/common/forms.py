from wtforms import StringField, PasswordField, SubmitField, IntegerField, BooleanField, validators, ColorField, DateField
from flask_wtf import FlaskForm
from flask import Response, make_response
from datetime import datetime
from dateutil.relativedelta import relativedelta
from ..model.product import StockUnitSubmission

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[validators.input_required()])
    password = PasswordField('Password', validators=[validators.input_required()])
    submit = SubmitField('Login')

class ProductUpdateAllForm(FlaskForm):
    product_name = StringField('Product Name', validators=[validators.input_required()])
    ideal_stock = IntegerField('Ideal Stock', validators=[validators.NumberRange(min=1)])
    submit = SubmitField('Submit')
    #also stock unit fields

class ProductAddForm(ProductUpdateAllForm):
    donation = BooleanField('Donation', default=False)
    category_id = IntegerField('Category Id', validators=[validators.NumberRange(min=1)])
    #also stock unit fields

# also for mobile
class ProductUpdateInventoryForm(FlaskForm):
    _method = StringField('_method', validators=[validators.AnyOf(['PATCH', 'patch'])])
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

class TimeFrameForm(FlaskForm):
    timeframe = StringField(
        'Time Frame',
        validators=[validators.AnyOf([
            "lifetime",
            "last_year",
            "year_to_date",
            "last_month",
            "last_week",
            "last_24_hours",
            "custom"
        ])]
    )
    startdate = DateField('Start Date', validators=[validators.Optional()])
    enddate = DateField('End Date', validators=[validators.Optional()])



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

def parse_timeframe_form_errors(form: TimeFrameForm) -> tuple[list[str], datetime | None, datetime | None]:
    base_errors = parse_errors(form)
    timeframe = form.timeframe.data
    now = datetime.now()
    if timeframe == 'lifetime':
        return base_errors, datetime(year=1970, month=1, day=1), now
    elif timeframe == 'last_year':
        return base_errors, now - relativedelta(years=1), now
    elif timeframe == 'last_month':
        return base_errors, now - relativedelta(months=1), now
    elif timeframe == 'last_week':
        return base_errors, now - relativedelta(weeks=1), now
    elif timeframe == 'last_24_hours':
        return base_errors, now - relativedelta(days=1), now
    elif timeframe == 'year_to_date':
        return base_errors, datetime(year=now.year, month=1, day=1), now
    elif timeframe == 'custom':
        if form.startdate.data is None:
            base_errors.append('Missing start date for custom range')
        if form.enddate.data is None:
            base_errors.append('Missing end date for custom range')
        if form.startdate.data is not None and form.enddate.data is not None and form.startdate.data > form.enddate.data:
            base_errors.append('Start date cannot be after end date')
        return base_errors, form.startdate.data, form.enddate.data
    else:
        return base_errors, None, None

def htmx_redirect(url: str) -> Response:
    response = make_response(url, 200)
    response.headers['HX-Redirect'] = url
    return response

def htmx_errors(errors: list[str]) -> Response:
    html = "<ul>" + "".join(f"<li>{error}</li>" for error in errors) + "</ul>"
    response = make_response(html, 400)
    response.headers['Content-Type'] = 'text/html'
    return response

# Parses the stock units in the form, appending any errors to the list and returning the successfully parsed units
def parse_stock_units(form: dict[str, str], errors: list[str], include_count: bool) -> list[StockUnitSubmission]:
    assert not isinstance(form, FlaskForm), 'form should be from `request.form`, not the form class itself'
    index = 1
    stock_units: list[StockUnitSubmission] = []
    while f'stock_name_{index}' in form and f'stock_multiplier_{index}' in form and f'stock_price_{index}' in form:
        name = form[f'stock_name_{index}']
        mult_key = f'stock_multiplier_{index}'
        price_key = f'stock_price_{index}'
        count_key = f'stock_count_{index}'

        if name is None or name == '':
            mult_is_missing = mult_key not in form or form[mult_key] == ''
            price_is_missing = price_key not in form or form[price_key] == ''
            count_is_missing = not include_count or count_key not in form or form[count_key] == ''
            if not (mult_is_missing and price_is_missing and count_is_missing):
                errors.append(f'Missing name for stock unit {index}')
            index += 1
            continue

        okay = True
        multiplier = form[mult_key]
        price = clean_price_to_float(form[price_key])

        try:
            multiplier = int(multiplier)
        except:
            errors.append(f'Multiplier for stock unit "{name}" is not an integer')
            okay = False
        if multiplier < 1:
            errors.append(f'Multiplier for stock unit "{name}" must be at least 1')
            okay = False

        if price is None:
            errors.append(f'Price for stock unit "{name}" is not valid')
            okay = False

        count = None
        if count_key in form:
            try:
                count = int(form[count_key])
            except:
                errors.append(f'Count for stock unit "{name}" is not an integer')
                okay = False
        elif include_count:
            errors.append(f'Count for stock unit "{name}" is missing')
            okay = False

        id = None
        if f'stock_id_{index}' in form:
            try:
                id = int(form[f'stock_id_{index}'])
            except:
                pass

        if okay:
            stock_units.append(StockUnitSubmission(id, name, multiplier, price, count))

        index += 1

    return stock_units

