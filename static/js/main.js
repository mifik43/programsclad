// Функции для работы с заказами, включая редактирование и проверку
async function loadOrders() {
    const res = await fetch('/api/orders');
    const orders = await res.json();
    const tbody = document.getElementById('ordersTable');
    tbody.innerHTML = '';
    orders.forEach(o => {
        const deadlineDate = new Date(o.deadline);
        const now = new Date();
        const diff = deadlineDate - now;
        const timerText = o.status === 'completed' ? 'Завершён' : (diff > 0 ? Math.floor(diff / 86400000) + 'д ' + Math.floor((diff % 86400000) / 3600000) + 'ч' : 'Просрочен');
        const statusBadge = o.status === 'in_progress' ? '<span class="badge bg-warning">В работе</span>' : (o.status === 'waiting_parts' ? '<span class="badge bg-info">Ждём запчасть</span>' : '<span class="badge bg-success">Завершён</span>');
        const checkedBadge = o.is_checked ? '<span class="badge bg-success">✓ Проверено</span>' : '<span class="badge bg-secondary">Не проверено</span>';
        const row = `<tr>
            <td>${o.id}</td>
            <td>${o.customer_name}<br><small>${o.phone}</small></td>
            <td>${o.device_model}</td>
            <td>${o.price}₽</td>
            <td class="timer-cell" data-deadline="${o.deadline}">${timerText}</td>
            <td>${statusBadge}</td>
            <td>${checkedBadge}</td>
            <td>
                <button class="btn btn-sm btn-info edit-order" data-id="${o.id}">✏️ Ред.</button>
                ${!o.is_checked && o.status === 'completed' ? `<button class="btn btn-sm btn-warning check-order" data-id="${o.id}">🔍 Проверить</button>` : ''}
                <button class="btn btn-sm btn-success complete-order" data-id="${o.id}" ${o.status === 'completed' ? 'disabled' : ''}>✅ Завершить</button>
            </td>
        </tr>`;
        tbody.insertAdjacentHTML('beforeend', row);
    });
    attachOrderButtons();
}
function attachOrderButtons() {
    document.querySelectorAll('.edit-order').forEach(btn => btn.addEventListener('click', () => openEditModal(btn.dataset.id)));
    document.querySelectorAll('.check-order').forEach(btn => btn.addEventListener('click', () => openCheckModal(btn.dataset.id)));
    document.querySelectorAll('.complete-order').forEach(btn => btn.addEventListener('click', async (e) => {
        const id = btn.dataset.id;
        const masterPercent = prompt("Процент мастеру от стоимости (по умолчанию 67):", 67);
        const bonusDays = prompt("Бонусные дни (по умолч. 3):", 3);
        const bonusPercent = prompt("Бонус/штраф % (по умолч. 10):", 10);
        await fetch(`/api/orders/${id}/complete`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({master_percent: parseFloat(masterPercent), bonus_days: parseInt(bonusDays), bonus_percent: parseFloat(bonusPercent)})
        });
        loadOrders();
        loadBalance();
    }));
}
async function openEditModal(id) {
    const res = await fetch('/api/orders');
    const orders = await res.json();
    const order = orders.find(o => o.id == id);
    if (!order) return;
    document.getElementById('editOrderId').value = order.id;
    document.getElementById('editCustomer').value = order.customer_name;
    document.getElementById('editPhone').value = order.phone;
    document.getElementById('editModel').value = order.device_model;
    document.getElementById('editProblem').value = order.main_problem;
    document.getElementById('editPrice').value = order.price;
    if (order.deadline) document.getElementById('editDeadline').value = order.deadline.slice(0,16);
    document.getElementById('editStatus').value = order.status;
    new bootstrap.Modal(document.getElementById('editOrderModal')).show();
}
document.getElementById('saveOrderEdit')?.addEventListener('click', async () => {
    const id = document.getElementById('editOrderId').value;
    const payload = {
        customer_name: document.getElementById('editCustomer').value,
        phone: document.getElementById('editPhone').value,
        device_model: document.getElementById('editModel').value,
        main_problem: document.getElementById('editProblem').value,
        price: parseFloat(document.getElementById('editPrice').value),
        deadline: document.getElementById('editDeadline').value,
        status: document.getElementById('editStatus').value
    };
    await fetch(`/api/orders/${id}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    bootstrap.Modal.getInstance(document.getElementById('editOrderModal')).hide();
    loadOrders();
});
function openCheckModal(id) {
    document.getElementById('checkOrderId').value = id;
    new bootstrap.Modal(document.getElementById('checkModal')).show();
}
document.getElementById('confirmCheck')?.addEventListener('click', async () => {
    const id = document.getElementById('checkOrderId').value;
    const checker = document.getElementById('checkerName').value || 'Сотрудник';
    await fetch(`/api/orders/${id}/mark-checked`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({checked_by: checker})});
    bootstrap.Modal.getInstance(document.getElementById('checkModal')).hide();
    loadOrders();
});
async function loadBalance() {
    const res = await fetch('/api/finance/balance');
    const data = await res.json();
    document.getElementById('balanceSpan').innerText = data.balance;
}
// Инициализация
loadOrders();
loadBalance();
setInterval(() => { loadOrders(); }, 5000);