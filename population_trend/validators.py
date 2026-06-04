def to_int(value: str, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是整数。") from None
    if number < 0:
        raise ValueError(f"{label}不能为负数。")
    return number


def to_float(value: str, label: str, allow_negative: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是数字。") from None
    if not allow_negative and number < 0:
        raise ValueError(f"{label}不能为负数。")
    return round(number, 2)
