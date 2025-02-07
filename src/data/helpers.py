from datetime import datetime
from typing import List


def split_filename(filename: str) -> List[str]:
    ext_idx = filename.rfind(".")
    if ext_idx == 0:
        return ["", filename]
    elif ext_idx < 0:
        return [filename, ""]
    else:
        return [filename[:ext_idx], filename[ext_idx:]]


def split_filename_from_path(path_to_file: str) -> List[str]:
    last_slash_idx = path_to_file.rfind("/")
    if last_slash_idx == 0:
        return split_filename(path_to_file[1:])
    elif last_slash_idx < 0:
        return split_filename(path_to_file)
    else:
        return split_filename(path_to_file[last_slash_idx + 1:])


def get_filename_from_timestamp(path_to_file: str) -> str:
    filename, extension = split_filename_from_path(path_to_file)
    timestamp = datetime.now().time().strftime("%H%M%S")
    return f"{filename}_{timestamp}{extension}"
