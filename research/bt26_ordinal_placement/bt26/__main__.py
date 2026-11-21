import argparse,json,sys
from pathlib import Path
from . import make_model,search

def main():
    p=argparse.ArgumentParser(description='Research ordinal placement; times in seconds')
    p.add_argument('problem',type=Path);p.add_argument('--forecast',type=Path)
    p.add_argument('--method',choices=['P','B','D'],default='P')
    p.add_argument('--max-checks',type=int);p.add_argument('--max-expansions',type=int);p.add_argument('--max-seconds',type=float)
    p.add_argument('--no-early-stop',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        m=make_model(json.loads(a.problem.read_text(encoding='utf-8')))
        f=json.loads(a.forecast.read_text(encoding='utf-8')) if a.forecast else None
        r=search(m,f,a.method,max_checks=a.max_checks,max_expansions=a.max_expansions,max_seconds=a.max_seconds,early_stop=not a.no_early_stop)
        text=json.dumps(r.to_dict(),ensure_ascii=False,indent=2)
        if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text+'\n',encoding='utf-8')
        else:print(text)
        return 0 if r.plan else 2
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'INVALID_INPUT','error':str(exc)},ensure_ascii=False),file=sys.stderr);return 3
if __name__=='__main__':sys.exit(main())
