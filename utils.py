import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from threading import Thread
from datetime import datetime
from models import db, Order, Notification
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm

def send_email_with_attachment_async(subject, recipient, html_body, pdf_buffer=None, filename="act.pdf"):
    """Асинхронная отправка email с вложением PDF (эмуляция вывода в консоль)"""
    def send():
        print(f"=== EMAIL TO {recipient} ===")
        print(f"Subject: {subject}")
        print(f"Body: {html_body}")
        if pdf_buffer:
            print(f"Attachment: {filename} ({len(pdf_buffer.getvalue())} bytes)")
        print("===========================")
    Thread(target=send).start()

def send_order_ready_email_with_act(order, pdf_buffer):
    """Отправка клиенту уведомления о готовности с актом PDF"""
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
    """Генерирует PDF-акт выполненных работ и возвращает BytesIO буфер"""
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

def check_warranty_expiry():
    from models import WarrantyCard
    now = datetime.utcnow()
    # За 3 дня до истечения
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
            link=f'/warranty'
        )