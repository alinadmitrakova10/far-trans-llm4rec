"""Portable standard-library audit of published raw requests and evaluation."""
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent


def main():
    manifest=json.loads((ROOT/'TRANSFER_MANIFEST.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    groups=json.loads((ROOT/'results/evaluation_groups.json').read_text())
    maps=json.loads((ROOT/'results/evaluation_mappings.json').read_text())
    rows=list(csv.DictReader((ROOT/'results/llm_per_user.csv').open(encoding='utf-8')))
    predictions=list(csv.DictReader((ROOT/'results/llm_top10.csv').open(encoding='utf-8')))
    computed=collections.defaultdict(list);call_count=0
    with zipfile.ZipFile(ROOT/'results/ranker_results.zip') as z:
        assert len(z.namelist())==204
        complete=json.loads(z.read('results/complete.json'))
        assert complete['users']==100 and complete['calls']==600
        for group,mapping in zip(groups,maps):
            uid=group['group_key'];assert uid==mapping['group_key']
            ids=dict(zip(group['candidate_aliases'],mapping['pool_isins']))
            assert len(ids)==20
            saved=json.loads(z.read('results/'+uid+'.json'))
            logs=[json.loads(s) for s in z.read('results/'+uid+'_calls.jsonl').decode().splitlines()]
            assert len(logs)==6
            for branch,subset in [('original',logs[:3]),('permuted',logs[3:])]:
                points=dict.fromkeys(ids,0)
                for i,call in enumerate(subset,1):
                    assert call['user_alias']==uid and call['branch']==branch and call['call']==i
                    assert call['status']=='completed_call' and not call['generated_response_cache_hit']
                    assert hashlib.sha256(call['prompt'].encode()).hexdigest()==call['prompt_sha256']
                    data=json.loads(call['prompt'].split('\n',1)[1])
                    ci=data['candidate_columns'].index('asset_alias')
                    wirepool=[r[ci] for r in data['candidate_rows']]
                    ri=data['candidate_columns'].index('source_cbf_rank')
                    wiremap={r[ci]:group['candidate_aliases'][int(r[ri])-1] for r in data['candidate_rows']}
                    try:
                        value=json.loads(call['text'].strip())
                        valid=type(value)is list and len(value)==10 and all(type(a)is str for a in value) and len(set(value))==10 and set(value)<=set(wirepool)
                    except (ValueError,TypeError):valid=False
                    assert call['invalid']==call['fallback']==(not valid)
                    ranking=call['ranked_aliases']
                    if valid:assert ranking==[wiremap[a] for a in value]
                    assert len(ranking)==len(set(ranking))==10 and set(ranking)<=set(ids)
                    if not valid:assert ranking==group['candidate_aliases'][:10]
                    for score,a in zip(range(10,0,-1),ranking):points[a]+=score
                    call_count+=1
                ranking=sorted(ids,key=lambda a:(-points[a],ids[a]))[:10]
                assert ranking==saved['branches'][branch]['aggregate_aliases']
                expected=[r for r in predictions if r['user_alias']==uid and r['branch']==branch]
                assert [ids[a] for a in ranking]==[r['ISIN'] for r in expected]
                labels=dict(zip(group['candidate_aliases'],group['labels']))
                ideal=math.fsum(1/math.log2(i+2) for i in range(min(10,group['full_truth_count'])))
                actual=math.fsum(labels[a]/math.log2(i+2) for i,a in enumerate(ranking))
                value=actual/ideal if ideal else 0
                row=next(r for r in rows if r['user_alias']==uid and r['branch']==branch)
                assert math.isclose(value,float(row['ndcg_at_10']),abs_tol=1e-14)
                computed[branch].append((value,group['full_truth_count']))
    result=json.loads((ROOT/'hw2/STAGE7_VERIFICATION.json').read_text())
    for branch,values in computed.items():
        allmean=math.fsum(v for v,n in values)/100
        active=[v for v,n in values if n]
        assert len(active)==11
        assert math.isclose(allmean,result['metrics'][branch]['ndcg_at_10'],abs_tol=1e-14)
        assert math.isclose(math.fsum(active)/11,result['metrics'][branch]['ndcg_at_10_nonempty'],abs_tol=1e-14)
        print(branch,allmean,math.fsum(active)/11)
    assert call_count==600
    print('PASS: transfer hashes, 600 call logs, strict flags/fallback, 200 rankings and full-truth nDCG')


if __name__=='__main__':main()
