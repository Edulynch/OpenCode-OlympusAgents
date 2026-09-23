from completion_target import combine

def test_combine_uses_both_inputs():
    assert combine(2, 3) == 5
