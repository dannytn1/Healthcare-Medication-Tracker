class MedicationManager:
    def __init__(self):
        self.users_medications = {}

    def add_user(self, user_id):
        if user_id not in self.users_medications:
            self.users_medications[user_id] = []

    def add_medication(self, user_id, name, day, time):
        if user_id not in self.users_medications:
            print(f"Error: No user with ID {user_id}.")
            return
        
        if not self.validate_time(time):
            print("Invalid time format. Please use HH:MM (24-hour format).")
            return

        if not self.validate_day(day):
            print("Invalid day. Please use a weekday (Monday to Sunday).")
            return

        self.users_medications[user_id].append({
            "name": name,
            "day": day,
            "time": time
        })
        print("Medication added successfully.")

    def validate_time(self, time):
        try:
            hours, minutes = map(int, time.split(":"))
            return 0 <= hours < 24 and 0 <= minutes < 60
        except:
            return False

    def validate_day(self, day):
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return day in valid_days

    def display_medications(self, user_id):
        if user_id in self.users_medications and self.users_medications[user_id]:
            print("Medication Schedule:")
            for med in self.users_medications[user_id]:
                print(f"Name: {med['name']}, Day: {med['day']}, Time: {med['time']}")
        else:
            print("No medications found.")

# Usage
manager = MedicationManager()
manager.add_user("user1")

# Test Case 1
manager.add_medication("user1", "Aspirin", "Monday", "09:00")

# Test Case 2
manager.add_user("user2")
manager.add_medication("user2", "Paracetamol", "Tuesday", "10:00")
manager.add_medication("user2", "Ibuprofen", "Wednesday", "11:00")

# Test Case 3
manager.add_user("user3")
manager.add_medication("user3", "Antacid", "Thursday", "12:00")

# Test Case 4
manager.add_medication("user1", "Vitamin C", "Monday", "25:00")

# Test Case 5
manager.add_medication("user1", "Vitamin D", "Funday", "10:00")

# Test Case 6
manager.display_medications("user2")
