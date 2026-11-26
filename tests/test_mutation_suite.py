from mutation_suite import run_mutations,MUTATIONS

def test_executed_source_mutations_are_killed():
    report=run_mutations()
    assert len(report)==len(MUTATIONS)==13
    assert all(row['Result']=='KILLED' for row in report)
