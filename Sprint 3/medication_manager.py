import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
from datetime import datetime, date, timedelta
import sqlite3
import threading
import time as time_lib
import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email credentials
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))

# Logging Configuration
logging.basicConfig(level=logging.INFO)

# Carrier Email Gateways
CARRIER_EMAIL_GATEWAYS = {
    "AT&T": "txt.att.net",
    "Verizon": "vtext.com",
    "T-Mobile": "tmomail.net",
    "Sprint": "messaging.sprintpcs.com",
    # Add other carriers as needed
}

# Medication Class
class Medication:
    def __init__(self, name, time, days, dosage="", notes="", taken_date=None):
        self.name = name
        self.time = time  # Stored as a string "HH:MM"
        self.days = days  # List of days
        self.dosage = dosage
        self.notes = notes
        self.taken_date = taken_date  # Date when medication was last taken

    def to_dict(self):
        return {
            "name": self.name,
            "time": self.time,
            "days": ','.join(self.days),
            "dosage": self.dosage,
            "notes": self.notes,
            "taken_date": self.taken_date.strftime("%Y-%m-%d") if self.taken_date else None
        }

    @classmethod
    def from_dict(cls, data):
        taken_date_str = data.get("taken_date")
        taken_date = datetime.strptime(taken_date_str, "%Y-%m-%d").date() if taken_date_str else None
        return cls(
            name=data["name"],
            time=data["time"],
            days=data["days"].split(','),
            dosage=data.get("dosage", ""),
            notes=data.get("notes", ""),
            taken_date=taken_date
        )

    def __str__(self):
        days_str = ', '.join(self.days)
        return f"{self.name} - Time: {self.time}, Days: {days_str}, Dosage: {self.dosage}"

# User Class
class User:
    def __init__(self, username, email, phone_number, carrier):
        self.username = username
        self.email = email
        self.phone_number = phone_number
        self.carrier = carrier
        self.medications = []

    def add_medication(self, medication):
        self.medications.append(medication)
        return True, f"Medication '{medication.name}' added successfully."

    def remove_medication(self, medication_name):
        for med in self.medications:
            if med.name == medication_name:
                self.medications.remove(med)
                return True, f"Medication '{medication_name}' removed successfully."
        return False, f"Medication '{medication_name}' not found."

    def get_medications(self):
        return self.medications

    def to_dict(self):
        return {
            "username": self.username,
            "email": self.email,
            "phone_number": self.phone_number,
            "carrier": self.carrier,
            "medications": [med.to_dict() for med in self.medications]
        }

    @classmethod
    def from_dict(cls, data):
        user = cls(
            data["username"],
            data.get("email", ""),
            data.get("phone_number", ""),
            data.get("carrier", "")
        )
        user.medications = [Medication.from_dict(med_data) for med_data in data["medications"]]
        return user

