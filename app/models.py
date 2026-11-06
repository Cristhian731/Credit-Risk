from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    profiles = db.relationship("CreditProfile", backref="user", lazy=True)
    applications = db.relationship("LoanApplication", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class CreditProfile(db.Model):
    __tablename__ = "credit_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20))
    monthly_income = db.Column(db.Numeric(12, 2), nullable=False)
    employment_status = db.Column(db.String(30), nullable=False)
    years_employment = db.Column(db.Numeric(4, 1), nullable=False)
    credit_score = db.Column(db.Integer, nullable=False)          # 300-850
    existing_debt = db.Column(db.Numeric(12, 2), nullable=False)
    debt_to_income_ratio = db.Column(db.Numeric(5, 2), nullable=False)  # %
    previous_loans = db.Column(db.Integer, nullable=False, default=0)
    payment_history = db.Column(db.String(30), nullable=False)

    created_at = db.Column(db.DateTime, default=utcnow)

    applications = db.relationship("LoanApplication", backref="profile", lazy=True)


class LoanApplication(db.Model):
    __tablename__ = "loan_applications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    profile_id = db.Column(db.Integer, db.ForeignKey("credit_profiles.id"), nullable=False)

    loan_amount = db.Column(db.Numeric(12, 2), nullable=False)
    loan_term_months = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    prediction = db.relationship("Prediction", backref="application",
                                 uselist=False, lazy=True)


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("loan_applications.id"),
                               unique=True, nullable=False)

    is_viable = db.Column(db.Boolean, nullable=False)
    default_probability = db.Column(db.Float, nullable=False)     # 0.0 - 1.0
    risk_category = db.Column(db.String(20), nullable=False)      # approved / medium / high
    model_version = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=utcnow)