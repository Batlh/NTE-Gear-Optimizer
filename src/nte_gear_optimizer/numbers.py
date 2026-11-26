"""Canonical decimal inputs, independent of the process Decimal context."""
from decimal import Decimal, Context, ROUND_HALF_UP, localcontext
from functools import wraps
import re

CONTEXT = Context(prec=120, rounding=ROUND_HALF_UP)
CANONICAL = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z')

class ValueUnavailable(ValueError):
    def __init__(self, field, invalid=False):
        self.field, self.invalid = field, invalid
        super().__init__('Ungültiger Wert: '+field if invalid else 'Wert fehlt: '+field)

def number(value, field='value', *, nonnegative=False):
    if value is None or value=='':
        raise ValueUnavailable(field)
    if not isinstance(value,str) or not CANONICAL.fullmatch(value):
        raise ValueUnavailable(field,True)
    n=Decimal(value)
    if not n.is_finite() or (nonnegative and n<0):
        raise ValueUnavailable(field,True)
    return n

def isolated(function):
    @wraps(function)
    def call(*args,**kwargs):
        with localcontext(CONTEXT):
            return function(*args,**kwargs)
    return call

def text(n):
    if n is None:
        return None
    if n==0:
        return '0'
    return format(n,'f').rstrip('0').rstrip('.') if '.' in format(n,'f') else format(n,'f')
