from app import app, db
from models import User

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin', full_name='Administrator')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created: admin / admin123")
    else:
        print("ℹ️ Admin already exists")
    print("✅ Database initialized.")