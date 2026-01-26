import pwinput
import sys
import os

from laminar.screen_printer import print_status, print_text

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # gets the libraries to write less garbage to the terminal

print_status("Starting Laminar...")

if "--register" in sys.argv:

    from laminar.client.d4pyclient import d4pClient
    client = d4pClient()
    user_name = os.getenv('LAMINAR_USERNAME')
    user_password = os.getenv('LAMINAR_PASSWORD')

    if user_name is not None and user_password is not None:
        client.register(user_name, user_password)
    else:
        user_name = input("Username: ")
        user_password = pwinput.pwinput("Password: ")
        client.register(user_name, user_password)
    print_status(f"Successfully registered user {user_name}")


elif "--convert" in sys.argv:
    from laminar.conversion.ConvertPy import ConvertPyToAST
    codeStr = '''
    class isEven(IterativePE):
        def __init__(self):
            IterativePE.__init__(self)
        def _process(self, input):
            if (input % 2 == 0):
                return True

            else:
                return False'''
    converted = ConvertPyToAST(codeStr, False)
    print_text(converted.result)

else:

    from laminar.cli import LaminarCLI
    LaminarCLI().cmdloop()
