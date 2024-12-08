from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scheduling.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define the models
class Surgeon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100), nullable=True)
    level = db.Column(db.String(10), nullable=False)
    calls_assigned = db.Column(db.Integer, default=0)
    weekend_calls = db.Column(db.Integer, default=0)

class Unavailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    surgeon_id = db.Column(db.Integer, db.ForeignKey('surgeon.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    surgeon = db.relationship('Surgeon', backref=db.backref('unavailability', lazy=True))

class CallSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    surgeon_id = db.Column(db.Integer, db.ForeignKey('surgeon.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    level = db.Column(db.String(10), nullable=False)
    surgeon = db.relationship('Surgeon', backref=db.backref('call_schedule', lazy=True))

# Routes
@app.route('/')
def index():
    surgeons = Surgeon.query.all()
    return render_template('index.html', surgeons=surgeons)

@app.route('/add_surgeon', methods=['GET', 'POST'])
def add_surgeon():
    if request.method == 'POST':
        name = request.form['name']
        specialization = request.form['specialization']
        contact = request.form['contact']
        level = request.form['level']

        new_surgeon = Surgeon(name=name, specialization=specialization, contact=contact, level=level)
        db.session.add(new_surgeon)
        db.session.commit()

        return redirect(url_for('index'))
    return render_template('add_surgeon.html')

@app.route('/set_unavailability/<int:surgeon_id>', methods=['GET', 'POST'])
def set_unavailability(surgeon_id):
    surgeon = Surgeon.query.get_or_404(surgeon_id)
    if request.method == 'POST':
        dates = request.form.getlist('dates')
        for date in dates:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            unavailability = Unavailability(surgeon_id=surgeon.id, date=date_obj)
            db.session.add(unavailability)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('set_unavailability.html', surgeon=surgeon)

@app.route('/generate_schedule', methods=['POST'])
def generate_schedule():
    surgeons = Surgeon.query.all()
    unavailabilities = {surgeon.id: {u.date for u in surgeon.unavailability} for surgeon in surgeons}
    schedule = []

    # Parameters
    start_date = request.form.get('start_date', datetime.now().date().isoformat())
    end_date = request.form.get('end_date', (datetime.now() + timedelta(days=30)).date().isoformat())
    min_spacing = int(request.form.get('min_spacing', 3))
    balance_weekends = request.form.get('balance_weekends', 'false').lower() == 'true'
    
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Track assigned dates and weekends
    assignments = {surgeon.id: [] for surgeon in surgeons}

    for day in range((end_date - start_date).days + 1):
        current_date = start_date + timedelta(days=day)
        is_weekend = current_date.weekday() in [4, 5, 6]

        for surgeon in surgeons:
            if (len(assignments[surgeon.id]) == 0 or
                (current_date - assignments[surgeon.id][-1]).days >= min_spacing) and \
                current_date not in unavailabilities[surgeon.id]:

                if is_weekend and balance_weekends:
                    if surgeon.weekend_calls >= min([s.weekend_calls for s in surgeons]):
                        continue

                schedule.append(CallSchedule(surgeon_id=surgeon.id, date=current_date, level=surgeon.level))
                assignments[surgeon.id].append(current_date)
                surgeon.calls_assigned += 1

                if is_weekend:
                    surgeon.weekend_calls += 1
                break

    db.session.bulk_save_objects(schedule)
    db.session.commit()
    return jsonify({'message': 'Schedule generated successfully'})

# Static files and templates for a better UI
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# HTML and JavaScript for calendar widget integration
@app.route('/set_unavailability_widget/<int:surgeon_id>', methods=['GET', 'POST'])
def set_unavailability_widget(surgeon_id):
    surgeon = Surgeon.query.get_or_404(surgeon_id)
    if request.method == 'POST':
        dates = request.form.getlist('dates')
        for date in dates:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            unavailability = Unavailability(surgeon_id=surgeon.id, date=date_obj)
            db.session.add(unavailability)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('set_unavailability_widget.html', surgeon=surgeon)

# Initialize the database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
