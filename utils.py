import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from threading import Thread
from datetime import datetime, timedelta
from models import db, Order, Notification, WarrantyCard, Backup
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
import os
import json
import shutil
import pandas as pd
import plotly.express as px
import plotly.utils
from models import Order, FinanceTransaction, Employee




VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY')
VAPID_CLAIMS = {"sub": "mailto:admin@service-center.ru"}

def send_push_notification(subscription_info, title, body, url='/'):
    try:
        pusher = WebPusher(VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIMS)
        payload = json.dumps({'title': title, 'body': body, 'url': url})
        pusher.send(subscription_info, payload)
    except Exception as e:
        print(f"Push error: {e}")


def send_email_with_attachment_async(subject, recipient, html_body, pdf_buffer=None, filename="act.pdf"):
    def send():
        print(f"=== EMAIL TO {recipient} ===")
        print(f"Subject: {subject}")
        print(f"Body: {html_body}")
        if pdf_buffer:
            print(f"Attachment: {filename} ({len(pdf_buffer.getvalue())} bytes)")
        print("===========================")
    Thread(target=send).start()

def send_order_ready_email_with_act(order, pdf_buffer):
    if not order.phone or '@' not in order.phone:
        return
    subject = f"Ваш заказ #{order.id} готов в сервисном центре"
    body = f"""
    <h3>Уважаемый {order.customer_name}!</h3>
    <p>Ваш заказ #{order.id} ({order.device_model}) выполнен.</p>
    <p>Вы можете забрать устройство в нашем сервисном центре.</p>
    <p>Во вложении акт выполненных работ.</p>
    <p>С уважением, команда сервиса.</p>
    """
    send_email_with_attachment_async(subject, order.phone, body, pdf_buffer, f"act_order_{order.id}.pdf")

