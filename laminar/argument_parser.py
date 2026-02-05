import argparse
import sys

import argparse
import sys


def type_checker(value):
    if value.isdigit():
        return int(value)
    return value

class CustomArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def error(self, message):
        # called by argparse on bad input
        if self.exit_on_error:
            super().error(message)
        else:
            raise ValueError(message)

    def exit(self, status=0, message=None):
        if self.exit_on_error:
            super().exit(status, message)
        else:
            if message:
                raise ValueError(message)
