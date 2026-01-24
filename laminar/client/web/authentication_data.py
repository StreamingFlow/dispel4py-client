import json


class AuthenticationData:
    def __init__(self, *, user_name: str, user_password: str):
        self.user_name = user_name
        self.user_password = user_password

    def to_dict(self):
        return {
            "userName": self.user_name,
            "password": self.user_password
        }

    def __str__(self):
        return "AuthenticationData(" + json.dumps(self.to_dict(), indent=4) + ")"
