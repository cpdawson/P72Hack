from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class TrafficEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.String(100))
    is_peak = db.Column(db.Integer)
    vehicle_class = db.Column(db.String(50))
    detection_group = db.Column(db.String(50))
    crz_entries = db.Column(db.Integer)
    excluded_roadway_entries = db.Column(db.Integer)