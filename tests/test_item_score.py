import json
from pathlib import Path
from nte_gear_optimizer.legacy.item_score import score_item

POLICY=json.loads((Path(__file__).parent/'fixtures/scoring_policy.json').read_text(encoding='utf-8'))['Policy']
W={**{str(i):'10' for i in range(4)},**{str(i):'1' for i in range(4,8)}}
def rolls(start=0,value='10'):
    return [{'StatID':str(i),'Value':value,'Baseline':'10','Minimum':'0','Maximum':'10'} for i in range(start,start+4)]

def test_important_weak_perfect_poor_and_ark_independence():
    strong=score_item(rolls(),W,POLICY,required_slots=4)
    weak=score_item(rolls(4),W,POLICY,required_slots=4)
    poor=score_item(rolls(value='1'),W,POLICY,required_slots=4)
    assert strong['Overall']=='1' and strong['Recommendation']=='Keep'
    assert weak['Quality']=='1' and weak['Relevance']=='0.1' and weak['Recommendation']=='Recycle'
    assert poor['Quality']=='0.1' and poor['Relevance']=='1'
    # No Ark field in API: NEG_BLANK_ARK cannot hide this intrinsic score.
    assert score_item(rolls(),W,POLICY,required_slots=4)==strong

def test_invalid_incomplete_overmaximum_duplicates():
    assert score_item(rolls()[:3],W,POLICY,required_slots=4)['Overall'] is None
    for value in (None,'11','-1'):
        assert score_item(rolls(value=value),W,POLICY,required_slots=4)['Status']=='UNKNOWN'
    dup=rolls();dup[1]['StatID']=dup[0]['StatID']
    assert score_item(dup,W,POLICY,required_slots=4)['Status']=='UNKNOWN'
