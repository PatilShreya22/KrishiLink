from flask_sqlalchemy import SQLAlchemy

# Initialize the database object
db = SQLAlchemy()
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(10))
    wallet = db.Column(db.Float, default=0.0, nullable=False)
    phone = db.Column(db.String(20))
    city = db.Column(db.String(100))
    location = db.Column(db.String(200))  # e.g., "Lat: xx.xxxx, Lng: yy.yyyy"
    pincode = db.Column(db.String(6))  # Postal code
    is_profile_complete = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(200))
    bio = db.Column(db.Text)
    bank_account = db.Column(db.String(50))         # for Farmer
    land_size = db.Column(db.String(50))            # for Farmer
    farm_type = db.Column(db.String(100))           # for Farmer
    accepts_cod = db.Column(db.Boolean, default=False)
    company_name = db.Column(db.String(100))        # for Buyer
    business_type = db.Column(db.String(100))       # for Buyer
    preferred_crops = db.Column(db.String(200))
    other_crops = db.Column(db.String(500))     # for Buyer (comma-separated)
    notifications = db.relationship('Notification', back_populates='user')

class Crop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    crop_name = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Integer)
    harvest_date = db.Column(db.String(50))
    status = db.Column(db.String(20), default="available", server_default="available")
    image = db.Column(db.String(200))  # Path to crop image
    description = db.Column(db.Text)
    delivery_method = db.Column(db.String(50))  # 'farmer_delivers' or 'buyer_pickup' 
    user = db.relationship('User', back_populates="crops")
    city = db.Column(db.String(100))
User.crops = db.relationship('Crop', back_populates='user')


class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'))
    quantity = db.Column(db.Integer, default=1)

    crop = db.relationship('Crop')
    user = db.relationship('User')


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'))
    quantity = db.Column(db.Integer)
    total_price = db.Column(db.Integer)
    status = db.Column(db.String(20), default="pending")
    order_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    crop = db.relationship('Crop')
    user = db.relationship('User')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    user = db.relationship('User', back_populates='notifications')

