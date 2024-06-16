from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
import numpy as np
import pickle
import sqlite3
import os
import sklearn
import time
import csv

# Initialize Flask app and SocketIO
app = Flask(__name__)
app.secret_key = os.urandom(16)
socketio = SocketIO(app)

# Print sklearn version
print(sklearn.__version__)

# Load models
dtr = pickle.load(open('dtr.pkl', 'rb'))

# Check if static and database folders exist
if not os.path.exists('static'):
    os.makedirs('static')

if not os.path.exists('database'):
    os.makedirs('database')

# SQLite3 setup
conn = sqlite3.connect('database/famx.db', check_same_thread=False)
c = conn.cursor()

# Create table if not exists
c.execute('''CREATE TABLE IF NOT EXISTS Famx(
            Username TEXT,
            Name TEXT,
            phone INTEGER,
            password TEXT
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS hourly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature REAL,
            humidity REAL,
            rain REAL
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                avg_temperature REAL,
                avg_humidity REAL,
                avg_rain REAL
                )''')

c.execute('''CREATE TABLE IF NOT EXISTS monthly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            avg_temperature REAL,
            avg_humidity REAL,
            avg_rain REAL
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS yearly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            soil TEXT DEFAULT 'Red Loam',
            avg_temperature REAL,
            avg_humidity REAL,
            avg_rain REAL
            )''')




conn.commit()

def create_connection(db_file):
    """ create a database connection to the SQLite database specified by db_file """
    conn = None
    try:
        conn = sqlite3.connect('database/famx.db')

    except sqlite3.Error as e:
        print(e)
    return conn

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Debug information (avoid in production)
        print(f"Attempting login with Username: {username}")

        # Query the Famx table for the provided username and password
        c.execute('SELECT * FROM Famx WHERE Username = ? AND password = ?', (username, password))
        user = c.fetchone()  # Fetch the first matching row

        # Print the fetched user information for debugging
        print(f"Fetched user: {user}")

        if user:
            # Set session variables
            session['logged_in'] = True
            session['username'] = username
            session['name'] = user[1]
            # If user exists and password matches, redirect to the home page
            return redirect(url_for('home'))
        else:
            # If user does not exist or password is incorrect, show error message
            return render_template('login.html', err='Please enter correct credentials...')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for('user_login'))

@app.route('/home')
def home():
    if 'logged_in' in session:
        return render_template('home.html', name=session['name'])
    else:
        return redirect(url_for('user_login'))

@app.route('/contact')
def contact():
    if 'logged_in' in session:
        return render_template('contact.html', name=session.get('name'))
    else:
        # Redirect to login page if the user is not logged in
        return redirect(url_for('user_login'))

@app.route('/aboutus')
def aboutus():
    if 'logged_in' in session:
        return render_template('aboutus.html', name=session.get('name'))
    else:
        # Redirect to login page if the user is not logged in
        return redirect(url_for('user_login'))

