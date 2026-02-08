print("Hello! This is my first Python app.")

name = "David"
age = 25
print(name, age)

name = input("What is your name? ")
print("Hi", name)

while True:
    try:
        age = int(input("Age? "))
        break
    except ValueError:
        print("Please enter a valid integer for age.")

if age >= 18:
    print("Adult")
else:
    print("Not adult")

for i in range(5):
    print("i is", i)

def greet(person):
    return "Hello " + person

print(greet("David"))
