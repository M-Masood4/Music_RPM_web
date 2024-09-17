from flask import Flask, render_template, request, session, g, redirect, url_for, flash, send_file, abort
from database import get_db, close_db
from forms import RegistrationForm, LoginForm, LoginForm
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import urllib.parse
import io
from datetime import datetime, timedelta
import random
import string


app = Flask(__name__)
app.teardown_appcontext(close_db)
app.config["SECRET_KEY"] = "Masood2024"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        # Fetch the user's details and their most recent used code expiry date
        user = db.execute('''
            SELECT u.user_id, u.is_admin, uc.expiry_date 
            FROM users u
            LEFT JOIN used_codes uc ON u.user_id = uc.user_id
            WHERE u.user_id = ?
            ORDER BY uc.used_date DESC LIMIT 1
        ''', (user_id,)).fetchone()

        if user is None:
            g.user = None
        else:
            g.user = {
                'user_id': user['user_id'],
                'is_admin': user['is_admin'],
                'subscription_expired': user['expiry_date'] is None or user['expiry_date'] < datetime.now()  # Check if the expiry date has passed
            }


# Login required decorator
def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.url))

        # Admins can access all pages without restrictions
        if g.user.get('is_admin'):
            return view(*args, **kwargs)

        # Check if the user's subscription is expired or they have no valid code
        if g.user.get('subscription_expired', True) and request.endpoint != 'account':
            flash("Your subscription has expired. Please buy a new code to regain access.")
            return redirect(url_for('account'))  # Only allow access to the account page

        return view(*args, **kwargs)
    return wrapped_view

# Admin check decorator
def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        # Ensure the user is logged in
        if g.user is None:
            return redirect(url_for('login'))
        
        # Check if the user is an admin
        db = get_db()
        user = db.execute('SELECT is_admin FROM users WHERE user_id = ?', (g.user['user_id'],)).fetchone()
        
        # If the user is not admin or doesn't exist, deny access
        if user is None or user['is_admin'] == 0:
            flash('Access Denied: Admins Only')
            return redirect(url_for('index'))  # or return a 403 error page

        return view(*args, **kwargs)
    return wrapped_view

# User registration

@app.route("/register",methods=["GET", "POST"])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        username = form.user_id.data
        password = form.password.data
        code = request.form.get('code')

        db = get_db()

        # Validate the code
        code_data = db.execute('SELECT * FROM codes WHERE code = ?', (code,)).fetchone()

        if not code_data:
            flash('Invalid code.')
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = generate_password_hash(password)
        expiry_date = datetime.now() + timedelta(days=30)  # 30 days from now

        # Insert new user into the database
        db.execute('INSERT INTO users (user_id, password) VALUES (?, ?)', (username, hashed_password))

        # Record the code usage in the used_codes table
        db.execute('INSERT INTO used_codes (code_id, user_id, used_date, expiry_date) VALUES (?, ?, ?, ?)',
                   (code_data['id'], username, datetime.now(), expiry_date))

        # Commit the transaction
        db.commit()

        flash('Registration successful! You now have 30 days of access.')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


# User login
@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_id = form.user_id.data
        password = form.password.data
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,)).fetchone()
        
        if user is None:
            form.user_id.errors.append("No such username!")
        elif not check_password_hash(user["password"], password):
            form.password.errors.append("Incorrect password!")
        else:
            session.clear()
            session["user_id"] = user_id
            next_page = request.args.get("next") or url_for("index")
            return redirect(next_page)
        
    return render_template("login.html", form=form)


# Helper function to generate unique codes
# Helper function to generate unique codes
def generate_unique_codes(count=10, length=8):
    """Generates `count` random alphanumeric codes."""
    codes = []
    for _ in range(count):
        code = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        codes.append(code)
    return codes

