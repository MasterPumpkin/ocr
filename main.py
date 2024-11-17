from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import FileField, StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
db = SQLAlchemy(app)

# Modely databáze
class Code(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(255), nullable=False)

class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_marker = db.Column(db.String(50), nullable=False)
    end_marker = db.Column(db.String(50), nullable=False)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

# Formuláře
class LoginForm(FlaskForm):
    username = StringField('Uživatelské jméno', validators=[InputRequired(), Length(min=3, max=50)])
    password = PasswordField('Heslo', validators=[InputRequired()])
    submit = SubmitField('Přihlásit se')

class UploadForm(FlaskForm):
    file = FileField('Nahrát CSV soubor', validators=[InputRequired()])
    submit = SubmitField('Nahrát')

class ConfigForm(FlaskForm):
    start_marker = StringField('Start Marker', validators=[InputRequired()])
    end_marker = StringField('End Marker', validators=[InputRequired()])
    submit = SubmitField('Uložit')

# Funkce pro kontrolu přihlášení
def is_logged_in():
    return 'user_id' in session

# Routy aplikace
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Admin.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            session['user_id'] = user.id
            flash('Přihlášení proběhlo úspěšně.', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Neplatné přihlašovací údaje.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Byli jste odhlášeni.', 'info')
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not is_logged_in():
        flash('Pro přístup se musíte přihlásit.', 'warning')
        return redirect(url_for('login'))

    upload_form = UploadForm()
    config_form = ConfigForm()

    # Nahrání CSV souboru
    if upload_form.validate_on_submit() and 'file' in request.files:
        file = request.files['file']
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Načtení kódů z CSV a uložení do databáze
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                db.session.add(Code(code=row[0]))
        db.session.commit()
        flash('CSV soubor byl úspěšně nahrán.', 'success')
        return redirect(url_for('admin_dashboard'))

    # Aktualizace konfigurace markerů
    if config_form.validate_on_submit():
        config = Config.query.first()
        if not config:
            config = Config(start_marker=config_form.start_marker.data, end_marker=config_form.end_marker.data)
            db.session.add(config)
        else:
            config.start_marker = config_form.start_marker.data
            config.end_marker = config_form.end_marker.data
        db.session.commit()
        flash('Konfigurace byla aktualizována.', 'success')
        return redirect(url_for('admin_dashboard'))

    current_config = Config.query.first()
    return render_template('admin.html', upload_form=upload_form, config_form=config_form, current_config=current_config)

@app.route('/api/config', methods=['GET'])
def get_config():
    """API pro získání dynamických markerů."""
    config = Config.query.first()
    if not config:
        return jsonify({"startMarker": "###", "endMarker": "###"}), 200
    return jsonify({"startMarker": config.start_marker, "endMarker": config.end_marker})

@app.route('/api/check', methods=['POST'])
def check_code():
    """Endpoint pro kontrolu kódu."""
    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({"error": "No code provided"}), 400

    code_to_check = data['code']
    found = Code.query.filter_by(code=code_to_check).first() is not None
    return jsonify({"found": found}), 200

if __name__ == "__main__":
    # Zajistěte, že složka pro nahrávání existuje
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Inicializace databáze
    with app.app_context():
        db.create_all()
        # Vytvoření výchozího administrátora (pokud neexistuje)
        if not Admin.query.first():
            admin = Admin(username='admin', password=generate_password_hash('admin123'))
            db.session.add(admin)
            db.session.commit()

    # Spuštění aplikace
    app.run(debug=True)
