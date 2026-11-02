# Reset permissions inside pixi envs so they inherit from the env folder.
#
# After `pixi install` on Windows, files in .pixi\envs\<env> can carry
# explicit ACLs that lock out other users (e.g. python.exe fails for regular
# users after `pixi shell`). This does the same as Explorer's Properties >
# Security > Advanced > "Replace all child object permission entries with
# inheritable permission entries from this object" on each env folder.
# The env folders' own permissions are left as they are.
#
#   scripts\fix-env-permissions.ps1                 # all envs
#   scripts\fix-env-permissions.ps1 cellpose4 stardist-full
#   pixi run fix-perms [env ...]
#
# Run it as the user who installed the envs (or as admin), and re-run after
# every `pixi install` / `pixi update`, since new files get the same ACLs.

param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$EnvName
)

$ErrorActionPreference = "Stop"
$envsDir = Join-Path $PSScriptRoot "..\.pixi\envs" | Resolve-Path

if ($EnvName) {
  $envDirs = foreach ($name in $EnvName) {
    $dir = Join-Path $envsDir $name
    if (-not (Test-Path $dir -PathType Container)) {
      throw "no env '$name' in $envsDir"
    }
    Get-Item $dir
  }
} else {
  $envDirs = Get-ChildItem $envsDir -Directory
}

$failed = 0
foreach ($dir in $envDirs) {
  Write-Host "== $($dir.Name)"
  # /reset: replace explicit ACLs with inherited ones; /T: recurse;
  # /C: continue on errors; /Q: only print the summary line.
  icacls "$($dir.FullName)\*" /reset /T /C /Q
  if ($LASTEXITCODE -ne 0) { $failed++ }
}

if ($failed) {
  Write-Host "$failed env(s) had files whose permissions could not be reset" -ForegroundColor Red
  exit 1
}
