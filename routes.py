from functools import wraps
from threading import Thread
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from models import db, WarehouseItem, Employee, Order, FinanceTransaction, BlacklistClient, PriceItem, RecurringPayment, User, Notification, OrderLog, WarrantyCard
from datetime import datetime
from sqlalchemy import func
from utils import check_deadlines_and_notify, send_order_ready_email_with_act, generate_act_pdf_buffer, log_order_change
import json

main_bp = Blueprint('main', __name__)

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.has_role(*roles):
                flash('Доступ запрещён', 'danger')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def add_transaction(type_, category, amount, description):
    tr = FinanceTransaction(type=type_, category=category, amount=amount, description=description)
    db.session.add(tr)
    db.session.commit()

def recalc_balance():
    inc = db.session.query(func.sum(FinanceTransaction.amount)).filter_by(type='income').scalar() or 0
    exp = db.session.query(func.sum(FinanceTransaction.amount)).filter_by(type='expense').scalar() or 0
    return inc - exp

# ------------------ Главная страница ------------------
@main_bp.route('/')
@login_required
def index():
    Thread(target=check_deadlines_and_notify).start()
    return render_template('index.html')

# ------------------ Страницы ------------------
@main_bp.route('/warehouse')
@role_required('admin', 'manager')
def warehouse_page():
    return render_template('warehouse.html')

@main_bp.route('/employees')
@role_required('admin', 'manager')
def employees_page():
    return render_template('employees.html')

@main_bp.route('/orders_page')
@login_required
def orders_page():
    return render_template('orders.html')

@main_bp.route('/finance')
@role_required('admin', 'accountant', 'manager')
def finance_page():
    return render_template('finance.html')

@main_bp.route('/blacklist_page')
@role_required('admin', 'manager')
def blacklist_page():
    return render_template('blacklist.html')

@main_bp.route('/pricelist_page')
@login_required
def pricelist_page():
    return render_template('pricelist.html')

@main_bp.route('/calendar_page')
@login_required
def calendar_page():
    return render_template('calendar.html')

@main_bp.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html')

@main_bp.route('/users')
@role_required('admin')
def users_list():
    users = User.query.all()
    return render_template('users.html', users=users)

# ------------------ API: Дашборд и уведомления ------------------
@main_bp.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    active_orders = Order.query.filter(Order.status != 'completed').count()
    overdue_orders = Order.query.filter(Order.deadline < datetime.utcnow(), Order.status != 'completed').count()
    today_orders = Order.query.filter(func.date(Order.start_time) == datetime.utcnow().date()).count()
    balance = recalc_balance()
    low_stock = WarehouseItem.query.filter(WarehouseItem.quantity < 3).count()
    return jsonify({
        'active_orders': active_orders,
        'overdue_orders': overdue_orders,
        'today_orders': today_orders,
        'balance': balance,
        'low_stock': low_stock
    })

@main_bp.route('/api/notifications')
@login_required
def get_notifications():
    role = current_user.role
    notif = Notification.query.filter(
        (Notification.user_role.like(f'%{role}%')) | (Notification.user_id == current_user.id),
        Notification.is_read == False
    ).order_by(Notification.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'link': n.link,
        'created_at': n.created_at.isoformat()
    } for n in notif])

@main_bp.route('/api/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_notification_read(id):
    n = Notification.query.get_or_404(id)
    n.is_read = True
    db.session.commit()
    return jsonify({'status': 'ok'})

@main_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    role = current_user.role
    Notification.query.filter(
        (Notification.user_role.like(f'%{role}%')) | (Notification.user_id == current_user.id),
        Notification.is_read == False
    ).update({'is_read': True})
    db.session.commit()
    return jsonify({'status': 'ok'})

# ------------------ API: Склад ------------------
@main_bp.route('/api/warehouse', methods=['GET'])
@role_required('admin', 'manager')
def get_warehouse():
    items = WarehouseItem.query.all()
    return jsonify([{
        'id': i.id, 'name': i.name, 'quantity': i.quantity,
        'weight': i.weight, 'size': i.size, 'cost_price': i.cost_price,
        'price_with_markup': round(i.cost_price * 1.2, 2)
    } for i in items])

@main_bp.route('/api/warehouse', methods=['POST'])
@role_required('admin', 'manager')
def add_warehouse():
    data = request.json
    item = WarehouseItem(
        name=data['name'],
        quantity=data['quantity'],
        weight=data.get('weight', ''),
        size=data.get('size', ''),
        cost_price=data['cost_price']
    )
    db.session.add(item)
    add_transaction('expense', 'Покупка товара', data['cost_price'], f'Закупка: {data["name"]}')
    db.session.commit()
    return jsonify({'status': 'ok'})

@main_bp.route('/api/warehouse/<int:id>', methods=['DELETE'])
@role_required('admin', 'manager')
def delete_warehouse(id):
    item = WarehouseItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'status': 'ok'})

