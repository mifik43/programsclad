from flask import Flask
from flask_login import LoginManager
from models import db, User
from auth import auth_bp
from routes import main_bp
from apscheduler.schedulers.background import BackgroundScheduler
from utils import create_backup
from api_v1 import api_bp



app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///service.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.register_blueprint(api_bp)


db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(main_bp)

with app.app_context():
    db.create_all()
    if User.query.count() == 0:
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()


scheduler = BackgroundScheduler()
# Еженедельный бэкап каждое воскресенье в 3:00
scheduler.add_job(func=create_backup, trigger='cron', day_of_week='sun', hour=3, minute=0, args=[app])
scheduler.start()

# При выключении приложения останавливаем планировщик
import atexit
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    app.run(debug=True)
