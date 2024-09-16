from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, validators
from wtforms.validators import InputRequired, EqualTo, Length, DataRequired

class RegistrationForm(FlaskForm):
    user_id = StringField("Username:", validators=[InputRequired()])
    password = PasswordField("Password:", validators=[InputRequired(),Length(min=5)])
    password2 = PasswordField("Confirm password:", validators=[InputRequired(), EqualTo("password")])
    submit = SubmitField("Submit")

class LoginForm(FlaskForm):
    user_id = StringField("Username:", validators=[InputRequired()])
    password = PasswordField("Password:", validators=[InputRequired()])
    submit = SubmitField("Submit")

class YouTubeChannelForm(FlaskForm):
    channel_url = StringField('YouTube Channel URL', validators=[validators.URL(), validators.DataRequired()])
    submit = SubmitField('Submit')

class LoginForm(FlaskForm):
    user_id = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')
