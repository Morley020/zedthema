"""Agreement statistics used when comparing human or AI coding decisions."""
from collections import Counter
from math import fsum

def _labels(codings):
    """Turn coding records into one label per unit for agreement calculations."""
    out={}
    for x in codings:
        unit=x.get('segment_id') or x.get('unit_id') or x.get('id')
        code=x.get('code_name') or x.get('code') or 'UNCODED'
        if unit is not None: out.setdefault(str(unit), set()).add(str(code))
    # Multi-coded qualitative segments cannot be forced into a single nominal
    # label without losing information. We therefore use a deterministic joined
    # label for Cohen's kappa and clearly report that choice in the result.
    return {k:'|'.join(sorted(v)) if v else 'UNCODED' for k,v in out.items()}

def cohens_kappa(a,b):
    A=_labels(a); B=_labels(b); units=sorted(set(A)|set(B))
    if not units: return {'kappa':1.0,'units':0,'note':'No coding units were supplied.'}
    la=[A.get(u,'UNCODED') for u in units]; lb=[B.get(u,'UNCODED') for u in units]
    agree=sum(x==y for x,y in zip(la,lb))/len(units)
    ca=Counter(la); cb=Counter(lb); pe=sum((ca[k]/len(units))*(cb[k]/len(units)) for k in set(ca)|set(cb))
    kappa=(agree-pe)/(1-pe) if pe < 1 else 1.0
    return {'kappa':round(kappa,6),'observed_agreement':round(agree,6),'expected_agreement':round(pe,6),'units':len(units),'note':'Multi-coded segments are represented as sorted joined nominal labels.'}

def krippendorff_alpha_nominal(a,b):
    A=_labels(a); B=_labels(b); units=sorted(set(A)|set(B))
    if not units: return {'alpha':1.0,'units':0}
    values=[A.get(u,'UNCODED') for u in units]+[B.get(u,'UNCODED') for u in units]
    counts=Counter(values); n=len(values)
    # Expected disagreement for nominal alpha: 1 - sum(n_c(n_c-1))/N(N-1).
    expected=1-sum(v*(v-1) for v in counts.values())/(n*(n-1)) if n>1 else 0
    observed=sum(0 if A.get(u,'UNCODED')==B.get(u,'UNCODED') else 1 for u in units)/len(units)
    alpha=1-observed/expected if expected else 1.0
    return {'alpha':round(alpha,6),'observed_disagreement':round(observed,6),'expected_disagreement':round(expected,6),'units':len(units),'note':'This two-rater nominal implementation is intended for transparent research reporting; validate against a specialist package for final publication.'}

def compare_codings(a,b):
    A={(x.get('segment_id'),x.get('code_name')) for x in a}; B={(x.get('segment_id'),x.get('code_name')) for x in b}; inter=len(A&B); union=len(A|B)
    return {'set_a':len(A),'set_b':len(B),'agreement_pairs':inter,'jaccard':round(inter/union,4) if union else 1.0,'cohen_kappa':cohens_kappa(a,b),'krippendorff_alpha_nominal':krippendorff_alpha_nominal(a,b)}