def generate_act_pdf_buffer(order):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1, spaceAfter=12)
    normal_style = styles['Normal']
    story = []
    story.append(Paragraph("Акт выполненных работ", title_style))
    story.append(Spacer(1, 12))
    data = [
        ["Номер заказа:", str(order.id)],
        ["Дата приёма:", order.start_time.strftime('%d.%m.%Y')],
        ["Дата выполнения:", order.completed_at.strftime('%d.%m.%Y') if order.completed_at else '—'],
        ["Клиент:", order.customer_name],
        ["Телефон:", order.phone or '—'],
        ["Устройство:", order.device_model or '—'],
        ["Серийный номер:", order.serial_number or '—'],
        ["Заявленная проблема:", order.main_problem or '—'],
        ["Выполненные работы:", order.detected_problem or '—'],
        ["Стоимость работ:", f"{order.price} руб."],
        ["Гарантия:", "2 недели на выполненные работы"],
    ]
    if order.is_checked and order.checked_by:
        data.append(["Проверено:", f"{order.checked_by}, {order.checked_at.strftime('%d.%m.%Y %H:%M')}"])
    t = Table(data, colWidths=[50*mm, 100*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Подписи сторон:", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("__________________ (Заказчик)", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("__________________ (Исполнитель)", normal_style))
    doc.build(story)
    buffer.seek(0)
    return buffer

def check_deadlines_and_notify():
    now = datetime.utcnow()
    overdue_orders = Order.query.filter(Order.deadline < now, Order.status != 'completed').all()
    for order in overdue_orders:
        existing = Notification.query.filter(
            Notification.title.like(f'%Просрочен заказ #{order.id}%'),
            Notification.created_at > datetime(now.year, now.month, now.day)
        ).first()
        if not existing:
            Notification.create_notification(
                role='admin,manager',
                title=f'Просрочен заказ #{order.id}',
                message=f'Заказ {order.customer_name} ({order.device_model}) просрочен на {(now - order.deadline).days} дней',
                link=f'/orders_page?highlight={order.id}'
            )
    # Проверка истечения гарантий
    threshold = now + timedelta(days=3)
    expiring_cards = WarrantyCard.query.filter(
        WarrantyCard.valid_until <= threshold,
        WarrantyCard.valid_until > now,
        WarrantyCard.is_active == True
    ).all()
    for card in expiring_cards:
        Notification.create_notification(
            role='admin,manager',
            title=f'Истекает гарантия по заказу #{card.order_id}',
            message=f'Гарантия {card.description} истекает {card.valid_until.strftime("%d.%m.%Y")}',
            link='/warranty'
        )

def log_order_change(order_id, user_id, username, action, field_name=None, old_value=None, new_value=None, comment=None):
    from models import db, OrderLog
    log = OrderLog(
        order_id=order_id,
        user_id=user_id,
        username=username,
        action=action,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        comment=comment
    )
    db.session.add(log)
    db.session.commit()


def create_backup(app=None):
    """Создаёт резервную копию базы данных"""
    with app.app_context():
        backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        if db_path.startswith('instance/'):
            db_path = os.path.join(os.path.dirname(__file__), db_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'backup_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.copy2(db_path, backup_path)
        size = os.path.getsize(backup_path)
        backup = Backup(filename=backup_name, size=size, description=f'Автоматический бэкап от {datetime.now()}')
        db.session.add(backup)
        db.session.commit()
        # Удаляем старые бэкапы (оставляем последние 10)
        backups = Backup.query.order_by(Backup.created_at.desc()).all()
        for old in backups[10:]:
            old_path = os.path.join(backup_dir, old.filename)
            if os.path.exists(old_path):
                os.remove(old_path)
            db.session.delete(old)
        db.session.commit()
        return backup_name

def list_backups():
    """Возвращает список резервных копий"""
    return Backup.query.order_by(Backup.created_at.desc()).all()

def restore_backup(backup_id, app):
    """Восстанавливает базу данных из выбранного бэкапа"""
    backup = Backup.query.get(backup_id)
    if not backup:
        raise ValueError("Бэкап не найден")
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    backup_path = os.path.join(backup_dir, backup.filename)
    if not os.path.exists(backup_path):
        raise FileNotFoundError("Файл бэкапа отсутствует")
    # Закрываем текущее соединение с БД
    db.session.remove()
    db.engine.dispose()
    # Копируем бэкап в основную БД
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if db_path.startswith('instance/'):
        db_path = os.path.join(os.path.dirname(__file__), db_path)
    shutil.copy2(backup_path, db_path)
    # Перезапускаем соединение
    with app.app_context():
        db.create_all()  # убедимся, что таблицы есть
    return True

def get_daily_kpis():
    """Расчёт KPI за последние 30 дней"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)
    
    orders = Order.query.filter(Order.start_time >= start_date).all()
    transactions = FinanceTransaction.query.filter(FinanceTransaction.date >= start_date).all()
    
    df_orders = pd.DataFrame([{
        'date': o.start_time.date(),
        'price': o.price,
        'status': o.status,
        'master_id': o.responsible_employee_id
    } for o in orders])
    
    df_income = pd.DataFrame([{
        'date': t.date.date(),
        'amount': t.amount
    } for t in transactions if t.type == 'income'])
    
    # Расчёт метрик
    total_revenue = df_income['amount'].sum()
    avg_check = df_income['amount'].mean() if len(df_income) > 0 else 0
    completed_orders = len(df_orders[df_orders['status'] == 'completed'])
    avg_completion_days = 0
    
    # Расчёт среднего времени выполнения заказов
    completed_orders_data = Order.query.filter(Order.status == 'completed', Order.completed_at.isnot(None)).all()
    if completed_orders_data:
        completion_times = [(o.completed_at - o.start_time).days for o in completed_orders_data]
        avg_completion_days = sum(completion_times) / len(completion_times)
    
    return {
        'total_revenue': float(total_revenue),
        'avg_check': float(avg_check),
        'completed_orders': completed_orders,
        'avg_completion_days': round(avg_completion_days, 1),
        'period_days': 30
    }

def get_revenue_by_day():
    """Выручка по дням за последние 30 дней для линейного графика"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)
    
    transactions = FinanceTransaction.query.filter(
        FinanceTransaction.type == 'income',
        FinanceTransaction.date >= start_date
    ).all()
    
    df = pd.DataFrame([{
        'date': t.date.date(),
        'amount': t.amount
    } for t in transactions])
    
    if df.empty:
        return {'dates': [], 'revenues': []}
    
    daily_revenue = df.groupby('date')['amount'].sum().reset_index()
    
    fig = px.line(daily_revenue, x='date', y='amount', title='Динамика выручки')
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    return {
        'dates': daily_revenue['date'].dt.strftime('%d.%m').tolist(),
        'revenues': daily_revenue['amount'].tolist(),
        'graph_json': graph_json
    }

def get_popular_services():
    """Самые популярные услуги (по моделям устройств)"""
    orders = Order.query.filter(Order.device_model.isnot(None)).all()
    df = pd.DataFrame([{'device': o.device_model} for o in orders])
    
    if df.empty:
        return {'models': [], 'counts': []}
    
    popular = df['device'].value_counts().head(10).reset_index()
    popular.columns = ['device', 'count']
    
    fig = px.bar(popular, x='device', y='count', title='Топ-10 моделей устройств')
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    return {
        'models': popular['device'].tolist(),
        'counts': popular['count'].tolist(),
        'graph_json': graph_json
    }

def get_master_performance():
    """Производительность мастеров (количество завершённых заказов)"""
    masters = Employee.query.filter_by(position='repair', fired=False).all()
    performance = []
    
    for master in masters:
        completed = Order.query.filter_by(
            responsible_employee_id=master.id,
            status='completed'
        ).count()
        performance.append({'master': master.full_name, 'completed': completed})
    
    df = pd.DataFrame(performance)
    
    if df.empty:
        return {'masters': [], 'completed': [], 'graph_json': None}
    
    fig = px.bar(df, x='master', y='completed', title='Количество завершённых заказов')
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    return {
        'masters': df['master'].tolist(),
        'completed': df['completed'].tolist(),
        'graph_json': graph_json
    }