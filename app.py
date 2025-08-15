from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_babel import Babel, _
from models import db, User, Crop, Cart, Order, Notification  # Notification imported
import os
import re
from werkzeug.utils import secure_filename
from flask_login import current_user


from weather_api import get_weather_by_pincode,get_city_from_address

app = Flask(__name__)
app.secret_key = 'krishilink_secret_key_123'

# i18n Configuration
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_SUPPORTED_LOCALES'] = ['en', 'hi', 'mr']
babel = Babel(app)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'profile_pics')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///krishilink.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

CORS(app)

with app.app_context():
    """db.drop_all()
    print("deleted")"""
    db.create_all()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        user = User.query.filter_by(email=email).first()

        if user:
            if user.password == password:  # plain text match
                session['user_id'] = user.id
                session['user_role'] = user.role

                if not user.phone or not user.location or not user.is_profile_complete:
                    return redirect(url_for('complete_profile'))

                return redirect(url_for('farmer_dashboard' if user.role == 'farmer' else 'buyer_dashboard'))
            else:
                # Wrong password
                return render_template('login.html', user=None, error="Incorrect password.")
        else:
            # No such email
            return render_template('login.html', user=None, error="No account found with that email.")

    return render_template('login.html', user=None)

@app.route('/forgot_password', methods=['GET'])
def forgot_password_form():
    return render_template('forgot_password.html')

from sqlalchemy import func

@app.route('/forgot_password', methods=['POST'])
def forgot_password_submit():
    data = request.get_json()
    print("📩 Raw data from request:", data)

    email = data.get('email', '').strip().lower()
    print("🔍 Normalized email:", email)

    user = User.query.filter(func.lower(User.email) == email).first()
    print("👤 Found user:", user)

    if not user:
        return jsonify({"success": False, "message": "No account found with that email."}), 400

    # Store password directly (matches your current login check)
    user.password = data.get('new_password', '').strip()
    db.session.commit()

    print("✅ Password updated successfully for:", email)
    return jsonify({"success": True, "message": "Password updated successfully."}), 200