@app.route("/predict", methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        # Convert form input to numeric values
        pH = float(request.form['pH'])
        rainfall = float(request.form['rainfall'])
        temperature = float(request.form['temperature'])
        Area_in_hectares = float(request.form['Area_in_hectares'])

        # Create features array
        features = np.array([[pH, rainfall, temperature, Area_in_hectares]])

        # Predict yield
        predicted_yield = dtr.predict(features)[0]

        prediction_message = f"The predicted crop yield is approximately {predicted_yield:.2f} tons."

        if 'logged_in' in session:
            return render_template('prediction.html',
                                   prediction_message=prediction_message,
                                   ph=pH,
                                   rainfall=rainfall,
                                   temperature=temperature,
                                   area_in_hectares=Area_in_hectares,
                                   name=session.get('name'))
        else:
            # If user is not logged in, redirect to login page
            return redirect(url_for('user_login'))
    else:
        if 'logged_in' in session:
            return render_template('prediction.html', name=session.get('name'))
        else:
            # If user is not logged in, redirect to login page
            return redirect(url_for('user_login'))

# List to store readings
readings = []
DATABASE = 'database/famx.db'

@app.route("/add_reading", methods=["POST"])
def add_reading():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    temperature = data.get("temperature")
    humidity = data.get("humidity")
    rain = data.get("rain")
    is_hourly = data.get("is_hourly", False)  # Add this flag to determine if it's an hourly reading

    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    # Create a dictionary for the new reading
    new_reading = {
        "temperature": temperature,
        "humidity": humidity,
        "rain": rain,
        "timestamp": f"{current_date} {current_time}"
    }

    conn = None
    try:
        # Establish a new database connection and cursor
        conn = create_connection(DATABASE)
        c = conn.cursor()

        if is_hourly:
            # Insert the reading into the hourly table
            query_insert_hourly = "INSERT INTO hourly (timestamp, temperature, humidity, rain) VALUES (?, ?, ?, ?)"
            c.execute(query_insert_hourly, (new_reading["timestamp"], temperature, humidity, rain))

            # Calculate the daily averages and insert into the daily table
            query_avg_24_hours = """
                SELECT AVG(temperature) AS avg_temperature, AVG(humidity) AS avg_humidity, AVG(rain) AS avg_rain
                FROM hourly
                WHERE timestamp >= datetime('now', '-1 day')
            """
            c.execute(query_avg_24_hours)
            avg_result = c.fetchone()

            if avg_result:
                avg_temperature = avg_result[0]
                avg_humidity = avg_result[1]
                avg_rain = avg_result[2]

                # Insert the daily average into the daily table
                query_insert_daily_avg = """
                    INSERT INTO daily (timestamp, avg_temperature, avg_humidity, avg_rain)
                    VALUES (?, ?, ?, ?)
                """
                c.execute(query_insert_daily_avg, (f"{current_date} {current_time}", avg_temperature, avg_humidity, avg_rain))

                # Calculate the monthly averages and insert into the monthly table
                query_avg_month = """
                    SELECT AVG(avg_temperature) AS avg_temperature, AVG(avg_humidity) AS avg_humidity, AVG(avg_rain) AS avg_rain
                    FROM daily
                    WHERE timestamp >= datetime('now', '-1 month')
                """
                c.execute(query_avg_month)
                avg_month_result = c.fetchone()

                if avg_month_result:
                    avg_month_temperature = avg_month_result[0]
                    avg_month_humidity = avg_month_result[1]
                    avg_month_rain = avg_month_result[2]

                    # Insert the monthly average into the monthly table
                    query_insert_monthly_avg = """
                        INSERT INTO monthly (timestamp, avg_temperature, avg_humidity, avg_rain)
                        VALUES (?, ?, ?, ?)
                    """
                    c.execute(query_insert_monthly_avg, (f"{current_date} {current_time}", avg_month_temperature, avg_month_humidity, avg_month_rain))

                    # Calculate the yearly averages and insert into the yearly table
                    query_avg_year = """
                        SELECT AVG(avg_temperature) AS avg_temperature, AVG(avg_humidity) AS avg_humidity, AVG(avg_rain) AS avg_rain
                        FROM monthly
                        WHERE timestamp >= datetime('now', '-1 year')
                    """
                    c.execute(query_avg_year)
                    avg_year_result = c.fetchone()

                    if avg_year_result:
                        avg_year_temperature = avg_year_result[0]
                        avg_year_humidity = avg_year_result[1]
                        avg_year_rain = avg_year_result[2]

                        # Insert the yearly average into the yearly table
                        query_insert_yearly_avg = """
                            INSERT INTO yearly (timestamp,soil, avg_temperature, avg_humidity, avg_rain)
                            VALUES (?, ?, ?, ?)
                        """
                        c.execute(query_insert_yearly_avg, (f"{current_date} {current_time}", avg_year_temperature, avg_year_humidity, avg_year_rain))

        # Add the new reading to the list (optional, if you want to keep it in memory)
        new_reading["id"] = c.lastrowid
        readings.append(new_reading)

        # Notify clients about the new reading
        socketio.emit('new_reading', new_reading)

        conn.commit()  # Commit to save the insert in the database

        return jsonify({"status": "success", "id": c.lastrowid}), 200
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()



@app.route("/get_readings", methods=["GET"])
def get_readings():
    return jsonify(readings), 200

@app.route("/main")
def main():
    if 'logged_in' in session:
        return render_template("main.html", name=session.get('name'))
    else:
        return redirect(url_for('user_login'))

# Export yearly data to CSV
def export_yearly_data_to_csv():
    conn = create_connection(DATABASE)
    if conn:
        cursor = conn.cursor()
        query = "SELECT * FROM yearly"
        cursor.execute(query)
        rows = cursor.fetchall()

        # Define the CSV file path and name
        csv_file_path = r'C:\Users\rvima\MP OG - Copy\yearly_data.csv'

        # Write the data to the CSV file
        with open(csv_file_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)

            # Write the header
            column_names = [description[0] for description in cursor.description]
            csvwriter.writerow(column_names)

            # Write the data rows
            csvwriter.writerows(rows)

        print(f"Data exported successfully to {csv_file_path}")
        conn.close()
    else:
        print("Error! Cannot create the database connection.")

if __name__ == "__main__":
    export_yearly_data_to_csv()
    try:
        socketio.run(app, host='0.0.0.0', port=8181, debug=True, allow_unsafe_werkzeug=True)
    finally:
        conn.close()
