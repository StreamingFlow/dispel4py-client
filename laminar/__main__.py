import argparse
import os
import sys
import pwinput

from laminar.screen_printer import print_status, print_text, print_error

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # gets the libraries to write less garbage to the terminal


def main():
    parser = argparse.ArgumentParser(
        prog='laminar',
        description='Laminar client: register a user, convert a Python function '
                    'into a dispel4py PE, or launch the interactive CLI.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--register', action='store_true',
                      help='Register a new user.')
    mode.add_argument('--convert', action='store_true',
                      help='Convert a generic Python function into a dispel4py PE.')
    parser.add_argument('-u', '--username',
                        help='Username for --register (falls back to LAMINAR_USERNAME, then prompt).')
    parser.add_argument('-f', '--filepath',
                        help='Path to the Python file to convert (required with --convert).')
    args = parser.parse_args()

    print_status("Starting Laminar...")

    if args.register:
        from laminar.client.d4pyclient import d4pClient
        client = d4pClient()
        user_name = args.username or os.getenv('LAMINAR_USERNAME')
        user_password = os.getenv('LAMINAR_PASSWORD')
        if user_name is None:
            user_name = input("Username: ")
        if user_password is None:
            user_password = pwinput.pwinput("Password: ")
        client.register(user_name, user_password)
        print_status(f"Successfully registered user {user_name}")

    elif args.convert:
        if not args.filepath:
            parser.error("--convert requires -f/--filepath")
        from laminar.conversion.ConvertToPE import ConvertToPE
        converted = ConvertToPE(args.filepath, True)  # True = read from file
        if converted.pe is None:
            print_error(
                "Could not convert: the function must take at most 1 parameter "
                "and return at most 1 value (Producer/Iterative/Consumer).")
            exit(-1)

        print_text(converted.pe)
        new_filename = args.filepath.replace(".py", "_pe.py")
        print_status(f"Storing converted PE to {new_filename}")
        with open(new_filename, "w") as f:
            f.write(converted.pe)
            f.write("\n")
        print_status(f"Successfully stored PE to {new_filename}")

    else:
        from laminar.cli import LaminarShell, ShellSession, _run_handoff_tool
        from laminar.clitools.login import run_login

        from laminar.client.d4pyclient import d4pClient

        client = d4pClient()
        if client.get_login() is None:
            if not run_login(client):
                print_error("Login cancelled.")
                sys.exit(0)

        session = ShellSession(client)
        while True:
            result = LaminarShell(session).run()
            if not result:  # None -> quit
                break
            if result[0] == "run":
                _, name, rest = result
                _run_handoff_tool(session, name, rest)


if __name__ == "__main__":
    main()
