# Give regular users read + execute access to the pixi envs, and nothing more.
#
# Just resetting the env files to inherit from their folders (Explorer's
# "Replace all child object permission entries...") only works if the folders
# grant the right things, and the easy way to get there in Explorer (Users
# Full Control) lets every user change or delete the envs. This script sets
# the permissions itself:
#
#   .pixi\envs   inheritance off. The inherited entries are kept as explicit
#                entries (SYSTEM, Administrators, owner, ...). Then all grants
#                to Users, Authenticated Users and Everyone are removed, and
#                these entries are added:
#                  Users          (OI)(CI)RX   read + execute, inherited down
#                  <you>          (OI)(CI)F    so you can still install/update
#   <env>\...    the explicit ACLs are reset, so the folders and files inherit
#                the entries above. This also clears any Full Control that was
#                set on the env folders themselves.
#
# Groups are given by SID, not by name, so the script also works on
# Windows installs in other languages (where Users is called e.g. "Käyttäjät").
# BUILTIN\Users (S-1-5-32-545) is a local group. By default its members include
# NT AUTHORITY\Authenticated Users and INTERACTIVE, and on domain-joined
# machines also Domain Users, so granting Users covers every user who can log
# in. Pass -AuthenticatedUsers to also grant Authenticated Users (S-1-5-11)
# directly, for machines where someone has removed it from Users.
#
#   scripts\fix-env-permissions.ps1                         # all envs
#   scripts\fix-env-permissions.ps1 cellpose4 stardist-full
#   scripts\fix-env-permissions.ps1 -AuthenticatedUsers
#   pixi run fix-perms [env ...]
#
# Run it from an elevated PowerShell (as admin). Re-run it after every
# `pixi install` / `pixi update`. Most env files are hardlinks into the
# installer's rattler cache and keep that cache's ACL, so they don't inherit
# from .pixi\envs on their own.

param(
  [switch]$AuthenticatedUsers,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$EnvName
)

$ErrorActionPreference = "Stop"

$SID_USERS      = "S-1-5-32-545"
$SID_AUTH_USERS = "S-1-5-11"
$SID_EVERYONE   = "S-1-1-0"
$me = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value

$repoDir = Join-Path $PSScriptRoot ".." | Resolve-Path
$envsDir = Join-Path $repoDir ".pixi\envs" | Resolve-Path

function Invoke-Icacls {
  & icacls @args
  if ($LASTEXITCODE -ne 0) { throw "icacls $($args -join ' ') failed ($LASTEXITCODE)" }
}

# ---- 1. .pixi\envs: explicit, minimal ACL --------------------------------
Write-Host "== $envsDir"
$readers = @($SID_USERS)
if ($AuthenticatedUsers) { $readers += $SID_AUTH_USERS }

Invoke-Icacls "$envsDir" /inheritance:d /Q
Invoke-Icacls "$envsDir" /remove:g "*$SID_USERS" "*$SID_AUTH_USERS" "*$SID_EVERYONE" /Q
foreach ($sid in $readers) {
  Invoke-Icacls "$envsDir" /grant "*${sid}:(OI)(CI)RX" /Q
}
Invoke-Icacls "$envsDir" /grant "*${me}:(OI)(CI)F" /Q

# ---- 2. envs: drop explicit ACLs, inherit from .pixi\envs -----------------
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
  # The env folder itself, then everything below it.
  # /T: recurse; /C: continue on errors; /Q: only print the summary line.
  icacls "$($dir.FullName)" /reset /C /Q
  if ($LASTEXITCODE -ne 0) { $failed++; continue }
  icacls "$($dir.FullName)\*" /reset /T /C /Q
  if ($LASTEXITCODE -ne 0) { $failed++ }
}

# ---- 3. checks -----------------------------------------------------------
$broad = @($SID_USERS, $SID_AUTH_USERS, $SID_EVERYONE)
$writeRights = [Security.AccessControl.FileSystemRights]"Write, Delete, ChangePermissions, TakeOwnership"

function Get-BroadAces($path) {
  # Ask for SIDs directly: no name lookups, no failures on orphaned SIDs.
  (Get-Acl -LiteralPath $path).GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]) |
    Where-Object { $_.AccessControlType -eq "Allow" -and $broad -contains $_.IdentityReference.Value }
}

# Regular users still need to read pixi.toml / pixi.lock and open .pixi
# to use `pixi shell` / `pixi run`. Warn if no broad group can do that.
foreach ($p in @($repoDir, (Join-Path $repoDir ".pixi"))) {
  $canRead = Get-BroadAces $p | Where-Object {
    ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadAndExecute) -eq
      [Security.AccessControl.FileSystemRights]::ReadAndExecute
  }
  if (-not $canRead) {
    Write-Host "warning: Users have no read access to $p" -ForegroundColor Yellow
  }
}

# Spot check: python.exe in each env should give broad groups no write access.
foreach ($dir in $envDirs) {
  $py = Join-Path $dir.FullName "python.exe"
  if (-not (Test-Path $py)) { continue }
  $w = Get-BroadAces $py | Where-Object { $_.FileSystemRights -band $writeRights }
  if ($w) {
    Write-Host "warning: $py is still writable by $($w.IdentityReference -join ', ')" -ForegroundColor Yellow
    $failed++
  }
}

if ($failed) {
  Write-Host "$failed problem(s); see above" -ForegroundColor Red
  exit 1
}