@app.route('/admin/generate_and_view_codes', methods=['GET', 'POST'])
def generate_and_view_codes():
    db = get_db()

    # Handle code generation
    if request.method == 'POST':
        codes = generate_unique_codes(count=10)  # Generate 10 codes
        for code in codes:
            db.execute('INSERT INTO codes (code) VALUES (?)', (code,))
        db.commit()
        flash(f'{len(codes)} codes generated successfully.')
        return redirect(url_for('generate_and_view_codes'))

    # Initialize sorting logic
    sort = request.args.get('sort', 'newest')  # Default sort by newest

    # Basic query for used codes
    base_query = '''
        SELECT c.code, uc.user_id, uc.used_date, uc.expiry_date
        FROM codes c
        LEFT JOIN used_codes uc ON c.id = uc.code_id
        WHERE uc.used_date IS NOT NULL
    '''

    # Sorting logic
    if sort == 'newest':
        base_query += ' ORDER BY uc.used_date DESC'
    elif sort == 'oldest':
        base_query += ' ORDER BY uc.used_date ASC'
    elif sort == 'expiring_soon':
        base_query += ' ORDER BY uc.expiry_date ASC'
    
    # Execute query and fetch used codes
    used_codes = db.execute(base_query).fetchall()

    # Query for unused codes
    unused_codes = db.execute('''
        SELECT code 
        FROM codes 
        WHERE id NOT IN (SELECT code_id FROM used_codes)
        ORDER BY code
    ''').fetchall()

    return render_template('admin_generate_and_view_codes.html', used_codes=used_codes, unused_codes=unused_codes, sort=sort)




# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))



@app.route('/renew_subscription', methods=['POST'])
@login_required
def renew_subscription():
    code = request.form.get('code')
    db = get_db()

    # Validate the code
    code_data = db.execute('SELECT * FROM codes WHERE code = ?', (code,)).fetchone()
    if not code_data:
        flash('Invalid code.')
        return redirect(url_for('account'))

    expiry_date = datetime.now() + timedelta(days=30)  # Extend by 30 days

    # Record the new code usage
    db.execute('INSERT INTO used_codes (code_id, user_id, used_date, expiry_date) VALUES (?, ?, ?, ?)',
               (code_data['id'], g.user['user_id'], datetime.now(), expiry_date))
    db.commit()

    flash('Subscription renewed successfully!')
    return redirect(url_for('index'))

