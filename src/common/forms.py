from wtforms import StringField, PasswordField, SubmitField, validators
from flask_wtf import FlaskForm

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[validators.input_required()])
    password  = PasswordField('Password', validators=[validators.input_required()])
    submit = SubmitField('Login')

def clean_price_to_float(val: str | None) -> float | None:
    if val is None:
        return None
    else:
        try:
            return float(val.replace('$', ''))
        except:
            return None

