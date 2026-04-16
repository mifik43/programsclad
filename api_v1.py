from flask import Blueprint, request, jsonify
from functools import wraps
from models import db, Order, ApiKey, BlacklistClient
from datetime import datetime
import secrets

api_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        key = ApiKey.query.filter_by(key=api_key, active=True).first()
        if not key:
            return jsonify({'error': 'Invalid API key'}), 401
        key.last_used = datetime.utcnow()
        db.session.commit()
        return f(*args, **kwargs)
    return decorated

@api_bp.route('/orders', methods=['GET'])
@api_key_required
def get_orders():
    status = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)
    query = Order.query
    if status:
        query = query.filter_by(status=status)
    orders = query.order_by(Order.id.desc()).limit(limit).all()
    return jsonify([{
        'id': o.id,
        'customer_name': o.customer_name,
        'phone': o.phone,
        'device_model': o.device_model,
        'status': o.status,
        'price': o.price,
        'created_at': o.start_time.isoformat(),
        'deadline': o.deadline.isoformat()
    } for o in orders])

@api_bp.route('/orders/<int:id>', methods=['GET'])
@api_key_required
def get_order(id):
    order = Order.query.get_or_404(id)
    return jsonify({
        'id': order.id,
        'customer_name': order.customer_name,
        'phone': order.phone,
        'device_model': order.device_model,
        'main_problem': order.main_problem,
        'detected_problem': order.detected_problem,
        'price': order.price,
        'status': order.status,
        'deadline': order.deadline.isoformat(),
        'start_time': order.start_time.isoformat(),
        'completed_at': order.completed_at.isoformat() if order.completed_at else None,
        'is_checked': order.is_checked
    })

@api_bp.route('/orders', methods=['POST'])
@api_key_required
def create_order():
    data = request.json
    required = ['customer_name', 'phone', 'price', 'deadline', 'responsible_employee_id']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing {field}'}), 400
    blacklisted = BlacklistClient.query.filter(
        (BlacklistClient.full_name == data['customer_name']) |
        (BlacklistClient.phone == data['phone'])
    ).first()
    if blacklisted:
        return jsonify({'error': 'Customer is blacklisted'}), 400
    order = Order(
        customer_name=data['customer_name'],
        phone=data['phone'],
        device_model=data.get('device_model', ''),
        serial_number=data.get('serial_number', ''),
        main_problem=data.get('main_problem', ''),
        detected_problem=data.get('detected_problem', ''),
        price=data['price'],
        deadline=datetime.fromisoformat(data['deadline']),
        status=data.get('status', 'in_progress'),
        responsible_employee_id=data['responsible_employee_id']
    )
    db.session.add(order)
    db.session.commit()
    return jsonify({'id': order.id, 'status': 'created'}), 201

@api_bp.route('/orders/<int:id>/status', methods=['PUT'])
@api_key_required
def update_order_status(id):
    data = request.json
    new_status = data.get('status')
    if new_status not in ['in_progress', 'waiting_parts', 'completed']:
        return jsonify({'error': 'Invalid status'}), 400
    order = Order.query.get_or_404(id)
    order.status = new_status
    if new_status == 'completed' and not order.completed_at:
        order.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'ok'})