from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    full_name = db.Column(db.String(100))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    def has_role(self, *roles):
        return self.role in roles

class WarehouseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    weight = db.Column(db.String(50))
    size = db.Column(db.String(50))
    cost_price = db.Column(db.Float, default=0.0)

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    passport = db.Column(db.String(100))
    details = db.Column(db.String(200))
    position = db.Column(db.String(50))
    salary_value = db.Column(db.Float, default=0.0)
    fired = db.Column(db.Boolean, default=False)
    fire_reason = db.Column(db.String(200))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30))
    device_model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    imei = db.Column(db.String(50))
    main_problem = db.Column(db.Text)
    detected_problem = db.Column(db.Text)
    price = db.Column(db.Float, default=0.0)
    deadline = db.Column(db.DateTime, nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), default='in_progress')
    responsible_employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    is_checked = db.Column(db.Boolean, default=False)
    checked_by = db.Column(db.String(100))
    checked_at = db.Column(db.DateTime)
    refused_with_parts = db.Column(db.Boolean, default=False)
    checklist_data = db.Column(db.Text, nullable=True)
    responsible_employee = db.relationship('Employee', foreign_keys=[responsible_employee_id])

class FinanceTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20))
    category = db.Column(db.String(100))
    amount = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))

class BlacklistClient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(30))
    reason = db.Column(db.Text)

class PriceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    execution_time = db.Column(db.String(100))
    price = db.Column(db.Float)

class RecurringPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100))
    amount = db.Column(db.Float)
    description = db.Column(db.String(200))
    last_applied_month = db.Column(db.String(7))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_role = db.Column(db.String(30))
    user_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    link = db.Column(db.String(200), nullable=True)

    @staticmethod
    def create_notification(role, title, message, link=None, user_id=None):
        n = Notification(user_role=role, user_id=user_id, title=title, message=message, link=link)
        db.session.add(n)
        db.session.commit()
        return n

class OrderLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80))
    action = db.Column(db.String(50))
    field_name = db.Column(db.String(50), nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.relationship('Order', backref=db.backref('logs', lazy='dynamic'))

class WarrantyCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    warranty_type = db.Column(db.String(30))  # 'work' или 'part'
    description = db.Column(db.String(200))
    valid_until = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    order = db.relationship('Order', backref=db.backref('warranty_cards', lazy='dynamic'))

    @staticmethod
    def create_for_order(order, warranty_type, description, days):
        until = datetime.utcnow() + timedelta(days=days)
        card = WarrantyCard(
            order_id=order.id,
            warranty_type=warranty_type,
            description=description,
            valid_until=until,
            is_active=True
        )
        db.session.add(card)
        return card