# ------------------ API: Сотрудники ------------------
@main_bp.route('/api/employees', methods=['GET'])
@role_required('admin', 'manager')
def get_employees():
    emps = Employee.query.filter_by(fired=False).all()
    return jsonify([{
        'id': e.id, 'full_name': e.full_name, 'passport': e.passport,
        'details': e.details, 'position': e.position, 'salary_value': e.salary_value
    } for e in emps])

@main_bp.route('/api/employees', methods=['POST'])
@role_required('admin', 'manager')
def add_employee():
    data = request.json
    emp = Employee(
        full_name=data['full_name'],
        passport=data.get('passport', ''),
        details=data.get('details', ''),
        position=data['position'],
        salary_value=data['salary_value']
    )
    db.session.add(emp)
    db.session.commit()
    return jsonify({'status': 'ok'})

@main_bp.route('/api/employees/<int:id>/fire', methods=['POST'])
@role_required('admin', 'manager')
def fire_employee(id):
    emp = Employee.query.get_or_404(id)
    emp.fired = True
    emp.fire_reason = request.json.get('reason', '')
    db.session.commit()
    return jsonify({'status': 'ok'})

# ------------------ API: Заказы ------------------
@main_bp.route('/api/orders', methods=['GET'])
@login_required
def get_orders():
    if current_user.role == 'master':
        master_emp = Employee.query.filter_by(full_name=current_user.full_name).first()
        if master_emp:
            orders = Order.query.filter_by(responsible_employee_id=master_emp.id).all()
        else:
            orders = []
    else:
        orders = Order.query.all()
    return jsonify([{
        'id': o.id, 'customer_name': o.customer_name, 'phone': o.phone,
        'device_model': o.device_model, 'main_problem': o.main_problem,
        'detected_problem': o.detected_problem, 'price': o.price,
        'deadline': o.deadline.isoformat(), 'start_time': o.start_time.isoformat(),
        'completed_at': o.completed_at.isoformat() if o.completed_at else None,
        'status': o.status, 'responsible_employee_id': o.responsible_employee_id,
        'is_checked': o.is_checked, 'checked_by': o.checked_by,
        'checked_at': o.checked_at.isoformat() if o.checked_at else None
    } for o in orders])

@main_bp.route('/api/orders', methods=['POST'])
@role_required('admin', 'receiver', 'manager')
def create_order():
    data = request.json
    # Проверка чёрного списка
    blacklisted = BlacklistClient.query.filter(
        (BlacklistClient.full_name == data['customer_name']) | 
        (BlacklistClient.phone == data['phone'])
    ).first()
    if blacklisted:
        return jsonify({'error': f'Клиент в чёрном списке. Причина: {blacklisted.reason}'}), 400
    order = Order(
        customer_name=data['customer_name'],
        phone=data['phone'],
        device_model=data['device_model'],
        serial_number=data.get('serial_number', ''),
        imei=data.get('imei', ''),
        main_problem=data.get('main_problem', ''),
        detected_problem=data.get('detected_problem', ''),
        price=data['price'],
        deadline=datetime.fromisoformat(data['deadline']),
        status='waiting_parts' if data.get('waiting_parts') else 'in_progress',
        responsible_employee_id=data['responsible_employee_id']
    )
    db.session.add(order)
    db.session.commit()
    add_transaction('income', 'Прием заказа', data['price'], f'Заказ №{order.id}')
    log_order_change(
        order_id=order.id,
        user_id=current_user.id,
        username=current_user.username,
        action='create',
        comment=f'Создан заказ на сумму {order.price} руб., мастер id={order.responsible_employee_id}'
    )
    return jsonify({'status': 'ok', 'id': order.id})

@main_bp.route('/api/orders/<int:id>', methods=['PUT'])
@role_required('admin', 'manager', 'receiver')
def update_order(id):
    order = Order.query.get_or_404(id)
    data = request.json
    order.customer_name = data.get('customer_name', order.customer_name)
    order.phone = data.get('phone', order.phone)
    order.device_model = data.get('device_model', order.device_model)
    order.main_problem = data.get('main_problem', order.main_problem)
    order.detected_problem = data.get('detected_problem', order.detected_problem)
    order.price = data.get('price', order.price)
    if 'deadline' in data:
        order.deadline = datetime.fromisoformat(data['deadline'])
    order.status = data.get('status', order.status)
    order.responsible_employee_id = data.get('responsible_employee_id', order.responsible_employee_id)
    db.session.commit()
    log_order_change(
        order_id=order.id,
        user_id=current_user.id,
        username=current_user.username,
        action='edit',
        comment='Изменены данные заказа'
    )
    return jsonify({'status': 'ok'})

