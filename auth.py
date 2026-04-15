from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('main.index'))
        flash('Неверные данные', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Пользователь существует', 'warning')
        else:
            user = User(username=username, role=request.form['role'], full_name=request.form.get('full_name',''))
            user.set_password(request.form['password'])
            db.session.add(user)
            db.session.commit()
            flash('Создан', 'success')
            return redirect(url_for('main.users_list'))
    return render_template('register.html')