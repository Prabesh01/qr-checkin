from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
import datetime as dt
import secrets

tz_NP = dt.timezone(dt.timedelta(hours=5, minutes=45))

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///checkin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    username = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(120), nullable=False)

class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Integer, db.ForeignKey('user.username'))
    attendee = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(80), nullable=False)
    checkin_time = db.Column(db.DateTime, default=lambda: dt.datetime.now(tz_NP).replace(second=0, microsecond=0))
    # combined unique
    __table_args__ = (db.UniqueConstraint('attendee', 'location','checkin_time', name='unique_checkin'),)


# Create tables
with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(username='admin', password='pass')
        db.session.add(admin_user)
        db.session.commit()

# Authentication
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('scanner'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = username
            return redirect(url_for('scanner'))
        return render_template('login.html', message='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Main Scanner
@app.route('/')
def scanner():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('scanner.html')

# API Endpoints
@app.route('/api/scan', methods=['POST'])
def handle_scan():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    new_checkin = CheckIn(
        username=session['username'],
        attendee=data['attendee'],
        location=data['location']
    )
    db.session.add(new_checkin)
    try: db.session.commit()
    except IntegrityError: pass
    return jsonify({'status': 'success'})

@app.route('/admin')
def admin():
    if not session.get('username') or session['username'] != 'admin':
        return redirect(url_for('login'))
    all_users = User.query.all()
    return render_template('admin.html', all_users=all_users)

# Add these routes to your Flask app

@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if not session.get('username') or session['username'] != 'admin':
        return redirect(url_for('login'))

    username = request.form['username']
    password = request.form['password']

    if not User.query.filter_by(username=username).first():
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()

    return redirect(url_for('admin'))

@app.route('/admin/delete_user/<username>', methods=['POST'])
def delete_user(username):
    if not session.get('username') or session['username'] != 'admin':
        return redirect(url_for('login'))
    if username == 'admin':
        return redirect(url_for('admin'))
    user = User.query.filter_by(username=username).first()
    if user:
        db.session.delete(user)
        db.session.commit()

    return redirect(url_for('admin'))

# Admin API
@app.route('/api/admin/checkins')
def get_checkins():
    if not session.get('username') or session['username'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    # Get all checkins with user info
    checkins = db.session.query(CheckIn, User.username)\
              .join(User, CheckIn.username == User.username)\
              .order_by(CheckIn.checkin_time.desc()).all()

    result = []
    for checkin, username in checkins:
        result.append({
            'username': username,
            'attendee': checkin.attendee,
            'location': checkin.location,
            'time': checkin.checkin_time.isoformat()
        })
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
