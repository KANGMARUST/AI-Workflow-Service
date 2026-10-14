"""Authorized developer test only. Never imported by the web server."""
import json,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend/.packages'));sys.path.insert(0,str(ROOT/'backend'))
from user_agent import AgentSettings,run_agent,AgentError
KEY_FILE=ROOT.parent/'SaveAPI.md'
def test_key():
    text=KEY_FILE.read_text(encoding='utf-8-sig')
    matches=re.findall(r'\bup_[A-Za-z0-9_-]{16,}\b',text)
    if len(set(matches))!=1:raise RuntimeError('테스트용 Upstage 키를 하나로 식별할 수 없습니다. 키 값은 출력하지 않았습니다.')
    return matches[0]
if __name__=='__main__':
    agent=sys.argv[1];path=Path(sys.argv[2]);out=Path(sys.argv[3]);start=time.monotonic()
    try:
        result,metadata=run_agent(path,AgentSettings(test_key(),agent),timeout=240)
        out.write_text(json.dumps(dict(ok=True,elapsed_seconds=round(time.monotonic()-start,2),result=result,metadata=metadata),ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(ok=True,elapsed_seconds=round(time.monotonic()-start,2),fields=list(result),metadata=metadata),ensure_ascii=False))
    except (AgentError,RuntimeError) as error:
        out.write_text(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False,indent=2),encoding='utf-8');print(str(error));sys.exit(1)
