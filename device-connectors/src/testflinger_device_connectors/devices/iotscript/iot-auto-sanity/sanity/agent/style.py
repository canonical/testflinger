import shutil

columns = shutil.get_terminal_size().columns


def gen_head_string(title):
    return f"======== {title} ========".center(columns)
