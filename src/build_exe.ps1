# 打包「月谕圣牌导出器.exe」
# 用法（在仓库根目录或 src 目录均可）：
#   pwsh -File src\build_exe.ps1
# 依赖： pip install pyinstaller segno
# 产物： src\dist\月谕圣牌导出器.exe （单文件、无控制台窗口）
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

$pyiArgs = @(
  '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
  '--log-level', 'WARN',
  '--name', '月谕圣牌导出器',
  '--exclude-module', 'numpy', '--exclude-module', 'pandas',
  '--exclude-module', 'matplotlib', '--exclude-module', 'scipy',
  '--exclude-module', 'PIL', '--exclude-module', 'PyQt5',
  '--exclude-module', 'PySide2', '--exclude-module', 'IPython',
  '--exclude-module', 'notebook', '--exclude-module', 'sqlalchemy',
  '--exclude-module', 'sympy', '--exclude-module', 'numba',
  'yysp_gui.py'
)

& python @pyiArgs
$code = $LASTEXITCODE
if ($code -ne 0) { throw "PyInstaller 退出码 $code，构建失败" }

$exe = Join-Path $PSScriptRoot 'dist\月谕圣牌导出器.exe'
if (-not (Test-Path $exe)) { throw '构建失败：未找到 dist\月谕圣牌导出器.exe' }
$f = Get-Item $exe
Write-Host ("构建成功：{0}  ({1:N1} MB)" -f $f.FullName, ($f.Length / 1MB))
