from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract, func
from collections import Counter
from datetime import datetime, time, date, timedelta
import os

app = Flask(__name__)
app.secret_key = "secret123"         
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fitness.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# -----------------------------
# Database Models
# -----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), default="member")      # user role: member/admin

class Trainer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    specialty = db.Column(db.String(100))
    contact = db.Column(db.String(50))

class GymClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    trainer = db.Column(db.String(100))
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(50))
    capacity = db.Column(db.Integer)
    
    def is_upcoming(self):
        today = datetime.today().date()
        return self.date >= today

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    membership_type = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20)) 
    expiry_date = db.Column(db.Date, nullable=False)

    def is_active(self):
        today = datetime.today().date()
        return self.expiry_date >= today

    def get_price(self):
        prices = {'Monthly': 300, 'Quarterly': 800, 'Yearly': 3000}
        return prices.get(self.membership_type, 0)

class PaymentReminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    reminder_type = db.Column(db.String(50))  # 'expiry_3_days', 'expiry_today', 'expired'
    sent_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='sent')
    member = db.relationship('Member', backref='reminders')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    method = db.Column(db.String(50))
    member = db.relationship('Member', backref='payments')

class Checkin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'))
    checkin_time = db.Column(db.DateTime, default=datetime.utcnow)
    member = db.relationship('Member', backref='checkins')

# -----------------------------
# SMS Functions
# -----------------------------
def send_sms_reminder(member, reminder_type):
    phone = member.phone
    if not phone:
        return False, "No phone number available"
    
    today = datetime.today().date()
    days_until_expiry = (member.expiry_date - today).days
    
    if reminder_type == 'expiry_3_days':
        message = f"Hi {member.name}, your {member.membership_type} membership at Fitness Club expires in {days_until_expiry} days on {member.expiry_date}. Please renew to avoid interruption. Reply STOP to unsubscribe."
    elif reminder_type == 'expiry_today':
        message = f"Hi {member.name}, your {member.membership_type} membership expires TODAY. Please visit us to renew. Reply STOP to unsubscribe."
    elif reminder_type == 'expired':
        message = f"Hi {member.name}, your {member.membership_type} membership expired on {member.expiry_date}. Renew now to restore access. Reply STOP to unsubscribe."
    else:
        message = f"Hi {member.name}, friendly reminder from Fitness Club about your membership. Reply STOP to unsubscribe."
    
    print(f"📱 SMS TO {phone}: {message}")
    
    reminder = PaymentReminder(
        member_id=member.id,
        reminder_type=reminder_type,
        status='simulated'
    )
    db.session.add(reminder)
    db.session.commit()
    
    return True, f"SMS reminder sent to {member.name}"

# -----------------------------
# Routes
# -----------------------------
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Simple login for dev
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        user = User.query.filter_by(
            username=request.form['username'],
            password=request.form['password']
        ).first()
        if user:
            session['user'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            # Store login error in session instead of flash
            flash("Invalid username/password", "error")
            return redirect(url_for('login'))
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)
    return redirect(url_for('login'))

