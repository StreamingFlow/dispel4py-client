import pwinput
import sys
import os

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # gets the libraries to write less garbage to the terminal

print("Starting Laminar...")
from laminar.client.d4pyclient import d4pClient

if "--register" in sys.argv:
    client = d4pClient()
    user_name = os.getenv('LAMINAR_USERNAME')
    user_password = os.getenv('LAMINAR_PASSWORD')

    if user_name is not None and user_password is not None:
        client.register(user_name, user_password)
    else:
        user_name = input("Username: ")
        user_password = pwinput.pwinput("Password: ")
        client.register(user_name, user_password)
    print(f"Successfully registered user {user_name}")
    sys.exit(0)

from laminar.cli import LaminarCLI

LaminarCLI().cmdloop()
