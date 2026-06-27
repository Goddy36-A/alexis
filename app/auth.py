from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from werkzeug.security import generate_password_hash, check_password_hash
from .database import get_db

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        db = get_db()
        error = None
        if not username or not email or not password:
            error = 'All fields are required.'
        elif db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
            error = 'Username already taken.'
        elif db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
            error = 'Email already registered.'
        if error:
            flash(error, 'error')
            return render_template('auth/register.html')
        db.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?,?,?)',
            (username, email, generate_password_hash(password))
        )
        db.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        password = request.form['password']
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username=? OR email=?',
            (identifier, identifier)
        ).fetchone()
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid credentials.', 'error')
            return render_template('auth/login.html')
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return redirect(url_for('main.index'))
    return render_template('auth/login.html')

@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))
