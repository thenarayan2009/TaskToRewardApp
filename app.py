import os
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Task, Submission, Withdrawal, Transaction, Setting
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads')

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helpers ---
def get_setting(key, default):
    setting = Setting.query.filter_by(key=key).first()
    return setting.value if setting else default

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(
            name=name, email=email, mobile=mobile,
            password=generate_password_hash(password, method='pbkdf2:sha256')
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            if user.is_blocked:
                flash('Your account is blocked. Please contact admin.', 'danger')
                return redirect(url_for('login'))
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/tasks')
@login_required
def tasks():
    all_tasks = Task.query.filter_by(is_active=True).all()
    return render_template('tasks.html', tasks=all_tasks)

@app.route('/task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        if 'screenshot' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['screenshot']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        if file:
            filename = secure_filename(f"{current_user.id}_{task_id}_{datetime.now().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            new_submission = Submission(
                user_id=current_user.id,
                task_id=task_id,
                screenshot=filename
            )
            db.session.add(new_submission)
            db.session.commit()
            flash('Task submitted successfully! Waiting for admin approval.', 'success')
            return redirect(url_for('task_history'))
            
    return render_template('task_detail.html', task=task)

@app.route('/task-history')
@login_required
def task_history():
    submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.submitted_at.desc()).all()
    return render_template('task_history.html', submissions=submissions)

@app.route('/wallet')
@login_required
def wallet():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).all()
    return render_template('wallet.html', user=current_user, transactions=transactions)

@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    min_withdrawal = float(get_setting('min_withdrawal', 300))
    pending_withdrawal = Withdrawal.query.filter_by(user_id=current_user.id, status='Pending').first()
    
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        upi_id = request.form.get('upi_id')
        
        if pending_withdrawal:
            flash('You already have a pending withdrawal request.', 'danger')
        elif amount < min_withdrawal:
            flash(f'Minimum withdrawal amount is ₹{min_withdrawal}.', 'danger')
        elif amount > current_user.wallet_balance:
            flash('Insufficient wallet balance.', 'danger')
        else:
            new_withdrawal = Withdrawal(user_id=current_user.id, amount=amount, upi_id=upi_id)
            # Deduct from wallet immediately to prevent double withdrawal
            current_user.wallet_balance -= amount
            db.session.add(new_withdrawal)
            
            # Record transaction
            transaction = Transaction(
                user_id=current_user.id, amount=amount, type='Debit',
                description=f'Withdrawal request for ₹{amount}'
            )
            db.session.add(transaction)
            db.session.commit()
            flash('Withdrawal request submitted successfully!', 'success')
            return redirect(url_for('withdrawal_history'))
            
    return render_template('withdraw.html', user=current_user, min_withdrawal=min_withdrawal)

@app.route('/withdrawal-history')
@login_required
def withdrawal_history():
    withdrawals = Withdrawal.query.filter_by(user_id=current_user.id).order_by(Withdrawal.requested_at.desc()).all()
    return render_template('withdrawal_history.html', withdrawals=withdrawals)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# --- Admin Routes ---
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('index'))
    stats = {
        'total_users': User.query.filter_by(is_admin=False).count(),
        'pending_tasks': Submission.query.filter_by(status='Pending').count(),
        'pending_withdrawals': Withdrawal.query.filter_by(status='Pending').count(),
        'total_earnings': db.session.query(db.func.sum(User.total_earnings)).scalar() or 0,
    }
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/tasks', methods=['GET', 'POST'])
@login_required
def admin_tasks():
    if not current_user.is_admin: return redirect(url_for('index'))
    if request.method == 'POST':
        title = request.form.get('title')
        reward = float(request.form.get('reward'))
        instructions = request.form.get('instructions')
        new_task = Task(title=title, reward=reward, instructions=instructions)
        db.session.add(new_task)
        db.session.commit()
        flash('Task added successfully!', 'success')
    tasks = Task.query.all()
    return render_template('admin/tasks.html', tasks=tasks)

