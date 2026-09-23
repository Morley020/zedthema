from app.stats import compare_codings

def test_agreement_perfect():
    a=[{'segment_id':'1','code_name':'Trust'},{'segment_id':'2','code_name':'Safety'}]
    b=[{'segment_id':'1','code_name':'Trust'},{'segment_id':'2','code_name':'Safety'}]
    r=compare_codings(a,b)
    assert r['jaccard']==1.0
    assert r['cohen_kappa']['kappa']==1.0
    assert r['krippendorff_alpha_nominal']['alpha']==1.0

def test_agreement_partial():
    a=[{'segment_id':'1','code_name':'Trust'},{'segment_id':'2','code_name':'Safety'}]
    b=[{'segment_id':'1','code_name':'Trust'},{'segment_id':'2','code_name':'Price'}]
    r=compare_codings(a,b)
    assert 0 < r['jaccard'] < 1
    assert r['cohen_kappa']['units']==2
