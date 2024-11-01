class UserManager:
    def __init__(self):
        self.users = set()

# this part allows the  addition of users as well as cheking if the username is avaible 

    def add_user(self, username):
        if username in self.users:
            return False, f"Error: Username '{username}' is already taken."
        else:
            self.users.add(username)
            return True, f"User '{username}' has been successfully added."

    def list_users(self):
        return list(self.users)

# this part is the manager aka the menu its super basic

def main():
    manager = UserManager()
    while True:
        print("\nUser Management Application")
        print("1. Add a new user")
        print("2. List all users")
        print("3. Exit")
        choice = input("Enter your choice (1-3): ").strip()

#these statements check the allow the sytem to check if the usersname is avalible or invalid

        if choice == '1':
            username = input("Enter a username to add: ").strip()
            success, message = manager.add_user(username)
            print(message)
        elif choice == '2':
            users = manager.list_users()
            if users:
                print("Current users:")
                for user in users:
                    print(f"- {user}")
            else:
                print("No users have been added yet.")
        elif choice == '3':
            print("Exiting application.")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