# Dashboard (counts only active check-ins/members where appropriate)
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    # FIX: Get SA time (UTC+2) FIRST - before using it
    utc_now = datetime.utcnow()
    sa_offset = timedelta(hours=2)
    sa_now = utc_now + sa_offset
    sa_today = sa_now.date()
    today_sa_str = sa_today.strftime('%Y-%m-%d')

    # Now calculate all your stats using SA time
    total_members = Member.query.count()
    active_memberships = sum(1 for m in Member.query.all() if m.is_active())
    trainers_count = Trainer.query.count()
    
    # Count classes happening TODAY in SA time
    classes_today = GymClass.query.filter(GymClass.date == sa_today).count()
    
    # Count UPCOMING classes with SA timezone
    all_classes_list = GymClass.query.all()
    upcoming_classes = 0
    for class_obj in all_classes_list:
        if class_obj.time:
            # Combine class date with its time
            class_time = datetime.strptime(class_obj.time, '%H:%M').time()
            class_datetime = datetime.combine(class_obj.date, class_time)
            
            # Compare with current SA time
            if class_datetime > sa_now:
                upcoming_classes += 1
        else:
            # If no time, just compare dates
            if class_obj.date > sa_today:
                upcoming_classes += 1

    # Get all class names and find the most common one
    all_classes = GymClass.query.with_entities(GymClass.name).all()
    if all_classes:
        class_names = [c[0] for c in all_classes]
        class_counts = Counter(class_names)
        popular_class = class_counts.most_common(1)[0][0]
    else:
        popular_class = "No classes"
        
    # Calculate Busiest Trainer  
    all_trainers = GymClass.query.with_entities(GymClass.trainer).all()
    if all_trainers:
        trainer_names = [t[0] for t in all_trainers if t[0]]  # Filter out empty names
        if trainer_names:
            trainer_counts = Counter(trainer_names)
            busy_trainer = trainer_counts.most_common(1)[0][0]
        else:
            busy_trainer = "No trainers"
    else:
        busy_trainer = "No trainers"

    
    # Get ALL payments
    all_payments = Payment.query.all()
    total_payments = sum(p.amount for p in all_payments) if all_payments else 0.0

    recent_members = Member.query.order_by(Member.id.desc()).limit(5).all()
    
    # Count today's check-ins using SA timezone
    all_checkins = Checkin.query.all()
    today_checkins_count = 0
    
    for checkin in all_checkins:
        # Convert checkin time to SA time (UTC+2)
        checkin_sa_time = checkin.checkin_time + timedelta(hours=2)
        if checkin_sa_time.date() == sa_today:
            today_checkins_count += 1
    
    # Memberships expiring in next 7 days
    expiring_soon = Member.query.filter(
        Member.expiry_date <= sa_today + timedelta(days=7),
        Member.expiry_date >= sa_today
    ).count()
    
    # Member Satisfaction - based on today's engagement
    if active_memberships > 0:
        engagement_rate = today_checkins_count / active_memberships
        member_satisfaction = min(round((engagement_rate * 8) + 1, 1), 5.0)
    else:
        member_satisfaction = 0.0
    member_satisfaction = max(1.0, min(5.0, member_satisfaction))
    
    payments_due = expiring_soon  # Simple assumption for now

    # SMS Reminders Data - using SA time
    members_with_phones = Member.query.filter(
        Member.phone.isnot(None),
        Member.phone != ''
    ).count()

    members_needing_reminders = Member.query.filter(
        Member.phone.isnot(None),
        Member.phone != '',
        Member.expiry_date <= sa_today + timedelta(days=3)
    ).count()

    # Recent reminders sent (last 7 days using SA time)
    recent_reminders = PaymentReminder.query.filter(
        PaymentReminder.sent_date >= datetime.utcnow() - timedelta(days=7)
    ).count()

    # ACTUAL PAYMENTS - Last 6 months
    payment_data = []
    payment_labels = []
    
    # Create last 6 months array
    months_data = []
    for i in range(5, -1, -1):
        month_date = sa_today - timedelta(days=30*i)
        month_key = month_date.strftime('%Y-%m')
        month_name = month_date.strftime('%b')
        months_data.append({
            'key': month_key,
            'name': month_name,
            'total': 0.0
        })
    
    # Get all payments and group by month
    for payment in all_payments:
        payment_month = payment.date.strftime('%Y-%m')
        for month_data in months_data:
            if month_data['key'] == payment_month:
                month_data['total'] += payment.amount
                break
    
    # Prepare data for template
    for month_data in months_data:
        payment_data.append(month_data['total'])
        payment_labels.append(month_data['name'])

    return render_template(
        "dashboard.html",
        total_members=total_members,
        active_memberships=active_memberships,
        trainers_count=trainers_count,
        upcoming_classes=upcoming_classes,
        popular_class=popular_class,
        busy_trainer=busy_trainer,
        total_payments=total_payments,
        recent_members=recent_members,
        today_checkins_count=today_checkins_count,
        revenue_data=payment_data,
        revenue_labels=payment_labels,
        expiring_soon=expiring_soon,
        classes_today=classes_today,
        member_satisfaction=member_satisfaction,
        payments_due=payments_due,
        members_with_phones=members_with_phones,
        members_needing_reminders=members_needing_reminders,
        recent_reminders=recent_reminders
    )
   
    