@main_bp.route('/api/orders/<int:id>/complete', methods=['POST'])
@role_required('admin', 'manager', 'master')
def complete_order(id):
    used_parts = request.json.get('used_parts', False)
    order = Order.query.get_or_404(id)
    if order.status == 'completed':
        return jsonify({'error': 'Already completed'}), 400
    order.status = 'completed'
    order.completed_at = datetime.utcnow()
    master_percent = request.json.get('master_percent', 67)
    bonus_days = request.json.get('bonus_days', 3)
    bonus_percent = request.json.get('bonus_percent', 10)
    days_taken = (order.completed_at - order.start_time).total_seconds() / 86400
    base_salary = order.price * master_percent / 100
    factor = 1
    if days_taken < bonus_days:
        factor = 1 + bonus_percent/100
    elif days_taken > bonus_days:
        factor = 1 - bonus_percent/100
    final_salary = round(base_salary * factor, 2)
    add_transaction('expense', 'ЗП мастеру (ремонт)', final_salary, f'Заказ {order.id}')
    db.session.commit()
    WarrantyCard.create_for_order(order, 'work', f'Гарантия на выполненные работы по заказу #{order.id}', 14)
    # Если были использованы запчасти (можно определить по наличию записи в чек-листе или по полю refused_with_parts, лучше добавить поле used_parts)
    # Для простоты: если цена ремонта > 0 и не отказ, считаем что запчасти могли быть. Но логичнее добавить флаг.
    # Добавим опционально: если в запросе при завершении передан флаг used_parts = True, то создаём гарантию на запчасти.
    used_parts = request.json.get('used_parts', False)
    if used_parts:
        WarrantyCard.create_for_order(order, 'part', f'Гарантия на установленные запчасти по заказу #{order.id}', 30)
    db.session.commit()


    @main_bp.route('/api/warranty-cards', methods=['GET'])
    @login_required
    def get_warranty_cards():
        cards = WarrantyCard.query.all()
        return jsonify([{
            'id': c.id,
            'order_id': c.order_id,
            'warranty_type': c.warranty_type,
            'description': c.description,
            'valid_until': c.valid_until.isoformat(),
            'is_active': c.is_active,
            'created_at': c.created_at.isoformat()
        } for c in cards])

    @main_bp.route('/api/warranty-cards/<int:id>/deactivate', methods=['POST'])
    @role_required('admin', 'manager')
    def deactivate_warranty(id):
        card = WarrantyCard.query.get_or_404(id)
        card.is_active = False
        db.session.commit()
        return jsonify({'status': 'ok'})
    # Генерация PDF и отправка email
    pdf_buffer = generate_act_pdf_buffer(order)
    send_order_ready_email_with_act(order, pdf_buffer)
    log_order_change(
        order_id=order.id,
        user_id=current_user.id,
        username=current_user.username,
        action='complete',
        comment=f'Заказ завершён, зарплата мастера {final_salary} руб.'
    )
    return jsonify({'status': 'ok', 'final_salary': final_salary})

@main_bp.route('/api/orders/<int:id>/mark-checked', methods=['POST'])
@role_required('admin', 'manager')
def mark_checked(id):
    order = Order.query.get_or_404(id)
    data = request.json
    order.is_checked = True
    order.checked_by = data.get('checked_by', current_user.full_name or current_user.username)
    order.checked_at = datetime.utcnow()
    checklist = data.get('checklist', {})
    order.checklist_data = json.dumps(checklist, ensure_ascii=False)
    db.session.commit()
    log_order_change(
        order_id=order.id,
        user_id=current_user.id,
        username=current_user.username,
        action='check',
        comment=f'Техника проверена {order.checked_by}, чек-лист: {checklist}'
    )
    return jsonify({'status': 'ok'})

