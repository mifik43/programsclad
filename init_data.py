from app import app
from models import db, User, Employee, WarehouseItem, PriceItem, RecurringPayment
with app.app_context():
    if User.query.count() == 0:
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    if Employee.query.count() == 0:
        db.session.add(Employee(full_name='Иван Мастер', position='repair', salary_value=67))
        db.session.add(Employee(full_name='Ольга Приёмщик', position='reception', salary_value=30000))
        db.session.commit()
    if WarehouseItem.query.count() == 0:
        db.session.add(WarehouseItem(name='Дисплей iPhone', quantity=5, cost_price=1500))
        db.session.add(WarehouseItem(name='Аккумулятор', quantity=10, cost_price=800))
        db.session.commit()
    if PriceItem.query.count() == 0:
        db.session.add(PriceItem(name='Замена экрана', execution_time='2 часа', price=2000))
        db.session.add(PriceItem(name='Чистка', execution_time='1 день', price=800))
        db.session.commit()
    if RecurringPayment.query.count() == 0:
        db.session.add(RecurringPayment(category='Аренда', amount=15000))
        db.session.add(RecurringPayment(category='Электричество', amount=3500))
        db.session.add(RecurringPayment(category='Кредит', amount=5000))
        db.session.commit()