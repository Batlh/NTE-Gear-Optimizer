import csv
from decimal import getcontext, ROUND_DOWN
from pathlib import Path
import pytest
from nte_gear_optimizer.rules.opb10 import evaluate, InputError

ROOT = Path(__file__).resolve().parents[1]
VECTORS = list(csv.DictReader((ROOT/'tests/fixtures/opb10.tsv').open(encoding='utf-8'), delimiter='\t'))

@pytest.mark.parametrize('case', VECTORS)
def test_vector(case):
    actual = evaluate(case['Input'])
    assert (actual.rounded,actual.verdict)==(case['ExpectedRounded'],case['ExpectedVerdict'])

@pytest.mark.parametrize('value,expected', [
    ('1.234567890499995','1.234567891'),
    ('-1.234567890499995','-1.234567891'),
    ('0.0000000015','0.000000002'),
    ('-0.0000000015','-0.000000002'),
    ('123456789012344.5','123456789012345.000000000'),
    ('-123456789012344.5','-123456789012345.000000000'),
    ('1.'+'0'*90+'1','1.000000000'),
])
def test_additional_rounding(value,expected):
    assert evaluate(value).rounded==expected

@pytest.mark.parametrize('value,category',[(None,'missing'),('','missing'),(' ','missing'),('NaN','nan'),('sNaN','nan'),('Infinity','infinite'),('-Infinity','infinite'),('bad','invalid'),(1.0,'invalid'),('1_000','invalid'),(' 1','invalid')])
def test_error_categories(value,category):
    with pytest.raises(InputError) as caught: evaluate(value)
    assert caught.value.category==category

def test_ambient_context_independence():
    original=getcontext().copy()
    try:
        getcontext().prec=2
        getcontext().rounding=ROUND_DOWN
        for signal in getcontext().traps: getcontext().traps[signal]=True
        test_vector(VECTORS[0])
        assert getcontext().prec==2
    finally:
        from decimal import setcontext
        setcontext(original)

@pytest.mark.parametrize('mutant',['half_even','down','float_input','skip_significant','float_round'])
def test_mutations_are_detected(mutant):
    # Execute deliberately faulty implementations against the real vector oracle.
    # Passing means the oracle catches a semantic difference, not a constant check.
    from decimal import Decimal, Context, localcontext, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN
    def wrong(text):
        number=Decimal(str(float(text))) if mutant=='float_input' else Decimal(text)
        mode={'half_even':ROUND_HALF_EVEN,'down':ROUND_DOWN}.get(mutant,ROUND_HALF_UP)
        with localcontext(Context(prec=15,rounding=mode)):
            number=number if mutant=='skip_significant' else +number
        with localcontext(Context(prec=max(80,number.adjusted()+12),rounding=mode)):
            number=Decimal(str(round(float(number),9))) if mutant=='float_round' else number.quantize(Decimal('0.000000001'))
            if number.is_zero():number=number.copy_abs()
            return format(number,'.9f')
    probes=[(v['Input'],v['ExpectedRounded']) for v in VECTORS]+[('123456789012344.5','123456789012345.000000000'),('1.00500000049999499','1.005000000')]
    assert any(wrong(value)!=expected for value,expected in probes),mutant
