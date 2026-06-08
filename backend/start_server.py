import os
import sys

if __name__ == '__main__':
    backend_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_path)
    sys.path.insert(0, backend_path)
    import uvicorn
    uvicorn.run('server:app', host='0.0.0.0', port=8000)
