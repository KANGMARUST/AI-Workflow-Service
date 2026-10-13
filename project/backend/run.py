from pathlib import Path
import os,sys
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE / '.packages'))
sys.path.insert(0,str(BASE))
if __name__=='__main__':
    import uvicorn
    uvicorn.run('app:app',host=os.getenv('HOST','127.0.0.1'),port=int(os.getenv('PORT','8000')))