# Database Class
class Database:
    def __init__(self, db_path="medications.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # Create users table with email, phone_number, and carrier
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    email TEXT,
                    phone_number TEXT,
                    carrier TEXT
                )
            ''')
            # Create medications table
            c.execute('''CREATE TABLE IF NOT EXISTS medications
                        (id INTEGER PRIMARY KEY, username TEXT, name TEXT, time TEXT, dosage TEXT, 
                         notes TEXT, days TEXT, taken_date TEXT,
                         FOREIGN KEY (username) REFERENCES users (username))''')
            conn.commit()
            conn.close()

    def save_user(self, user):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO users (username, email, phone_number, carrier) VALUES (?, ?, ?, ?)",
                      (user.username, user.email, user.phone_number, user.carrier))
            c.execute("DELETE FROM medications WHERE username=?", (user.username,))
            for med in user.medications:
                c.execute("""INSERT INTO medications (username, name, time, dosage, notes, days, taken_date)
                             VALUES (?, ?, ?, ?, ?, ?, ?)""",
                          (user.username, med.name, med.time, med.dosage, med.notes, ','.join(med.days),
                           med.taken_date.strftime("%Y-%m-%d") if med.taken_date else None))
            conn.commit()
            conn.close()

    def delete_user(self, username):
        """Remove user and associated medications from the database."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE username=?", (username,))
            c.execute("DELETE FROM medications WHERE username=?", (username,))
            conn.commit()
            conn.close()

    def load_user(self, username):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=?", (username,))
            row = c.fetchone()
            if not row:
                conn.close()
                return None
            user = User(username=row[0], email=row[1], phone_number=row[2], carrier=row[3])
            c.execute("SELECT * FROM medications WHERE username=?", (username,))
            for med_row in c.fetchall():
                # med_row indices: id, username, name, time, dosage, notes, days, taken_date
                taken_date = None
                if med_row[7]:
                    try:
                        taken_date = datetime.strptime(med_row[7], "%Y-%m-%d").date()
                    except ValueError:
                        taken_date = None
                med = Medication(
                    name=med_row[2],
                    time=med_row[3],
                    dosage=med_row[4],
                    notes=med_row[5],
                    days=med_row[6].split(','),
                    taken_date=taken_date
                )
                user.medications.append(med)
            conn.close()
            return user

    def get_all_users(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT username FROM users")
            users = [row[0] for row in c.fetchall()]
            conn.close()
            return users

# Reminder Service
class ReminderService:
    def __init__(self, manager):
        self._running = False
        self._thread = None
        self.manager = manager

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run)
            self._thread.daemon = True
            self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            current_time_str = datetime.now().strftime("%H:%M")
            current_day = datetime.now().strftime("%A").lower()
            self.manager.check_reminders(current_time_str, current_day)
            time_lib.sleep(60)  # Check every minute

# User Manager
class UserManager:
    def __init__(self):
        self.db = Database()
        self.reset_medication_statuses()
        self.reminder_service = ReminderService(self)
        self.reset_thread = threading.Thread(target=self.reset_medication_statuses_daily)
        self.reset_thread.daemon = True
        self.reset_thread.start()

    def add_user(self, username, email, phone_number, carrier):
        if self.db.load_user(username):
            return False, f"Error: Username '{username}' is already taken."
        user = User(username, email, phone_number, carrier)
        self.db.save_user(user)
        return True, f"User '{username}' has been successfully added."

    def remove_user(self, username):
        if not self.db.load_user(username):
            return False, f"Error: User '{username}' does not exist."
        self.db.delete_user(username)
        return True, f"User '{username}' has been successfully removed."

    def list_users(self):
        return self.db.get_all_users()

    def get_user(self, username):
        return self.db.load_user(username)

    def save_user(self, user):
        self.db.save_user(user)

    def validate_time(self, time_str):
        try:
            datetime.strptime(time_str, "%H:%M")
            return True, "Valid time"
        except ValueError:
            return False, "Invalid time format. Please use HH:MM format (24-hour)"

    def send_email(self, to_address, subject, body):
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_address
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
            logging.info(f"Email sent to {to_address}")
        except Exception as e:
            logging.error(f"Failed to send email to {to_address}: {e}")

    def send_sms_via_email(self, user, subject, body):
        carrier_domain = CARRIER_EMAIL_GATEWAYS.get(user.carrier)
        if not carrier_domain:
            logging.error(f"Carrier not supported for user {user.username}")
            return
        sms_email = f"{user.phone_number}@{carrier_domain}"
        self.send_email(sms_email, subject, body)

    def check_reminders(self, current_time_str, current_day):
        today = date.today()
        current_time = datetime.strptime(current_time_str, "%H:%M").time()
        for username in self.list_users():
            user = self.get_user(username)
            if user:
                for med in user.medications:
                    if current_day in [day.lower() for day in med.days]:
                        med_time = datetime.strptime(med.time, "%H:%M").time()
                        # Check if medication time is less than or equal to current time
                        if med_time <= current_time:
                            # If medication hasn't been taken today
                            if med.taken_date != today:
                                subject = f"Medication Reminder: {med.name}"
                                message = f"Hello {user.username},\n\nIt's time to take your medication '{med.name}' ({med.dosage})."
                                if med.notes:
                                    message += f"\n\nNotes: {med.notes}"
                                # Send email
                                self.send_email(user.email, subject, message)
                                # Send SMS via Email-to-SMS
                                self.send_sms_via_email(user, subject, message)
                                # Mark as sent to avoid spamming
                                med.taken_date = today
                                self.save_user(user)

    def reset_medication_statuses_daily(self):
        while True:
            now = datetime.now()
            next_day = datetime.combine(now.date(), datetime.min.time()) + timedelta(days=1)
            wait_time = (next_day - now).total_seconds()
            time_lib.sleep(wait_time)
            self.reset_medication_statuses()

    def reset_medication_statuses(self):
        """Reset the taken_date for medications."""
        for username in self.list_users():
            user = self.get_user(username)
            if user:
                updated = False
                for med in user.medications:
                    if med.taken_date is not None:
                        med.taken_date = None
                        updated = True
                if updated:
                    self.save_user(user)

def run_gui():
    manager = UserManager()
    manager.reminder_service.start()

    root = tk.Tk()
    root.title("Medication Management System")

    current_username = tk.StringVar()
    current_username.set("")

    def add_user():
        username = simpledialog.askstring("Add User", "Enter username:")
        if username:
            email = simpledialog.askstring("Add User", "Enter email address:")
            if not email:
                messagebox.showwarning("Add User", "Email address is required.")
                return
            phone_number = simpledialog.askstring("Add User", "Enter phone number (digits only):")
            if not phone_number:
                messagebox.showwarning("Add User", "Phone number is required.")
                return
            # List of supported carriers
            carriers = list(CARRIER_EMAIL_GATEWAYS.keys())
            carrier = simpledialog.askstring("Add User", f"Enter mobile carrier ({', '.join(carriers)}):")
            if not carrier or carrier not in carriers:
                messagebox.showwarning("Add User", "Valid mobile carrier is required.")
                return
            success, message = manager.add_user(username.strip(), email.strip(), phone_number.strip(), carrier.strip())
            messagebox.showinfo("Add User", message)
            update_user_list()

    def remove_user():
        username = current_username.get()
        if not username:
            messagebox.showwarning("Remove User", "Please select a user to remove.")
            return
        confirm = messagebox.askyesno("Confirm Remove User", f"Are you sure you want to remove user '{username}'?")
        if confirm:
            success, message = manager.remove_user(username)
            if success:
                current_username.set("")
                update_user_list()
                update_medication_list()
            messagebox.showinfo("Remove User", message)

    def update_user_list():
        user_list.delete(0, tk.END)
        users = manager.list_users()
        for user in users:
            user_list.insert(tk.END, user)

    def update_medication_list():
        username = current_username.get()
        med_list.delete(0, tk.END)
        if not username:
            return
        user = manager.get_user(username)
        if user:
            for med in user.medications:
                days_str = ', '.join(med.days)
                med_list.insert(tk.END, f"{med.name} ({days_str} at {med.time})")

    def add_medication():
        username = current_username.get()
        if not username:
            messagebox.showwarning("Add Medication", "Please select a user first.")
            return

        med_name = simpledialog.askstring("Medication Name", "Enter medication name:")
        if not med_name:
            return

        time_str = simpledialog.askstring("Medication Time", "Enter time (HH:MM):")
        if not time_str:
            return
        time_valid, time_message = manager.validate_time(time_str)
        if not time_valid:
            messagebox.showerror("Invalid Time", time_message)
            return

        # Select days for the medication
        day_selection = tk.Toplevel(root)
        day_selection.title("Select Days")

        tk.Label(day_selection, text="Select days for the medication:").pack()

        days_vars = {}
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days_of_week:
            var = tk.BooleanVar()
            chk = tk.Checkbutton(day_selection, text=day, variable=var)
            chk.pack(anchor='w')
            days_vars[day] = var

        def confirm_days():
            selected_days = [day for day, var in days_vars.items() if var.get()]
            if not selected_days:
                messagebox.showwarning("No Days Selected", "Please select at least one day.")
            else:
                day_selection.destroy()
                dosage = simpledialog.askstring("Dosage", "Enter dosage (optional):") or ""
                notes = simpledialog.askstring("Notes", "Enter any notes (optional):") or ""

                user = manager.get_user(username)
                medication = Medication(med_name, time_str, selected_days, dosage, notes)
                success, message = user.add_medication(medication)
                if success:
                    manager.save_user(user)
                messagebox.showinfo("Add Medication", message)
                update_medication_list()

        confirm_btn = tk.Button(day_selection, text="Confirm", command=confirm_days)
        confirm_btn.pack(pady=5)

    def remove_medication():
        username = current_username.get()
        if not username:
            messagebox.showwarning("Remove Medication", "Please select a user first.")
            return
        selection = med_list.curselection()
        if not selection:
            messagebox.showwarning("Remove Medication", "Please select a medication to remove.")
            return
        index = selection[0]
        med_info = med_list.get(index)
        med_name = med_info.split(' (')[0]

        user = manager.get_user(username)
        success, message = user.remove_medication(med_name)
        if success:
            manager.save_user(user)
        messagebox.showinfo("Remove Medication", message)
        update_medication_list()

    def view_upcoming():
        username = current_username.get()
        if not username:
            messagebox.showwarning("View Reminders", "Please select a user first.")
            return
        user = manager.get_user(username)
        if user:
            today = date.today()
            current_time = datetime.now().time()
            current_day = datetime.now().strftime("%A").lower()
            upcoming_meds = []
            for med in user.medications:
                if current_day in [day.lower() for day in med.days]:
                    med_time = datetime.strptime(med.time, "%H:%M").time()
                    if med_time >= current_time:
                        upcoming_meds.append(f"{med.name} at {med.time}")
            if upcoming_meds:
                message = "Upcoming medications:\n" + "\n".join(upcoming_meds)
            else:
                message = "No upcoming medications for today."
            messagebox.showinfo("Upcoming Reminders", message)

    def export_data():
        file_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                                                 title="Choose location to save backup")
        if file_path:
            data = {}
            for username in manager.list_users():
                user = manager.get_user(username)
                if user:
                    data[username] = user.to_dict()
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("Export Data", "Data exported successfully.")

    def import_data():
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                                               title="Select backup file to restore")
        if file_path:
            with open(file_path, 'r') as f:
                data = json.load(f)
            for username, user_data in data.items():
                user = User.from_dict(user_data)
                manager.save_user(user)
            messagebox.showinfo("Import Data", "Data imported successfully.")
            update_user_list()
            update_medication_list()

    def on_user_select(event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            username = event.widget.get(index)
            current_username.set(username)
            update_medication_list()

    def on_closing():
        manager.reminder_service.stop()
        root.destroy()

    # User List Frame
    user_frame = tk.Frame(root)
    user_frame.pack(side=tk.LEFT, padx=10, pady=10)

    user_label = tk.Label(user_frame, text="Users")
    user_label.pack()

    user_list = tk.Listbox(user_frame, height=15)
    user_list.pack()
    user_list.bind('<<ListboxSelect>>', on_user_select)

    add_user_btn = tk.Button(user_frame, text="Add User", command=add_user)
    add_user_btn.pack(pady=5)

    remove_user_btn = tk.Button(user_frame, text="Remove User", command=remove_user)
    remove_user_btn.pack(pady=5)

    # Medication List Frame
    med_frame = tk.Frame(root)
    med_frame.pack(side=tk.LEFT, padx=10, pady=10)

    med_label = tk.Label(med_frame, text="Medications")
    med_label.pack()

    med_list = tk.Listbox(med_frame, height=15)
    med_list.pack()

    add_med_btn = tk.Button(med_frame, text="Add Medication", command=add_medication)
    add_med_btn.pack(pady=5)

    remove_med_btn = tk.Button(med_frame, text="Remove Medication", command=remove_medication)
    remove_med_btn.pack(pady=5)

    view_upcoming_btn = tk.Button(med_frame, text="View Upcoming Reminders", command=view_upcoming)
    view_upcoming_btn.pack(pady=5)

    # Backup and Restore Buttons
    backup_frame = tk.Frame(root)
    backup_frame.pack(side=tk.LEFT, padx=10, pady=10)

    export_btn = tk.Button(backup_frame, text="Export Data", command=export_data)
    export_btn.pack(pady=5)

    import_btn = tk.Button(backup_frame, text="Import Data", command=import_data)
    import_btn.pack(pady=5)

    update_user_list()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    run_gui()
