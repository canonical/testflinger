import os


def syscmd(message=""):
    status = os.system(message)
    return status