@main_bp.route('/api/orders/<int:id>/wait-parts', methods=['POST'])
@role_required('admin', 'manager', 'master')
def toggle_wait_parts(id):
    order = Order.query.get_or_404(id)
    if order.status == 'completed':
        return jsonify({'error': 'Completed'}), 400
    order.status = 'waiting_parts' if order.status != 'waiting_parts' else 'in_progress'
    db.session.commit()
    log_order_change(
        order_id=order.id,
        user_id=current_user.id,
        username=current_user.username,
        action='wait_parts',
        comment=f'Статус изменён на {order.status}'
    )
    return jsonify({'status': 'ok', 'new_status': order.status})

@main_bp.route('/api/orders/<int:id>/logs', methods=['GET'])
@login_required
def get_order_logs(id):
    logs = OrderLog.query.filter_by(order_id=id).order_by(OrderLog.created_at.desc()).all()
    return jsonify([{
        'id': l.id,
        'username': l.username or 'Система',
        'action': l.action,
        'field_name': l.field_name,
        'old_value': l.old_value,
        'new_value': l.new_value,
        'comment': l.comment,
        'created_at': l.created_at.isoformat()
    } for l in logs])

# ------------------ Генерация PDF для скачивания ------------------
@main_bp.route('/api/orders/<int:id>/pdf-act')
@login_required
def generate_act_pdf(id):
    order = Order.query.get_or_404(id)
    if order.status != 'completed':
        flash('Акт можно сформировать только для завершённого заказа', 'warning')
        return redirect(url_for('main.orders_page'))
    pdf_buffer = generate_act_pdf_buffer(order)
    return send_file(pdf_buffer, as_attachment=True, download_name=f'act_order_{order.id}.pdf', mimetype='application/pdf')

# ------------------ API: Финансы ------------------
@main_bp.route('/api/finance/transactions', methods=['GET'])
@role_required('admin', 'accountant', 'manager')
def get_transactions():
    trans = FinanceTransaction.query.order_by(FinanceTransaction.date.desc()).all()
    return jsonify([{
        'id': t.id, 'type': t.type, 'category': t.category,
        'amount': t.amount, 'date': t.date.isoformat(), 'description': t.description
    } for t in trans])

@main_bp.route('/api/finance/balance', methods=['GET'])
@login_required
def get_balance():
    return jsonify({'balance': recalc_balance()})

@main_bp.route('/api/finance/transaction', methods=['POST'])
@role_required('admin', 'accountant', 'manager')
def add_finance():
    data = request.json
    add_transaction(data['type'], data['category'], data['amount'], data.get('description', ''))
    return jsonify({'status': 'ok', 'balance': recalc_balance()})

# ------------------ API: Ежемесячные платежи ------------------
@main_bp.route('/api/recurring', methods=['GET'])
@role_required('admin', 'accountant')
def get_recurring():
    items = RecurringPayment.query.all()
    return jsonify([{
        'id': i.id, 'category': i.category, 'amount': i.amount,
        'description': i.description, 'last_applied_month': i.last_applied_month
    } for i in items])

@main_bp.route('/api/recurring', methods=['POST'])
@role_required('admin', 'accountant')
def add_recurring():
    data = request.json
    rec = RecurringPayment(
        category=data['category'],
        amount=data['amount'],
        description=data.get('description', ''),
        last_applied_month=None
    )
    db.session.add(rec)
    db.session.commit()
    return jsonify({'status': 'ok'})

@main_bp.route('/api/recurring/<int:id>', methods=['DELETE'])
@role_required('admin', 'accountant')
def delete_recurring(id):
    rec = RecurringPayment.query.get_or_404(id)
    db.session.delete(rec)
    db.session.commit()
    return jsonify({'status': 'ok'})

@main_bp.route('/api/recurring/apply', methods=['POST'])
@role_required('admin', 'accountant')
def apply_recurring():
    now = datetime.utcnow()
    current_ym = now.strftime('%Y-%m')
    applied = 0
    for pay in RecurringPayment.query.all():
        if pay.last_applied_month != current_ym:
            add_transaction('expense', pay.category, pay.amount, pay.description or 'Ежемесячный платёж')
            pay.last_applied_month = current_ym
            applied += 1
    db.session.commit()
    return jsonify({'status': 'ok', 'applied': applied})

# ------------------ API: Чёрный список ------------------
@main_bp.route('/api/blacklist', methods=['GET'])
@role_required('admin', 'manager')
def get_blacklist():
    items = BlacklistClient.query.all()
    return jsonify([{'id': i.id, 'full_name': i.full_name, 'phone': i.phone, 'reason': i.reason} for i in items])

@main_bp.route('/api/blacklist', methods=['POST'])
@role_required('admin', 'manager')
def add_blacklist():
    data = request.json
    bl = BlacklistClient(full_name=data['full_name'], phone=data['phone'], reason=data.get('reason', ''))
    db.session.add(bl)
    db.session.commit()
    return jsonify({'status': 'ok'})

