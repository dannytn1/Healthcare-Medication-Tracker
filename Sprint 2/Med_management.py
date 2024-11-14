import tkinter as tk
from tkinter import messagebox, simpledialog
from datetime import datetime
import sqlite3
import threading
import time as time_lib
import os

# This is the medication class
class Medication:
    def __init__(self, name, time, days, dosage="", notes=""):
        self.name = name
        self.time = time
        self.days = days  # Now a list of days
        self.dosage = dosage
        self.notes = notes

    def to_dict(self):
        return {
            "name": self.name,
            "time": self.time,
            "days": ','.join(self.days),
            "dosage": self.dosage,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            time=data["time"],
            days=data["days"].split(','),
            dosage=data.get("dosage", ""),
            notes=data.get("notes", "")
        )

    def __str__(self):
        days_str = ', '.join(self.days)
        return f"{self.name} - Time: {self.time}, Days: {days_str}, Dosage: {self.dosage}"

# User this is how u add and people 
class User:
    def __init__(self, username):
        self.username = username
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
            "medications": [med.to_dict() for med in self.medications]
        }

    @classmethod
    def from_dict(cls, data):
        user = cls(data["username"])
        user.medications = [Medication.from_dict(med_data) for med_data in data["medications"]]
        return user

# ReminderService class
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
            current_time = datetime.now().strftime("%H:%M")
            current_day = datetime.now().strftime("%A").lower()
            self.manager.check_reminders(current_time, current_day)
            time_lib.sleep(60)  # Check every minute

# Database pls dont mess with this its the schema 
class Database:
    def __init__(self, db_path="medications.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # Create users table
            c.execute('''CREATE TABLE IF NOT EXISTS users
                        (username TEXT PRIMARY KEY)''')
            # Create medications table with initial schema
            c.execute('''CREATE TABLE IF NOT EXISTS medications
                        (id INTEGER PRIMARY KEY,
                         username TEXT,
                         name TEXT,
                         time TEXT,
                         dosage TEXT,
                         notes TEXT,
                         FOREIGN KEY (username) REFERENCES users (username))''')
            conn.commit()

            # Check if 'days' column exists
            c.execute("PRAGMA table_info(medications)")
            columns = [info[1] for info in c.fetchall()]
            if 'days' not in columns:
                # Add 'days' column to medications table
                c.execute("ALTER TABLE medications ADD COLUMN days TEXT")
                conn.commit()

            conn.close()

    def save_user(self, user):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO users VALUES (?)", (user.username,))

            # Remove old medications for this user
            c.execute("DELETE FROM medications WHERE username=?", (user.username,))

            # Add new medications
            for med in user.medications:
                c.execute("""INSERT INTO medications 
                            (username, name, time, dosage, notes, days)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                          (user.username, med.name, med.time, med.dosage, med.notes, ','.join(med.days)))
            conn.commit()
            conn.close()

    def delete_user(self, username):
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
            if not c.fetchone():
                conn.close()
                return None

            user = User(username)
            c.execute("SELECT * FROM medications WHERE username=?", (username,))
            for row in c.fetchall():
                # Adjusted indices based on the table schema
                # row[0]: id, row[1]: username, row[2]: name, row[3]: time,
                # row[4]: dosage, row[5]: notes, row[6]: days
                med = Medication(
                    name=row[2],
                    time=row[3],
                    dosage=row[4],
                    notes=row[5],
                    days=row[6].split(',') if row[6] else []
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

# UserManager class
class UserManager:
    def __init__(self):
        self.db = Database()
        self.reminder_service = ReminderService(self)

    def add_user(self, username):
        if self.db.load_user(username):
            return False, f"Error: Username '{username}' is already taken."
        user = User(username)
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

    def check_reminders(self, current_time, current_day):
        for username in self.list_users():
            user = self.get_user(username)
            if user:
                for med in user.medications:
                    if med.time == current_time and current_day in [day.lower() for day in med.days]:
                        message = f"{username}, it's time to take {med.name} ({med.dosage})."
                        if med.notes:
                            message += f" Notes: {med.notes}"
                        messagebox.showinfo("Medication Reminder", message)

# GUI Application
def run_gui():
    manager = UserManager()
    manager.reminder_service.start()

    root = tk.Tk()
    root.title("Medication Management System")

    # Global variables to store current username
    current_username = tk.StringVar()
    current_username.set("")

    def add_user():
        username = simpledialog.askstring("Add User", "Enter username:")
        if username:
            success, message = manager.add_user(username.strip())
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

    def on_user_select(event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            username = event.widget.get(index)
            current_username.set(username)
            update_medication_list()

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

        # New window for day selection
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

    def update_medication_list():
        username = current_username.get()
        if not username:
            med_list.delete(0, tk.END)
            return
        user = manager.get_user(username)
        med_list.delete(0, tk.END)
        if user:
            for med in user.medications:
                days_str = ', '.join(med.days)
                med_list.insert(tk.END, f"{med.name} ({days_str} at {med.time})")

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

    def on_closing():
        manager.reminder_service.stop()
        root.destroy()

    # User frame
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

    # Medication frame
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

    update_user_list()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    # Run the GUI application
    run_gui()