@app.route('/api/search_members')
def api_search_members():
    if 'user' not in session:
        return jsonify([])
    
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    
    # Simple search 
    members = Member.query.filter(
        Member.name.ilike(f'%{query}%')
    ).limit(10).all()
    
    result = []
    for member in members:
        result.append({
            'id': member.id,
            'name': member.name,
            'membership_type': member.membership_type,
            'expiry_date': member.expiry_date.strftime('%Y-%m-%d')
        })
    
    return jsonify(result)

@app.route('/api/members_needing_reminders')
def api_members_needing_reminders():
    """Get members needing SMS reminders using SA time"""
    if 'user' not in session:
        return jsonify([])
    
    # Use South Africa time
    sa_time = datetime.utcnow() + timedelta(hours=2)
    today_sa = sa_time.date()
    
    # Members with phones expiring in next 3 days or expired
    members = Member.query.filter(
        Member.phone.isnot(None),
        Member.phone != '',
        Member.expiry_date <= today_sa + timedelta(days=3)
    ).all()
    
    result = []
    for member in members:
        days_until_expiry = (member.expiry_date - today_sa).days
        result.append({
            'id': member.id,
            'name': member.name,
            'membership_type': member.membership_type,
            'phone': member.phone,
            'expiry_date': member.expiry_date.strftime('%Y-%m-%d'),
            'days_until_expiry': days_until_expiry
        })
    
    return jsonify(result)

@app.route('/api/members_with_phones')
def api_members_with_phones():
    """Get members with phone numbers for testing"""
    if 'user' not in session:
        return jsonify([])
    
    members = Member.query.filter(
        Member.phone.isnot(None),
        Member.phone != ''
    ).limit(5).all()
    
    result = []
    for member in members:
        result.append({
            'id': member.id,
            'name': member.name,
            'phone': member.phone
        })
    
    return jsonify(result)

@app.route('/send_reminder/<int:member_id>')
def send_reminder(member_id):
    """Send reminder to specific member using SA time"""
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    member = Member.query.get_or_404(member_id)
    
    if not member.phone:
        return jsonify({'success': False, 'message': 'Member has no phone number'})
    
    # Use South Africa time (UTC+2) for date calculations
    sa_time = datetime.utcnow() + timedelta(hours=2)
    today_sa = sa_time.date()
    
    # Determine reminder type based on expiry date using SA time
    days_until_expiry = (member.expiry_date - today_sa).days
    
    if days_until_expiry == 0:
        reminder_type = 'expiry_today'
    elif 1 <= days_until_expiry <= 3:
        reminder_type = 'expiry_3_days'
    elif days_until_expiry < 0:
        reminder_type = 'expired'
    else:
        reminder_type = 'general'
    
    success, message = send_sms_reminder(member, reminder_type)
    
    return jsonify({
        'success': success,
        'message': message,
        'member_name': member.name,
        'days_until_expiry': days_until_expiry
    })
   
@app.route('/create_sample_payments')
def create_sample_payments():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Delete existing payments
    Payment.query.delete()
    
    # Get some members
    members = Member.query.limit(3).all()
    if not members:
        return "No members found to create sample payments for"
    
    # Create sample payments for the last 6 months
    today = datetime.today().date()
    sample_payments = []
    
    for i in range(6):
        payment_date = today - timedelta(days=30*(5-i))
        amount = 300 + (i * 50)  # Increasing amounts
        member = members[i % len(members)]
        
        payment = Payment(
            member_id=member.id,
            amount=amount,
            date=payment_date,
            method='Card'
        )
        sample_payments.append(payment)
        print(f"Created sample payment: R{amount} for {member.name} on {payment_date}")
    
    db.session.add_all(sample_payments)
    db.session.commit()
    
    return f"Created {len(sample_payments)} sample payments for testing"

# -----------------------------
# Members CRUD
# -----------------------------
@app.route('/members')
def members():
    if 'user' not in session:
        return redirect(url_for('login'))
    all_members = Member.query.order_by(Member.name).all()
    return render_template("members.html", members=all_members)