@main_bp.route('/api/blacklist/<int:id>', methods=['DELETE'])
@role_required('admin', 'manager')
def del_blacklist(id):
    bl = BlacklistClient.query.get_or_404(id)
    db.session.delete(bl)
    db.session.commit()
    return jsonify({'status': 'ok'})

# ------------------ API: Прайс ------------------
@main_bp.route('/api/pricelist', methods=['GET'])
@login_required
def get_pricelist():
    items = PriceItem.query.all()
    return jsonify([{'id': i.id, 'name': i.name, 'execution_time': i.execution_time, 'price': i.price} for i in items])

@main_bp.route('/api/pricelist', methods=['POST'])
@role_required('admin', 'accountant', 'manager')
def add_price():
    data = request.json
    price = PriceItem(name=data['name'], execution_time=data.get('execution_time', ''), price=data['price'])
    db.session.add(price)
    db.session.commit()
    return jsonify({'status': 'ok'})

@main_bp.route('/api/pricelist/<int:id>', methods=['DELETE'])
@role_required('admin', 'accountant', 'manager')
def del_price(id):
    price = PriceItem.query.get_or_404(id)
    db.session.delete(price)
    db.session.commit()
    return jsonify({'status': 'ok'})

# ------------------ API: Календарь ------------------
@main_bp.route('/api/daily-orders', methods=['GET'])
@login_required
def daily_orders():
    date_str = request.args.get('date')
    if not date_str:
        return jsonify([])
    target = datetime.strptime(date_str, '%Y-%m-%d').date()
    orders = Order.query.filter(func.date(Order.start_time) == target).all()
    return jsonify([{
        'id': o.id, 'customer_name': o.customer_name, 'device_model': o.device_model,
        'price': o.price, 'status': o.status
    } for o in orders])

# ------------------ Сброс демо-данных ------------------
@main_bp.route('/api/reset-demo', methods=['POST'])
@role_required('admin')
def reset_demo():
    WarehouseItem.query.delete()
    Employee.query.delete()
    Order.query.delete()
    FinanceTransaction.query.delete()
    BlacklistClient.query.delete()
    PriceItem.query.delete()
    RecurringPayment.query.delete()
    Notification.query.delete()
    OrderLog.query.delete()
    demo_warehouse = [
        WarehouseItem(name="Дисплей iPhone", quantity=5, weight="0.1кг", size="6.1", cost_price=1500),
        WarehouseItem(name="Аккумулятор", quantity=10, weight="50г", size="стандарт", cost_price=800)
    ]
    demo_employees = [
        Employee(full_name="Иван Петров", passport="4512 345678", details="счет 40817", position="repair", salary_value=67),
        Employee(full_name="Ольга Смирнова", passport="4512 111222", details="", position="reception", salary_value=30000)
    ]
    demo_pricelist = [
        PriceItem(name="Замена экрана", execution_time="2 часа", price=2000),
        PriceItem(name="Чистка от пыли", execution_time="1 день", price=800)
    ]
    demo_recurring = [
        RecurringPayment(category="Аренда помещения", amount=15000, description="Аренда"),
        RecurringPayment(category="Электроэнергия", amount=3500, description="Свет"),
        RecurringPayment(category="Водоснабжение", amount=1200, description="Вода"),
        RecurringPayment(category="Отопление", amount=2800, description="Отопление"),
        RecurringPayment(category="Кредитный платёж", amount=5000, description="Кредит")
    ]
    for item in demo_warehouse:
        db.session.add(item)
    for emp in demo_employees:
        db.session.add(emp)
    for price in demo_pricelist:
        db.session.add(price)
    for rec in demo_recurring:
        db.session.add(rec)
    from datetime import timedelta
    deadline = datetime.utcnow() + timedelta(days=2)
    demo_order = Order(
        customer_name="Алексей", phone="+79111234567", device_model="Xiaomi Note",
        serial_number="SN123", imei="356789", main_problem="Не включается",
        detected_problem="Батарея", price=2500, deadline=deadline,
        start_time=datetime.utcnow() - timedelta(days=1), status="in_progress",
        responsible_employee_id=1, is_checked=False
    )
    db.session.add(demo_order)
    add_transaction('income', 'Прием заказа', 2500, 'Заказ №1 (демо)')
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Демо-данные восстановлены'})

@main_bp.route('/warranty')
@login_required
def warranty_page():
    return render_template('warranty.html')