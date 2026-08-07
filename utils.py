import math
import random
import string

def humanbytes(size: int) -> str:
    if not size:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {units[i]}"

def generate_code(length=10) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
