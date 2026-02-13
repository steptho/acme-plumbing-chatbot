# Clear the Screen

import os
os.system("clear")

# functions

# Create the function
# def namer(first_name, last_name):
# 	print(f"Hello there {first_name} {last_name}!")

def adder(num1, num2):
	print(num1 + num2)


# Call the function
# namer("Steve", "Thompson")

# adder(5,4)

# Create a Return Function
# 	return(f"Hello there {first_name} {last_name}!")

# Call the function
# my_name = namer("Steve", "Thompson")

# print(my_name)
# for x in my_name:
	print(x)

# Create a Return Function
def namer(first_name):
	count = 0
	for letter in first_name:
		count +=1
	return(count)

# Call the function
letter_count = namer("Steve Thompson")

print(f"There are {letter_count} letters in that name!")