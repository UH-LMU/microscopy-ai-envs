@echo off
rem Windows activation for all envs (pixi runs this in cmd.exe).
rem
rem numba (cache=True, e.g. in cellpose.dynamics) checks whether it can write
rem its cache to site-packages\...\__pycache__. On Windows, when that folder
rem exists but is read-only via ACLs (fix-perms-ro), tempfile retries new
rem names up to TMP_MAX times instead of failing, so imports hang for regular
rem users. A user-writable NUMBA_CACHE_DIR makes numba skip that check.
if not defined NUMBA_CACHE_DIR set "NUMBA_CACHE_DIR=%LOCALAPPDATA%\numba-cache"