@app.route('/admin/submissions')
@login_required
def admin_submissions():
    if not current_user.is_admin: return redirect(url_for('index'))
    submissions = Submission.query.filter_by(status='Pending').all()
    return render_template('admin/submissions.html', submissions=submissions)

@app.route('/admin/approve-task/<int:sub_id>')
@login_required
def approve_task(sub_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    sub = Submission.query.get_or_404(sub_id)
    if sub.status == 'Pending':
        sub.status = 'Approved'
        user = User.query.get(sub.user_id)
        user.wallet_balance += sub.task_rel.reward
        user.total_earnings += sub.task_rel.reward
        
        transaction = Transaction(
            user_id=user.id, amount=sub.task_rel.reward, type='Credit',
            description=f'Reward for task: {sub.task_rel.title}'
        )
        db.session.add(transaction)
        db.session.commit()
        flash('Task approved and reward credited!', 'success')
    return redirect(url_for('admin_submissions'))

@app.route('/admin/reject-task/<int:sub_id>', methods=['POST'])
@login_required
def reject_task(sub_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    sub = Submission.query.get_or_404(sub_id)
    reason = request.form.get('reason')
    if sub.status == 'Pending':
        sub.status = 'Rejected'
        sub.rejection_reason = reason
        db.session.commit()
        flash('Task rejected.', 'info')
    return redirect(url_for('admin_submissions'))

@app.route('/admin/withdrawals')
@login_required
def admin_withdrawals():
    if not current_user.is_admin: return redirect(url_for('index'))
    withdrawals = Withdrawal.query.filter_by(status='Pending').all()
    return render_template('admin/withdrawals.html', withdrawals=withdrawals)

@app.route('/admin/pay-withdrawal/<int:w_id>', methods=['POST'])
@login_required
def pay_withdrawal(w_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    withdrawal = Withdrawal.query.get_or_404(w_id)
    if withdrawal.status == 'Pending':
        if 'proof' in request.files:
            file = request.files['proof']
            if file.filename != '':
                filename = secure_filename(f"payment_{w_id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                withdrawal.payment_proof = filename
        
        withdrawal.status = 'Paid'
        withdrawal.processed_at = datetime.utcnow()
        user = User.query.get(withdrawal.user_id)
        user.total_withdrawn += withdrawal.amount
        db.session.commit()
        flash('Withdrawal marked as Paid!', 'success')
    return redirect(url_for('admin_withdrawals'))

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin: return redirect(url_for('index'))
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/toggle-user/<int:user_id>')
@login_required
def toggle_user(user_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    user.is_blocked = not user.is_blocked
    db.session.commit()
    flash(f'User {"blocked" if user.is_blocked else "unblocked"} successfully.', 'info')
    return redirect(url_for('admin_users'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if not current_user.is_admin: return redirect(url_for('index'))
    if request.method == 'POST':
        min_withdrawal = request.form.get('min_withdrawal')
        setting = Setting.query.filter_by(key='min_withdrawal').first()
        if setting:
            setting.value = min_withdrawal
        else:
            setting = Setting(key='min_withdrawal', value=min_withdrawal)
            db.session.add(setting)
        db.session.commit()
        flash('Settings updated!', 'success')
    min_withdrawal = get_setting('min_withdrawal', '300')
    return render_template('admin/settings.html', min_withdrawal=min_withdrawal)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        admin = User.query.filter_by(email='admin@tasktoreward.com').first()
        if not admin:
            admin = User(
                name='Admin', email='admin@tasktoreward.com', mobile='0000000000',
                password=generate_password_hash('admin123', method='pbkdf2:sha256'),
                is_admin=True
            )
            db.session.add(admin)
            # Initial setting
            db.session.add(Setting(key='min_withdrawal', value='300'))
            db.session.commit()
    app.run(debug=True, port=5000)
