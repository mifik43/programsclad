import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from threading import Thread
from datetime import datetime, timedelta
from models import db, Order, Notification, WarrantyCard, Backup
import io
import os
import shutil
import qrcode
import base64
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm

# ---------- Email (эмуляция) ----------
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

# ---------- Генерация PDF (акт, смета, договор) ----------
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

def generate_estimate_pdf_buffer(order):
    """Смета на ремонт"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1, spaceAfter=12)
    story = []
    story.append(Paragraph("Смета на ремонт", title_style))
    story.append(Spacer(1, 12))
    data = [
        ["Заказ №", str(order.id)],
        ["Клиент", order.customer_name],
        ["Телефон", order.phone or '—'],
        ["Устройство", order.device_model or '—'],
        ["Заявленная проблема", order.main_problem or '—'],
        ["Предполагаемые работы", order.detected_problem or '—'],
        ["Стоимость работ", f"{order.price} руб."],
        ["Срок выполнения", order.deadline.strftime('%d.%m.%Y') if order.deadline else '—']
    ]
    t = Table(data, colWidths=[50*mm, 100*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Смета действительна в течение 3 дней.", styles['Normal']))
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_contract_pdf_buffer(order):
    """Договор на оказание услуг"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    normal_style = styles['Normal']
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1, spaceAfter=12)
    story = []
    story.append(Paragraph("Договор на оказание услуг", title_style))
    story.append(Spacer(1, 12))
    contract_text = f"""
    <b>г. _______________</b> <b>«___» _________ 20__ г.</b><br/><br/>
    <b>Исполнитель:</b> Сервисный центр «Мастер», в лице администратора, действующего на основании Устава.<br/>
    <b>Заказчик:</b> {order.customer_name}, {order.phone}.<br/><br/>
    <b>1. Предмет договора</b><br/>
    Исполнитель обязуется выполнить ремонт устройства <b>{order.device_model}</b> согласно заявленной проблеме: 
    <i>{order.main_problem}</i>, а Заказчик обязуется принять и оплатить выполненные работы.<br/><br/>
    <b>2. Стоимость работ и порядок расчётов</b><br/>
    Стоимость работ составляет <b>{order.price} руб.</b> Оплата производится при приёме заказа.<br/><br/>
    <b>3. Сроки выполнения</b><br/>
    Ремонт должен быть выполнен до <b>{order.deadline.strftime('%d.%m.%Y')}</b>.<br/><br/>
    <b>4. Гарантийные обязательства</b><br/>
    Исполнитель предоставляет гарантию 14 дней на выполненные работы.<br/><br/>
    <b>5. Ответственность сторон</b><br/>
    Исполнитель не несёт ответственности за скрытые дефекты устройства, не выявленные при диагностике.<br/><br/>
    <b>Подписи сторон:</b><br/>
    Исполнитель: __________________<br/>
    Заказчик: __________________<br/>
    """
    story.append(Paragraph(contract_text, normal_style))
    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------- QR-код ----------
def generate_order_qr(order_id, base_url):
    url = f"{base_url}/track/{order_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"

# ---------- Уведомления о дедлайнах и гарантиях ----------
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

# ---------- Логирование изменений заказа ----------
def log_order_change(order_id, user_id, username, action, field_name=None, old_value=None, new_value=None, comment=None):
    from models import OrderLog
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

# ---------- Резервное копирование (локальное и облачное) ----------
def create_backup(app=None):
    """Создаёт локальную резервную копию БД"""
    if app is None:
        from flask import current_app
        app = current_app
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

def restore_backup(backup_id, app):
    """Восстанавливает БД из бэкапа"""
    backup = Backup.query.get(backup_id)
    if not backup:
        raise ValueError("Бэкап не найден")
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    backup_path = os.path.join(backup_dir, backup.filename)
    if not os.path.exists(backup_path):
        raise FileNotFoundError("Файл бэкапа отсутствует")
    db.session.remove()
    db.engine.dispose()
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if db_path.startswith('instance/'):
        db_path = os.path.join(os.path.dirname(__file__), db_path)
    shutil.copy2(backup_path, db_path)
    with app.app_context():
        db.create_all()
    return True

def list_backups():
    return Backup.query.order_by(Backup.created_at.desc()).all()

def upload_backup_to_yadisk(backup_path, backup_name, token):
    """Загружает бэкап на Яндекс.Диск"""
    try:
        import yadisk
        y = yadisk.YaDisk(token=token)
        if not y.exists('/service_backups'):
            y.mkdir('/service_backups')
        remote_path = f'/service_backups/{backup_name}'
        y.upload(backup_path, remote_path)
        return True
    except Exception as e:
        print(f"Ошибка загрузки на Яндекс.Диск: {e}")
        return False

def create_backup_with_cloud(app):
    """Создаёт бэкап и загружает в облако"""
    with app.app_context():
        backup_name = create_backup(app)
        if backup_name:
            backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
            backup_path = os.path.join(backup_dir, backup_name)
            token = app.config.get('YADISK_TOKEN')
            if token:
                upload_backup_to_yadisk(backup_path, backup_name, token)
        return backup_name