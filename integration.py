import json
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import url_for
from models import db, PaymentTransaction, FiscalReceipt

# ---------- Эквайринг (симуляция) ----------
def create_payment_link(order_id, amount, customer_name, phone):
    """Создаёт фиктивную ссылку на оплату (в реальном проекте – запрос к платежному шлюзу)"""
    transaction_id = str(uuid.uuid4())
    payment_url = f"https://demo-payment.example.com/pay?order={order_id}&amount={amount}&tid={transaction_id}"
    # Сохраняем транзакцию в БД
    payment = PaymentTransaction(
        order_id=order_id,
        amount=amount,
        status='pending',
        payment_method='online',
        payment_url=payment_url,
        transaction_id=transaction_id
    )
    db.session.add(payment)
    db.session.commit()
    return payment_url, transaction_id

def check_payment_status(transaction_id):
    """Проверка статуса платежа (симуляция – всегда 'paid' после вызова)"""
    payment = PaymentTransaction.query.filter_by(transaction_id=transaction_id).first()
    if payment and payment.status == 'pending':
        # Имитируем успешную оплату через 5 секунд (в реальном проекте – вебхук)
        payment.status = 'paid'
        payment.paid_at = datetime.utcnow()
        db.session.commit()
    return payment.status if payment else 'not_found'

# ---------- Онлайн-касса (фискализация) ----------
def generate_receipt(order_id, amount, items_list, tax_system='usn_income'):
    """Генерирует чек (в реальном проекте – отправка в ККТ)"""
    receipt_number = f"RE-{order_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    receipt = FiscalReceipt(
        order_id=order_id,
        receipt_number=receipt_number,
        amount=amount,
        tax_system=tax_system,
        items=json.dumps(items_list, ensure_ascii=False),
        fiscal_sign=str(uuid.uuid4())[:10]
    )
    db.session.add(receipt)
    db.session.commit()
    # Печать чека в консоль (эмуляция)
    print(f"=== ФИСКАЛЬНЫЙ ЧЕК #{receipt_number} ===")
    print(f"Сумма: {amount} руб.")
    print(f"Товары/услуги: {items_list}")
    print(f"Система налогообложения: {tax_system}")
    print(f"Фискальный признак: {receipt.fiscal_sign}")
    print("=================================")
    return receipt_number

# ---------- Экспорт в 1С (XML) ----------
def export_order_to_1c_xml(order):
    """Экспорт заказа в формат XML для 1С"""
    root = ET.Element("Order")
    ET.SubElement(root, "ID").text = str(order.id)
    ET.SubElement(root, "CustomerName").text = order.customer_name
    ET.SubElement(root, "Phone").text = order.phone or ''
    ET.SubElement(root, "DeviceModel").text = order.device_model or ''
    ET.SubElement(root, "Problem").text = order.main_problem or ''
    ET.SubElement(root, "Price").text = str(order.price)
    ET.SubElement(root, "Status").text = order.status
    ET.SubElement(root, "CreatedAt").text = order.start_time.isoformat()
    if order.completed_at:
        ET.SubElement(root, "CompletedAt").text = order.completed_at.isoformat()
    xml_str = ET.tostring(root, encoding='unicode')
    return xml_str

def export_orders_to_1c_json(orders):
    """Экспорт списка заказов в JSON для 1С"""
    result = []
    for order in orders:
        result.append({
            'id': order.id,
            'customer_name': order.customer_name,
            'phone': order.phone,
            'device_model': order.device_model,
            'main_problem': order.main_problem,
            'price': order.price,
            'status': order.status,
            'start_time': order.start_time.isoformat(),
            'completed_at': order.completed_at.isoformat() if order.completed_at else None
        })
    return json.dumps(result, ensure_ascii=False, indent=2)