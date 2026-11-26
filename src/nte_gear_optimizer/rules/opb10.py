"""PLATTFORM-11: decimal strings, 15 significant digits then 9 places.

Error categories describe input failures, not new game-domain error codes.
No global decimal context changes and no adapters or I/O in this module.
"""
from dataclasses import dataclass
from decimal import Context, Decimal, DecimalException, ROUND_HALF_UP, localcontext
import re


class InputError(ValueError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class Result:
    rounded: str
    verdict: str


def evaluate(value: str | None) -> Result:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise InputError("missing")
    if not isinstance(value, str):
        raise InputError("invalid")
    try:
        number = Decimal(value)
    except (DecimalException, ValueError):
        raise InputError("invalid") from None
    if number.is_nan():
        raise InputError("nan")
    if number.is_infinite():
        raise InputError("infinite")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value):
        raise InputError("invalid")
    # Precision for fixed-point quantization must accommodate the integer part.
    # Both contexts are constructed fresh: ambient precision/rounding/traps
    # cannot affect this call. Decimal constructor preserves all input digits.
    try:
        with localcontext(Context(prec=15, rounding=ROUND_HALF_UP)):
            significant = +number
        precision = max(25, significant.adjusted() + 12)
        with localcontext(Context(prec=precision, rounding=ROUND_HALF_UP)):
            rounded = significant.quantize(Decimal("0.000000001"))
            if rounded.is_zero():
                rounded = rounded.copy_abs()
            verdict = "BETTER" if rounded > Decimal("1.005") else "WORSE" if rounded < Decimal("0.995") else "EQUAL"
            return Result(format(rounded, "f"), verdict)
    except DecimalException:
        raise InputError("invalid") from None