@app.route('/upload_music', methods=['GET', 'POST'])
@admin_required
def upload_music():
    if request.method == 'POST':
        file = request.files.get('file')
        image = request.files.get('image')  # Get the album cover image file
        description = request.form.get('description')
        genre = request.form.get('genre')
        
        if file:
            filename = secure_filename(file.filename)
            file_data = file.read()

            # Handle image upload (optional)
            image_data = None
            if image:
                image_data = image.read()

            user_id = g.user['user_id']  # Get user_id from g.user

            db = get_db()
            db.execute("""
                INSERT INTO music (filename, file, user_id, description, genre, image)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (filename, file_data, user_id, description, genre, image_data))
            db.commit()
            flash('Music uploaded successfully!')
            return redirect(url_for('index'))
    
    return render_template('upload_music.html')

@app.route('/download_music/<int:id>')
@login_required
def download_music(id):
    db = get_db()
    music = db.execute('SELECT filename, file FROM music WHERE id = ?', (id,)).fetchone()

    if music and music['file']:
        return send_file(io.BytesIO(music['file']), as_attachment=True, download_name=music['filename'], mimetype='audio/mpeg')
    else:
        abort(404)

@app.route('/serve_music_image/<int:id>')
@login_required
def serve_music_image(id):
    db = get_db()
    music = db.execute('SELECT image FROM music WHERE id = ?', (id,)).fetchone()

    if music and music['image']:
        return send_file(io.BytesIO(music['image']), mimetype='image/jpeg')
    else:
        abort(404)



@app.route('/serve_music/<int:id>')
@login_required
def serve_music(id):
    db = get_db()
    music = db.execute('SELECT file FROM music WHERE id = ?', (id,)).fetchone()

    if music and music['file']:
        return send_file(io.BytesIO(music['file']), mimetype='audio/mpeg')
    else:
        abort(404)

# Music search and filtering
@app.route('/music', methods=['GET'])
@login_required
def music():
    search_query = request.args.get('search', '')
    genre_filter = request.args.get('genre', '')
    order = request.args.get('order', 'newest')

    db = get_db()
    query = "SELECT id, filename, description, genre, image, upload_date FROM music WHERE 1=1"
    params = []

    if search_query:
        query += " AND filename LIKE ?"
        params.append(f"%{search_query}%")
    
    if genre_filter:
        query += " AND genre = ?"
        params.append(genre_filter)
    
    if order == 'newest':
        query += " ORDER BY upload_date DESC"
    else:
        query += " ORDER BY upload_date ASC"
    
    music_list = db.execute(query, params).fetchall()
    genres = db.execute("SELECT DISTINCT genre FROM music").fetchall()

    return render_template('music.html', entries=music_list, genres=[g['genre'] for g in genres])



@app.route('/')
def index():
    # If the user is logged in
    if g.user:
        if g.user['subscription_expired']:
            flash('Your subscription has expired. Please renew to regain access.')
            return redirect(url_for('account'))  # Redirect expired users to the account page
        elif g.user['is_admin']:
            return redirect(url_for('admin_panel'))  # Admin users
        else:
            return redirect(url_for('music'))  # Normal users with active subscriptions

    # If the user is not logged in, show the index page
    return render_template('index.html')


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user_id = session.get('user_id')
    db = get_db()

    # Fetch user details
    user = db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()

    # Fetch linked YouTube channels
    linked_channels = db.execute(
        'SELECT channel_url, verification_code, verified FROM youtube_channels WHERE user_id = ?',
        (user_id,)
    ).fetchall()

    # Fetch RPM, revenue, and YouTube image from the music_rpm table
    music_rpm_info = db.execute(
        'SELECT rpm, revenue, youtube_image FROM music_rpm WHERE user_id = ?',
        (user_id,)
    ).fetchone()

    if request.method == 'POST':
        # Handle password change logic
        new_password = request.form.get('new_password')
        if new_password:
            db.execute('UPDATE users SET password = ? WHERE user_id = ?', (new_password, user_id))
            db.commit()
            flash('Password updated successfully!')
            return redirect(url_for('account'))

    return render_template('account.html', user=user, linked_channels=linked_channels, music_rpm_info=music_rpm_info)



# Change password
@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    db = get_db()
    new_password = request.form.get('new_password')
    new_password_hash = generate_password_hash(new_password)
    user_id = session['user_id']
    db.execute('UPDATE users SET password = ? WHERE user_id = ?', (new_password_hash, user_id))
    db.commit()
    flash('Password updated successfully!')
    return redirect(url_for('account'))


# Helper to generate verification code
def generate_verification_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Check if the channel has already been verified
def is_channel_verified(channel_url):
    db = get_db()
    channel = db.execute("SELECT * FROM youtube_channels WHERE channel_url = ? AND verified = 2", (channel_url,)).fetchone()
    return bool(channel)


@app.route('/submit_youtube_channel', methods=['GET', 'POST'])
@login_required
def submit_youtube_channel():
    db = get_db()
    
    if request.method == 'POST':
        # This handles the final submission
        channel_url = request.form['channel_url']
        verification_code = request.form['verification_code']
        
        # Check if the channel has already been verified
        if is_channel_verified(channel_url):
            flash('This channel is already verified.')
            return redirect(url_for('submit_youtube_channel'))

        # Check for duplicates
        existing_channel = db.execute("SELECT * FROM youtube_channels WHERE channel_url = ?", (channel_url,)).fetchone()
        if existing_channel:
            flash('This channel has already been submitted for verification.')
            return redirect(url_for('submit_youtube_channel'))

        # Save the new channel submission with verification code
        user_id = g.user['user_id']
        db.execute("INSERT INTO youtube_channels (channel_url, verification_code, user_id, submission_time, verified) VALUES (?, ?, ?, ?, ?)", 
                   (channel_url, verification_code, user_id, datetime.utcnow(), 0))
        db.commit()

        flash('Your channel has been submitted for verification.')
        return redirect(url_for('submit_youtube_channel'))
    
    # Generate a verification code on GET or after URL entry
    if 'channel_url' in request.args:
        channel_url = request.args.get('channel_url')
        verification_code = generate_verification_code()
        return render_template('submit_youtube_channel.html', channel_url=channel_url, verification_code=verification_code)
    
    return render_template('submit_youtube_channel.html')



@app.route('/verify_youtube_channel', methods=['POST'])
@login_required
def verify_youtube_channel():
    db = get_db()
    channel_url = request.form['channel_url']
    user_id = g.user['user_id']

    channel = db.execute("SELECT * FROM youtube_channels WHERE channel_url = ? AND user_id = ?", (channel_url, user_id)).fetchone()

    if channel:
        flash('Your channel has been submitted for admin review.')
    else:
        flash('Channel not found or not submitted by you.')
    
    return redirect(url_for('submit_youtube_channel'))





@app.route('/admin')
@admin_required
def admin_panel():
    db = get_db()
    channels = db.execute("SELECT channel_url, verification_code, user_id, verified FROM youtube_channels WHERE verified = 0").fetchall()
    return render_template('admin.html', channels=channels)

@app.route('/admin_approve_channel/<path:channel_url>', methods=['POST'])
@admin_required
def admin_approve_channel(channel_url):
    decoded_channel_url = urllib.parse.unquote(channel_url)
    db = get_db()

    # Approve the channel
    db.execute("UPDATE youtube_channels SET verified = 2 WHERE channel_url = ?", (decoded_channel_url,))
    db.commit()

    flash(f'Channel {decoded_channel_url} has been approved.')
    return redirect(url_for('admin_panel'))

@app.route('/admin_disapprove_channel/<path:channel_url>', methods=['POST'])
@admin_required
def admin_disapprove_channel(channel_url):
    decoded_channel_url = urllib.parse.unquote(channel_url)
    db = get_db()

    # Disapprove and delete the channel from the database
    db.execute("DELETE FROM youtube_channels WHERE channel_url = ?", (decoded_channel_url,))
    db.commit()

    flash(f'Channel {decoded_channel_url} has been disapproved and removed from the list.')
    return redirect(url_for('admin_panel'))

@app.route('/check_verification_status', methods=['GET'])
@login_required
def check_verification_status():
    db = get_db()
    user_id = g.user['user_id']
    channels = db.execute("SELECT channel_url, verified FROM youtube_channels WHERE user_id = ?", (user_id,)).fetchall()

    return render_template('verification_status.html', channels=channels)



@app.route('/admin_verified_channels')
@admin_required
def admin_verified_channels():
    db = get_db()
    # Fetch all the channels that are verified (verified = 2)
    verified_channels = db.execute("SELECT channel_url, user_id FROM youtube_channels WHERE verified = 2").fetchall()
    return render_template('admin_verified_channels.html', verified_channels=verified_channels)


@app.route('/revenue')
@login_required
def revenue():
    return render_template('revenue.html')

@app.route('/admin/update_account', methods=['GET', 'POST'])
@login_required
def update_account():
    # Ensure only admins can access this route
    if not g.user['is_admin']:
        return redirect(url_for('account'))

    db = get_db()

    # Fetch search query and sort order from the request
    search_query = request.args.get('search', '')
    sort_order = request.args.get('sort', 'last_updated')

    # Query users based on the search query, sorting by last_updated or username
    users = db.execute(
        'SELECT u.user_id, u.username, u.last_updated, m.rpm, m.revenue '
        'FROM users u LEFT JOIN music_rpm m ON u.user_id = m.user_id '
        'WHERE u.username LIKE ? '
        'ORDER BY ' + sort_order + ' DESC',
        ('%' + search_query + '%',)
    ).fetchall()

    # Handle the form submission (POST request)
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        rpm = request.form.get('rpm')
        revenue = request.form.get('revenue')
        new_password = request.form.get('password')

        # Update RPM if present
        if rpm is not None:
            rpm = float(rpm)
            db.execute('UPDATE music_rpm SET rpm = ? WHERE user_id = ?', (rpm, user_id))

        # Update Revenue if present
        if revenue is not None:
            revenue = float(revenue)
            db.execute('UPDATE music_rpm SET revenue = ? WHERE user_id = ?', (revenue, user_id))

        # Update YouTube image if uploaded
        file = request.files.get('youtube_image')
        if file and file.filename != '':
            youtube_image = file.read()
            db.execute('UPDATE music_rpm SET youtube_image = ? WHERE user_id = ?', (youtube_image, user_id))

        # Update last_updated timestamp
        db.execute('UPDATE users SET last_updated = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        db.commit()

        flash('User account updated successfully!')
        return redirect(url_for('update_account'))

    return render_template('admin_update_account.html', users=users)