# Provide both a form route and POST handler at the same endpoint for ease
@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get("name", "").strip()
        membership_type = request.form.get("membership_type", "").strip()
        phone = request.form.get("phone", "").strip()  # Get phone number

        # Basic validation
        if not name or not membership_type:
            flash("Name and membership type are required.", "error")
            return redirect(url_for('add_member'))

        # Validate phone format if provided
        if phone and (len(phone) != 10 or not phone.startswith('0')):
            flash("Phone number must be 10 digits starting with 0 (e.g., 0123456789)", "error")
            return redirect(url_for('add_member'))

        today = datetime.today().date()
        # Choose expiry based on membership_type
        mt_lower = membership_type.lower()
        try:
            if mt_lower == "monthly":
                expiry = today + timedelta(days=30)
            elif mt_lower == "quarterly":
                expiry = today + timedelta(days=90)
            elif mt_lower == "yearly":
                expiry = today + timedelta(days=365)
            elif mt_lower == "custom":
                expiry_raw = request.form.get("expiry")
                if not expiry_raw:
                    flash("Expiry date required for Custom membership.", "error")
                    return redirect(url_for('add_member'))
                expiry = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
            else:
                expiry_raw = request.form.get("expiry")
                if expiry_raw:
                    expiry = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
                else:
                    expiry = today + timedelta(days=30)
        except ValueError:
            flash("Invalid expiry date format.", "error")
            return redirect(url_for('add_member'))

        # Create member with phone number
        new_member = Member(
            name=name, 
            membership_type=membership_type, 
            expiry_date=expiry,
            phone=phone if phone else None  # Store phone if provided
        )
        db.session.add(new_member)
        db.session.commit()
        
        if phone:
            flash(f'Member {name} added successfully with phone number!', 'success')
        else:
            flash(f'Member {name} added successfully!', 'success')
            
        return redirect(url_for('members'))

    # GET -> show form
    today_str = datetime.today().strftime('%Y-%m-%d')
    return render_template("add_member.html", today=today_str)