@app.route('/register', methods=['GET', 'POST'])
def register():
    alert_script = ""  # initialize empty JS alert

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            alert_script = "<script>alert('Email already registered. Please use a different email.');</script>"
            return render_template('register.html', alert_script=alert_script)

        # Password validation
        pattern = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$'
        if not re.match(pattern, password):
            alert_script = "<script>alert('Password must be at least 8 characters long, include a letter, number, and special character.');</script>"
            return render_template('register.html', alert_script=alert_script)

        # If valid, create user
        new_user = User(name=name, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        # Success notification
        add_notification(new_user.id, "Your account has been created successfully.")
        alert_script = "<script>alert('Account created successfully! Please log in.');</script>"

        return redirect(url_for('login'))  # alert won't show on login page; notifications will

    return render_template('register.html', alert_script=alert_script)


@app.route('/complete_profile', methods=['GET', 'POST'])
def complete_profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    alert_script = ""  # will hold JavaScript alert

    if request.method == 'POST':
        phone = request.form.get('phone')
        if not re.fullmatch(r'\d{10}', phone):
            alert_script = f"<script>alert('Invalid phone number. Please enter a 10-digit number.');</script>"
            return render_template('complete_profile.html', user=user, alert_script=alert_script)

        user.phone = phone
        user.location = request.form['location']
        user.pincode = request.form.get('pincode')
        user.city = get_city_from_address(user.location)

        file = request.files.get('profile_image')
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{user.id}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            user.profile_image = f'uploads/profile_pics/{filename}'
            db.session.commit()

        if user.role == 'farmer':
            bank_account = request.form.get('bank_account')
            if bank_account and not re.fullmatch(r'\d{9,18}', bank_account):
                alert_script = "<script>alert('Invalid bank account number. It should be 9 to 18 digits.');</script>"
                return render_template('complete_profile.html', user=user, alert_script=alert_script)

            user.bank_account = bank_account
            user.bio = request.form.get('bio')
            user.land_size = request.form.get('land_size')
            user.farm_type = request.form.get('farm_type')

        if user.role == 'buyer':
            user.company_name = request.form.get('company_name')
            user.business_type = request.form.get('business_type')
            selected_crops = request.form.getlist('preferred_crops')
            user.preferred_crops = ",".join(selected_crops)
            other_crops_input = request.form.get('other_crops', '').strip()
            user.other_crops = other_crops_input

        user.is_profile_complete = True
        db.session.commit()

        # Success notification (optional alert)
        alert_script = "<script>alert('Profile completed successfully!');</script>"
        add_notification(user.id, "Your profile has been completed successfully.")
        return redirect(url_for('farmer_dashboard') if user.role == 'farmer' else url_for('buyer_dashboard'))

    return render_template('complete_profile.html', user=user, alert_script=alert_script)

@app.route('/farmer/dashboard')
def farmer_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if user is None or user.role != 'farmer':
        return redirect(url_for('login'))

    crops = Crop.query.filter_by(user_id=user_id).all()

    # Fetch COD pending orders for this farmer
    cod_orders = (
        Order.query.join(Crop)
        .filter(Crop.user_id == user_id, Order.status == 'cod_pending')
        .order_by(Order.order_date.desc())
        .all()
    )

    rain_expected = False
    weather_alert_msg = None
    weather_info = None

    if user.location:
        try:
            weather_alert_msg, weather_info = get_weather_by_pincode(user.pincode)
            if weather_info and "Rain predicted" in weather_alert_msg:
                rain_expected = True
        except Exception as e:
            print("Weather error:", e)
            weather_alert_msg = "⚠ Weather data could not be fetched in dashboard"
    else:
        weather_alert_msg = "⚠ No location found for your account."

    from datetime import datetime
    today = datetime.now()
    crop_alerts = []

    for crop in crops:
        harvest_date = datetime.strptime(crop.harvest_date, '%Y-%m-%d')
        days_left = (harvest_date - today).days

        if 0 <= days_left <= 7:
            if days_left == 0:
                crop_alerts.append(f"Harvest for {crop.crop_name} is due today!")
                add_notification(user.id, f"Harvest for {crop.crop_name} is due today!")
            else:
                crop_alerts.append(f"Harvest for {crop.crop_name} is due in {days_left} days.")
                add_notification(user.id, f"Harvest for {crop.crop_name} is due in {days_left} days.")
        if crop.quantity == 0:
            crop_alerts.append(f"{crop.crop_name} is out of stock.")
            add_notification(user.id, f"{crop.crop_name} is out of stock.")
        if rain_expected:
            crop_alerts.append(f"Rain expected soon. Take precautions for {crop.crop_name}.")
            add_notification(user.id, f"Rain expected soon. Take precautions for {crop.crop_name}.")

    profile_incomplete = not all([user.phone, user.location, user.bank_account, user.land_size, user.farm_type])

    future_alerts = [
        "📅 Fertilizer tracking will be available soon!",
        "📈 Yield prediction model launching next month!",
        "📲 KrishiLink app for Android is under development!"
    ]

    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    
    from collections import defaultdict

    # Fetch all orders for this farmer's crops
    all_orders = (
        Order.query.join(Crop)
        .filter(Crop.user_id == user_id)
        .all()
    )

    # Group orders by crop id
    orders_by_crop = defaultdict(list)
    for order in all_orders:
        orders_by_crop[order.crop_id].append(order)

    return render_template(
        'farmer_dashboard.html',
        user=user,
        crops=crops,
        cod_orders=cod_orders,
        orders_by_crop=orders_by_crop,  # <-- added here
        profile_incomplete=profile_incomplete,
        weather_alert_msg=weather_alert_msg,
        weather_info=weather_info,
        rain_expected=rain_expected,
        crop_alerts=crop_alerts,
        future_alerts=future_alerts,
        notifications=notifications
    )


from flask import flash

@app.route('/cod_approve/<int:order_id>', methods=['POST'])
def cod_approve(order_id):
    order = Order.query.get(order_id)
    if not order:
        flash("Order not found")
        return redirect(url_for('farmer_dashboard'))
    
    # Mark this order as approved
    order.status = "approved"
    
    # Mark all other pending orders for same crop as rejected
    other_orders = Order.query.filter(
        Order.crop_id == order.crop_id,
        Order.id != order.id,
        Order.status == "cod_pending"
    ).all()
    for o in other_orders:
        o.status = "rejected"
    
    # Update crop status as sold
    crop = Crop.query.get(order.crop_id)
    crop.status = "sold"
    
    db.session.commit()
    flash("Order approved, other orders rejected")
    return redirect(url_for('farmer_dashboard'))


@app.route('/farmer/cod/reject/<int:order_id>', methods=['POST'])
def cod_reject(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)

    # Unauthorized or invalid order
    if order.crop.user_id != user_id or order.status != 'cod_pending':
        alert_script = "<script>alert('Unauthorized or invalid order.');</script>"
        return render_template('farmer_dashboard.html', alert_script=alert_script)

    # Reject the order
    order.status = 'cancelled'
    db.session.commit()

    # Notify buyer about rejection
    add_notification(order.user_id, f"Your COD order #{order.id} has been rejected by the farmer.")

    # Alert for farmer
    alert_script = f"<script>alert('Order #{order.id} rejected successfully.');</script>"
    return render_template('farmer_dashboard.html', alert_script=alert_script)


@app.route("/remove_profile_image", methods=["POST"])
def remove_profile_image():
    user_id = session.get("user_id")
    if user_id is None:
        return "Not logged in", 401

    user = db.session.get(User, user_id)
    if user is None:
        return "User not found", 404

    user.profile_image = "uploads/profile_pics/default_picture.png"
    db.session.commit()
    return "", 204


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/buyer/dashboard', methods=['GET', 'POST'])
def buyer_dashboard():
    from sqlalchemy import or_, func

    # Get user ID from session
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    # Fetch the latest user info from the DB
    user = User.query.get(user_id)
    if not user or user.role != 'buyer':
        return redirect(url_for('login'))

    # Prepare preferred crops list (lowercased and trimmed)
    preferred_crop_list = [
        c.strip().lower() for c in (user.preferred_crops or "").split(',') if c.strip()
    ]

    if user.other_crops:
        preferred_crop_list += [c.strip().lower() for c in user.other_crops.split(',') if c.strip()]

    # Get search query
    search_query = request.args.get('search', '').strip()

    # Base query: available crops in user's current city
    base_query = Crop.query.join(User, Crop.user_id == User.id).filter(
        Crop.status == "available",
        User.city == user.city
    )

    # Apply search filter if present
    if search_query:
        base_query = base_query.filter(
            or_(
                Crop.crop_name.ilike(f"%{search_query}%"),
                Crop.description.ilike(f"%{search_query}%")
            )
        )

    preferred_crops = []
    other_crops = []

    if preferred_crop_list:
        # Query for preferred crops
        preferred_query = base_query
        filters = [
            func.lower(func.trim(Crop.crop_name)).ilike(f"%{crop}%")
            for crop in preferred_crop_list
        ]
        preferred_crops = preferred_query.filter(or_(*filters)).all()
        preferred_ids = [c.id for c in preferred_crops]

        # Other crops are the remaining
        other_crops = base_query.filter(~Crop.id.in_(preferred_ids)).all()
    else:
        other_crops = base_query.all()

    # Fetch notifications for the user
    notifications = Notification.query.filter_by(user_id=user.id).order_by(
        Notification.created_at.desc()
    ).all()

    return render_template(
        'buyer_dashboard.html',
        user=user,
        preferred_crops=preferred_crops,
        other_crops=other_crops,
        search_query=search_query,
        notifications=notifications
    )



@app.route('/add_money', methods=['POST'])
def add_money():
    user_id = session.get('user_id')
    if not user_id:
        alert_script = "<script>alert('You must be logged in to add money.'); window.location='/login';</script>"
        return render_template('login', alert_script=alert_script)

    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        alert_script = "<script>alert('Invalid amount.'); window.history.back();</script>"
        return render_template('buyer_dashboard.html', alert_script=alert_script)

    upi_id = request.form.get('upi_id', '').strip()

    if amount <= 0:
        alert_script = "<script>alert('Invalid amount.'); window.history.back();</script>"
        return render_template('buyer_dashboard.html', alert_script=alert_script)

    if not upi_id or "@" not in upi_id:
        alert_script = "<script>alert('Please enter a valid UPI ID.'); window.history.back();</script>"
        return render_template('buyer_dashboard.html', alert_script=alert_script)

    user = User.query.get(user_id)
    if user:
        user.wallet += amount
        db.session.commit()
        alert_script = f"<script>alert('Payment successful! ₹{amount} added to your wallet.'); window.location='{request.referrer or url_for('home')}';</script>"
    else:
        alert_script = "<script>alert('User not found.'); window.history.back();</script>"

    return render_template('buyer_dashboard.html', alert_script=alert_script)

@app.route('/add_crop', methods=['GET', 'POST'])
def add_crop():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        crop_name = request.form['crop_name']
        quantity = request.form['quantity']
        price = request.form['price']
        harvest_date = request.form['harvest_date']
        description = request.form['description']
        delivery_method = request.form.get('delivery_method')

        # ✅ Get the current user's city from the User table
        farmer = User.query.get(session['user_id'])
        farmer_city = farmer.city if farmer and farmer.city else None

        file = request.files.get('image')
        image_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(f"crop_{session['user_id']}_{file.filename}")
            filepath = os.path.join('static/uploads/crops', filename)
            file.save(filepath)
            image_path = f'uploads/crops/{filename}'

        # ✅ Save crop with farmer's city
        new_crop = Crop(
            user_id=session['user_id'],
            crop_name=crop_name,
            quantity=int(quantity),
            price=int(price),
            harvest_date=harvest_date,
            image=image_path,
            description=description,
            delivery_method=delivery_method,
        )

        db.session.add(new_crop)
        db.session.commit()
        return redirect(url_for('farmer_dashboard'))
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    return render_template('add_crop.html', user=user, notifications=notifications)

@app.route('/edit_crop/<int:crop_id>', methods=['GET', 'POST'])
def edit_crop(crop_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    crop = Crop.query.filter_by(id=crop_id, user_id=user_id).first_or_404()
    sold = (crop.status.lower() == "sold")

    if request.method == 'POST':
        crop.crop_name = request.form['crop_name']
        crop.quantity = int(request.form['quantity'])
        crop.price = int(request.form['price'])
        crop.harvest_date = request.form['harvest_date']
        crop.description = request.form['description']
        crop.delivery_method = request.form.get('delivery_method')

        if not sold:
            crop.status = request.form['status'].lower()

        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(f"crop_{user_id}_{file.filename}")
            filepath = os.path.join('static/uploads/crops', filename)
            file.save(filepath)
            crop.image = f'uploads/crops/{filename}'

        db.session.commit()
        add_notification(user_id, 'Crop updated successfully!')
        return redirect(url_for('farmer_dashboard'))

    user = User.query.get(user_id)
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()

    return render_template('edit_crop.html', crop=crop, sold=sold, user=user, notifications=notifications)

@app.route('/delete_crop/<int:crop_id>')
def delete_crop(crop_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    crop = Crop.query.filter_by(id=crop_id, user_id=session['user_id']).first_or_404()

    if crop.image and os.path.exists(crop.image):
        os.remove(crop.image)

    db.session.delete(crop)
    db.session.commit()
    return redirect(url_for('farmer_dashboard'))


from weather_api import get_weather_by_pincode as get_weather


@app.route('/get_weather', methods=['POST'])
def fetch_weather():
    pincode = request.form.get('pincode')

    if not pincode:
        return {"error": "Pincode is required"}, 400

    alert, weather_info = get_weather(pincode)

    return {
        "alert": alert,
        "weather": weather_info
    }


user_carts = {}


@app.route('/add_to_cart/<int:crop_id>', methods=['POST'])
def add_to_cart(crop_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    crop = Crop.query.get(crop_id)
    if not crop or crop.status != 'available':
        add_notification(user_id, "Crop not available.")
        return redirect(url_for('buyer_dashboard'))

    quantity = crop.quantity  # Always add full available quantity

    cart_item = Cart.query.filter_by(user_id=user_id, crop_id=crop_id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = Cart(user_id=user_id, crop_id=crop_id, quantity=quantity)
        db.session.add(cart_item)

    db.session.commit()
    add_notification(user_id, f"{crop.crop_name} added to cart.")
    return redirect(url_for('buyer_dashboard'))

@app.route('/buy_now/<int:crop_id>', methods=['POST'])
def buy_now(crop_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    crop = Crop.query.get(crop_id)
    if not crop or crop.status != 'available':
        add_notification(user_id, "Crop not available.")
        return redirect(url_for('buyer_dashboard'))

    # Check for existing pending order
    existing_order = Order.query.filter_by(
        user_id=user_id,
        crop_id=crop.id,
        status="pending"
    ).first()

    if existing_order:
        return redirect(url_for('payment_page', order_id=existing_order.id))

    total_price = crop.price * crop.quantity

    # Create new pending order
    order = Order(
        user_id=user_id,
        crop_id=crop.id,
        quantity=crop.quantity,
        total_price=total_price,
        status="pending"
    )
    db.session.add(order)
    db.session.commit()

    return redirect(url_for('payment_page', order_id=order.id))

@app.route('/payment/<int:order_id>')
def payment_page(order_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)

    if order.user_id != user_id:
        return "Unauthorized", 403

    # Only allow payment if order status is pending
    if order.status != "pending":
        return redirect(url_for('orders'))

    user = User.query.get(user_id)
    return render_template('payment.html', order=order, user=user)

import random
from flask import request, jsonify

@app.route('/process_payment', methods=['POST'])
def process_payment():
    data = request.json
    order_id = data.get('order_id')
    user_id = data.get('user_id')
    payment_method = data.get('payment_method')  # new param: 'upi', 'wallet', 'cod'
    upi_id = data.get('upi_id', None)

    order = Order.query.get(order_id)
    if not order or order.user_id != user_id:
        return jsonify({"status": "failed", "message": "Invalid order or user"}), 400

    if order.status != "pending":
        return jsonify({"status": "failed", "message": "Order is not pending payment"}), 400

    buyer = User.query.get(user_id)
    farmer = User.query.get(order.crop.user_id)
    total_price = order.total_price

    if payment_method == 'upi':
        if not upi_id:
            return jsonify({"status": "failed", "message": "UPI ID required"}), 400
        # Simulate UPI payment success (mock)
        # You can add wallet balance check if you want to deduct wallet as well here
        farmer.wallet += total_price
        order.crop.status = "sold"
        order.status = "confirmed"
        db.session.commit()

        # handle sequential payments session logic (same as before)
        pending_orders = session.get('pending_orders', [])
        if order.id in pending_orders:
            pending_orders.remove(order.id)
            session['pending_orders'] = pending_orders

        if pending_orders:
            next_order_id = pending_orders[0]
            return jsonify({
                "status": "success",
                "transaction_id": f"MOCKTXN{random.randint(100000,999999)}",
                "message": "Mock UPI payment successful and order confirmed.",
                "next_order_url": url_for('payment_page', order_id=next_order_id)
            })
        else:
            session.pop('pending_orders', None)
            return jsonify({
                "status": "success",
                "transaction_id": f"MOCKTXN{random.randint(100000,999999)}",
                "message": "All orders confirmed. Thank you for your purchase!"
            })

    elif payment_method == 'wallet':
        if buyer.wallet < total_price:
            return jsonify({"status": "failed", "message": "Insufficient wallet balance"}), 400
        buyer.wallet -= total_price
        farmer.wallet += total_price
        order.crop.status = "sold"
        order.status = "confirmed"
        db.session.commit()

        # same session logic as above
        pending_orders = session.get('pending_orders', [])
        if order.id in pending_orders:
            pending_orders.remove(order.id)
            session['pending_orders'] = pending_orders

        if pending_orders:
            next_order_id = pending_orders[0]
            return jsonify({
                "status": "success",
                "message": "Wallet payment successful and order confirmed.",
                "next_order_url": url_for('payment_page', order_id=next_order_id)
            })
        else:
            session.pop('pending_orders', None)
            return jsonify({
                "status": "success",
                "message": "All orders confirmed via wallet. Thank you!"
            })

    elif payment_method == 'cod':
        order.status = "cod_pending"
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Order placed with Cash on Delivery. Farmer will confirm."
    })

    else:
        return jsonify({"status": "failed", "message": "Invalid payment method"}), 400

@app.route('/users')
def get_users():
    users = User.query.all()
    return jsonify([
        {
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'wallet': u.wallet
        } for u in users
    ])


@app.route('/cart')
def view_cart():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    cart_items = Cart.query.filter_by(user_id=user_id).all()
    total_price = sum(item.crop.price * item.quantity for item in cart_items)
    user = User.query.get(user_id)
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    return render_template('cart.html', cart_items=cart_items, total_price=total_price, user=user, notifications=notifications)


@app.route('/remove_from_cart/<int:cart_id>')
def remove_from_cart(cart_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    item = Cart.query.get_or_404(cart_id)

    # Optional: verify the item belongs to the logged-in user
    if item.user_id != user_id:
        # Optionally handle unauthorized deletion attempt
        return redirect(url_for('view_cart'))

    db.session.delete(item)
    db.session.commit()

    add_notification(user_id, "Item removed from cart.")  # notification instead of flash
    return redirect(url_for('view_cart'))


@app.route('/checkout', methods=['POST'])
def checkout():
    user_id = session.get('user_id')
    if not user_id:
        alert_script = "<script>alert('You must be logged in to checkout.'); window.location='/login';</script>"
        return render_template('cart.html', alert_script=alert_script)

    cart_items = Cart.query.filter_by(user_id=user_id).all()
    if not cart_items:
        alert_script = "<script>alert('Your cart is empty.'); window.location='/view_cart';</script>"
        return render_template('cart.html', alert_script=alert_script)

    order_ids = []

    for item in cart_items:
        crop = Crop.query.get(item.crop_id)
        if not crop or crop.status != 'available':
            continue

        order_total = crop.price * item.quantity

        order = Order(
            user_id=user_id,
            crop_id=crop.id,
            quantity=item.quantity,
            total_price=order_total,
            status="pending"
        )
        db.session.add(order)
        db.session.delete(item)  # Remove from cart
        db.session.flush()  # To get order.id

        order_ids.append(order.id)

    db.session.commit()

    if not order_ids:
        alert_script = "<script>alert('No valid items to order.'); window.location='/view_cart';</script>"
        return render_template('cart.html', alert_script=alert_script)

    # Save remaining order IDs in session to process sequential payments
    session['pending_orders'] = order_ids

    # Optional: notify the user that the order(s) are created (before payment)
    for oid in order_ids:
        add_notification(user_id, f"Order #{oid} created. Please proceed to payment.")

    # Redirect to payment page of first order
    return redirect(url_for('payment_page', order_id=order_ids[0]))

@app.route('/orders')
def orders():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)  # ← define user first
    
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    user_orders = Order.query.filter_by(user_id=user_id).order_by(Order.order_date.desc()).all()
    
    return render_template(
        'orders.html',
        orders=user_orders,
        user=user,
        notifications=notifications
    )



def add_notification(user_id, message):
    notif = Notification(user_id=user_id, message=message)
    db.session.add(notif)
    db.session.commit()

@app.route('/notifications')
def notifications():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()

    # Mark all unread notifications as read automatically
    unread_notifications = [n for n in notifications if not n.is_read]
    if unread_notifications:
        for notif in unread_notifications:
            notif.is_read = True
        db.session.commit()

    # Pass user role to template
    return render_template('notifications.html', notifications=notifications, user_role=user.role)



@app.route('/notifications/mark_read/<int:notif_id>', methods=['POST'])
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    notif.is_read = True
    db.session.commit()
    return ('', 204)

@app.route('/notifications/clear_selected', methods=['POST'])
def clear_selected_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    selected_ids = request.form.get('selected_ids')
    if selected_ids:
        ids_list = [int(i) for i in selected_ids.split(',') if i.isdigit()]
        Notification.query.filter(Notification.user_id == user_id, Notification.id.in_(ids_list)).delete(synchronize_session=False)
        db.session.commit()

    return redirect(url_for('notifications'))

@babel.localeselector
def get_locale():
    lang = request.cookies.get('lang')
    if lang in app.config['BABEL_SUPPORTED_LOCALES']:
        return lang
    return app.config['BABEL_DEFAULT_LOCALE']


from flask import make_response

@app.route('/set_language/<lang_code>')
def set_language(lang_code):
    if lang_code in app.config['BABEL_SUPPORTED_LOCALES']:
        resp = make_response(redirect(request.referrer or url_for('home')))
        # cookie valid for 30 days
        resp.set_cookie('lang', lang_code, max_age=30*24*60*60)
        return resp
    return redirect(request.referrer or url_for('home'))


from sqlalchemy import or_

@app.route('/search_crops', methods=['GET'])
def search_crops():
    user_id = session.get('user_id') 
    if not user_id: 
        return redirect(url_for('login'))
    
    query = request.args.get('query', '').strip()
    if query:
        crops = Crop.query.filter(
            or_(
                Crop.crop_name.ilike(f'%{query}%'),
                Crop.description.ilike(f'%{query}%')
            )
        ).all()
    else:
        crops = Crop.query.all()
    user = User.query.get(user_id)
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    
    return render_template('search_results.html', crops=crops, search_query=query,user=user, notifications=notifications)

@app.route('/farmer/<int:farmer_id>')
def farmer_profile(farmer_id):
    farmer = User.query.get_or_404(farmer_id)
    # Get crops posted by this farmer
    crops = Crop.query.filter_by(user_id=farmer.id, status='available').all()
    return render_template('farmer_profile.html', farmer=farmer, crops=crops)

@app.route('/buyer/<int:buyer_id>')
def buyer_profile(buyer_id):
    buyer = User.query.get_or_404(buyer_id)
    return render_template('buyer_profile.html', buyer=buyer)

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

