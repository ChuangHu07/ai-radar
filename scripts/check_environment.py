"""Cross-platform read-only startup checks. Never prints credentials."""
import importlib.util
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    checks={'os':platform.system(),'python':platform.python_version(),'python_supported':sys.version_info >= (3,12),
            'frontend_built':(ROOT/'frontend/dist/index.html').is_file(),
            'local_configuration_present':(ROOT/'.env').is_file(),
            'dependencies':{name:importlib.util.find_spec(name) is not None for name in ['fastapi','uvicorn','pypdf','httpx','pydantic']}}
    for name in ['node','npm','git']:
        executable=shutil.which(name)
        if executable:
            result=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=15,shell=False)
            checks[name]=result.stdout.strip() if result.returncode==0 else 'version_check_failed'
        else:checks[name]='missing'
    checks['ready']=checks['python_supported'] and checks['frontend_built'] and checks['local_configuration_present'] and all(checks['dependencies'].values())
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    return 0 if checks['ready'] else 1


if __name__=='__main__':raise SystemExit(main())
