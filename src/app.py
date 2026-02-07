def run_app():
    while True:
        print("\n=== My App ===")
        print("1) Say hello")
        print("2) Add two numbers")
        print("0) Exit")

        choice = input("Choose: ").strip()

        if choice == "1":
            say_hello()
        elif choice == "2":
            add_two_numbers()
        elif choice == "0":
            print("Bye!")
            break
        else:
            print("Invalid choice. Try again.")

def say_hello():
    name = input("Name: ")
    print(f"Hello, {name}!")

def add_two_numbers():
    a = float(input("First number: "))
    b = float(input("Second number: "))
    print("Result:", a + b)