@app.route('/members/edit/<int:id>', methods=['GET', 'POST'])
def edit_member(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    member = Member.query.get_or_404(id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        membership_type = request.form.get("membership_type", "").strip()
        
        if not name or not membership_type:
            flash("Name and membership type required.", "error")
            return redirect(url_for('edit_member', id=id))

        # Get the expiry date from the form
        expiry_raw = request.form.get("expiry")
        
        if expiry_raw:
            # Use the date from the form
            try:
                expiry = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid expiry date format.", "error")
                return redirect(url_for('edit_member', id=id))
        else:
            # If no date provided, calculate based on membership type
            today = datetime.today().date()
            mt_lower = membership_type.lower()
            if mt_lower == "monthly":
                expiry = today + timedelta(days=30)
            elif mt_lower == "quarterly":
                expiry = today + timedelta(days=90)
            elif mt_lower == "yearly":
                expiry = today + timedelta(days=365)
            else:
                # For custom or unknown types, keep the current expiry
                expiry = member.expiry_date

        member.name = name
        member.membership_type = membership_type
        member.expiry_date = expiry
        db.session.commit()
        
        flash(f'Member {member.name} updated successfully!', 'success')
        return redirect(url_for('members'))

    # GET - show current data
    return render_template("edit_member.html", member=member)

@app.route('/members/delete/<int:id>')
def delete_member(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    member = Member.query.get_or_404(id)
    db.session.delete(member)
    db.session.commit()
    flash(f'Member {member.name} deleted.', 'success')
    return redirect(url_for('members'))

# --------------------------------------------------
# Classes / Trainers / Payments / Checkins
# --------------------------------------------------

@app.route('/classes')
def classes():
    if 'user' not in session:
        return redirect(url_for('login'))
    all_classes = GymClass.query.all()
    return render_template("classes.html", classes=all_classes)

@app.route('/add_class_form')
def add_class_form():
    if 'user' not in session:
        return redirect(url_for('login'))
    trainers = Trainer.query.all()
    return render_template("add_class.html", trainers=trainers)

@app.route('/add_class', methods=['POST'])
def add_class():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        # Convert date string to date object
        date_str = request.form.get('date','')
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        new_class = GymClass(
            name=request.form['name'],
            trainer=request.form.get('trainer',''),
            date=date_obj,  # ← FIXED: Now it's a date object
            time=request.form.get('time',''),
            capacity=request.form.get('capacity', None)
        )
        db.session.add(new_class)
        db.session.commit()
        flash("Class added successfully!", "success")
    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "error")
    except Exception as e:
        flash(f"Error adding class: {e}", "error")
    
    return redirect(url_for('classes'))

@app.route('/edit_class/<int:class_id>', methods=['GET', 'POST'])
def edit_class(class_id):
    gym_class = GymClass.query.get_or_404(class_id)
    trainers = Trainer.query.all()
    
    if request.method == 'POST':
        try:
            # Convert date string to date object
            date_str = request.form.get('date','')
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            gym_class.name = request.form['name']
            gym_class.trainer = request.form.get('trainer','')
            gym_class.date = date_obj  # ← FIXED: Now it's a date object
            gym_class.time = request.form.get('time','')
            gym_class.capacity = request.form.get('capacity', None)
            
            db.session.commit()
            flash("Class updated successfully!", "success")
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "error")
        except Exception as e:
            flash(f"Error updating class: {e}", "error")
        
        return redirect(url_for('classes'))
    
    return render_template('edit_class.html', gym_class=gym_class, trainers=trainers)

@app.route('/delete_class/<int:id>')
def delete_class(id):
    gym_class = GymClass.query.get(id)
    if gym_class:
        db.session.delete(gym_class)
        db.session.commit()
    flash("Class deleted.", "success")
    return redirect(url_for('classes'))

# Trainers
@app.route('/trainers', methods=['GET', 'POST'])
def trainers():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == "POST":
        new_trainer = Trainer(
            name=request.form.get("name",""),
            specialty=request.form.get("specialty",""),
            contact=request.form.get("contact","")
        )
        db.session.add(new_trainer)
        db.session.commit()
        return redirect(url_for('trainers'))
    all_trainers = Trainer.query.all()
    return render_template("trainers.html", trainers=all_trainers)

@app.route('/trainers/edit/<int:id>', methods=['GET', 'POST'])
def edit_trainer(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    trainer = Trainer.query.get_or_404(id)
    
    if request.method == 'POST':
        trainer.name = request.form['name']
        trainer.specialty = request.form['specialty']
        trainer.contact = request.form['contact']
        
        db.session.commit()
        flash(f'Trainer {trainer.name} updated successfully!', 'success')
        return redirect(url_for('trainers'))
    
    return render_template("edit_trainer.html", trainer=trainer)

@app.route('/trainers/delete/<int:id>')
def delete_trainer(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    trainer = Trainer.query.get_or_404(id)
    db.session.delete(trainer)
    db.session.commit()
    flash(f'Trainer {trainer.name} deleted successfully!', 'success')
    return redirect(url_for('trainers'))

# Payments
@app.route('/payments')
def payments():
    if 'user' not in session:
        return redirect(url_for('login'))
    all_payments = Payment.query.all()
    members = Member.query.all()
    return render_template("payments.html", payments=all_payments, members=members)

@app.route('/add_payment', methods=['POST'])
def add_payment():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        # Convert the date string to a Python date object
        date_str = request.form['date']
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        new_payment = Payment(
            member_id=int(request.form['member_id']),
            amount=float(request.form['amount']),
            date=date_obj,  # ← FIXED: Now it's a date object
            method=request.form.get('method','')
        )
        db.session.add(new_payment)
        db.session.commit()
        flash("Payment recorded successfully!", "success")
    except ValueError as e:
        flash(f"Invalid date format: {e}", "error")
    except Exception as e:
        flash(f"Error recording payment: {e}", "error")
    
    return redirect(url_for('payments'))

@app.route('/add_payment_form')
def add_payment_form():
    if 'user' not in session:
        return redirect(url_for('login'))
    members = Member.query.all()
    return render_template("add_payment.html", members=members)

@app.route('/edit_payment/<int:id>', methods=['GET', 'POST'])
def edit_payment(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    payment = Payment.query.get_or_404(id)
    members = Member.query.all()
    
    if request.method == 'POST':
        try:
            # Convert the date string to a Python date object
            date_str = request.form['date']
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            payment.member_id = int(request.form['member_id'])
            payment.amount = float(request.form['amount'])
            payment.date = date_obj  # ← FIXED: Now it's a date object
            payment.method = request.form.get('method', '')
            
            db.session.commit()
            flash("Payment updated successfully!", "success")
        except ValueError as e:
            flash(f"Invalid date format: {e}", "error")
        except Exception as e:
            flash(f"Error updating payment: {e}", "error")
        
        return redirect(url_for('payments'))
    
    return render_template("edit_payment.html", payment=payment, members=members)

@app.route('/delete_payment/<int:id>')
def delete_payment(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    payment = Payment.query.get_or_404(id)
    db.session.delete(payment)
    db.session.commit()
    flash("Payment deleted successfully!", "success")
    return redirect(url_for('payments'))

# Checkins
@app.route('/checkin/<int:member_id>')
def checkin_member(member_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    member = Member.query.get(member_id)
    if not member:
        flash('Member not found!', 'error')
        return redirect(url_for('members'))
    if not member.is_active():
        flash(f'{member.name} cannot check in - membership expired on {member.expiry_date}!', 'error')
        return redirect(url_for('members'))
    
    today_str = datetime.today().strftime('%Y-%m-%d')
    already = Checkin.query.filter(db.func.date(Checkin.checkin_time) == today_str,
                                   Checkin.member_id == member_id).first()
    if already:
        # Add 2 hours for South Africa time (UTC+2)
        sa_time = already.checkin_time + timedelta(hours=2)
        flash(f'{member.name} already checked in today at {sa_time.strftime("%H:%M")}', 'warning')
        return redirect(url_for('members'))
    
    new_checkin = Checkin(member_id=member_id)
    db.session.add(new_checkin)
    db.session.commit()
    
    # Add 2 hours for South Africa time (UTC+2)
    sa_time = new_checkin.checkin_time + timedelta(hours=2)
    flash(f'{member.name} checked in at {sa_time.strftime("%H:%M:%S")}', 'success')
    return redirect(url_for('members'))

@app.route('/checkins')
def checkins():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Simple approach: get all check-ins and filter by SA time
    all_checkins = Checkin.query.order_by(Checkin.checkin_time.desc()).all()
    
    # Filter for today's check-ins in SA time (+2 hours)
    sa_time_now = datetime.utcnow() + timedelta(hours=2)
    today_sa = sa_time_now.date()
    
    today_checkins = []
    for checkin in all_checkins:
        # Convert checkin time to SA time
        checkin_sa_time = checkin.checkin_time + timedelta(hours=2)
        if checkin_sa_time.date() == today_sa:
            today_checkins.append(checkin)
    
    valid_today_checkins = [c for c in today_checkins if c.member and c.member.is_active()]
    
    # Count check-ins for week and month in SA time
    week_ago_sa = sa_time_now - timedelta(days=7)
    month_ago_sa = sa_time_now - timedelta(days=30)
    
    week_checkins = len([c for c in all_checkins if (c.checkin_time + timedelta(hours=2)) >= week_ago_sa])
    month_checkins = len([c for c in all_checkins if (c.checkin_time + timedelta(hours=2)) >= month_ago_sa])
    
    return render_template("checkins.html", 
                         today_checkins=valid_today_checkins, 
                         week_checkins=week_checkins, 
                         month_checkins=month_checkins, 
                         today=today_sa.strftime('%Y-%m-%d'))

@app.route('/cleanup_checkins')
def cleanup_checkins():
    if 'user' not in session:
        return redirect(url_for('login'))
    all_checkins = Checkin.query.all()
    orphaned_count = 0
    for c in all_checkins:
        if c.member is None:
            db.session.delete(c); orphaned_count += 1
    db.session.commit()
    return f"Cleaned up {orphaned_count} orphaned check-ins"

@app.route('/whoami')
def whoami():
    return f"Logged in as: {session.get('user')}"

# -----------------------------
# Initialize DB & Default Admin
# -----------------------------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", password="admin123", role="admin")
        db.session.add(admin)
        db.session.commit()
        print("✅ Default admin created! Username: admin | Password: admin123")

# -----------------------------
# Run App
# -----------------------------
port = int(os.environ.get("PORT", 5000))
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=port, debug=False)



