@echo off
REM OpenLaoKe - Build and upload to PyPI (Windows)
setlocal enabledelayedexpansion

echo === OpenLaoKe PyPI Upload ===

echo [1/5] Bumping patch version...
python -c "import re; p='openlaoke/__init__.py'; t=open(p,encoding='utf-8').read(); m=re.search(r'(__version__\s*=\s*\"(\d+\.\d+\.)(\d+)\")', t); old_v=m.group(2)+m.group(3); new_v=m.group(2)+str(int(m.group(3))+1); open(p,'w',encoding='utf-8').write(t.replace(m.group(1), '__version__ = \"' + new_v + '\"')); print(f'  {old_v} -^> {new_v}')"

echo [2/5] Cleaning old builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist openlaoke.egg-info rmdir /s /q openlaoke.egg-info

echo [3/5] Installing build tools...
python -m pip install --upgrade build twine -q

echo [4/5] Building package...
python -m build
python -m twine check dist\*

echo [5/5] Uploading to PyPI...
python -m twine upload dist\*

echo === Done! ===
