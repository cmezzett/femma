set femmadir=c:\femma
set pythonbin=c:\python25\python.exe 
set fedmetadata=https://www.idem.garr.it/docs/conf/signed-metadata.xml

set powershell=c:\windows\system32\windowspowershell\v1.0\powershell.exe
set pshscript=.\update_adfs_rptrust.ps1

cd %femmadir%
%pythonbin% femma.py -m %fedmetadata%
%powershell% -ExecutionPolicy Unrestricted -File %pshscript%
%pythonbin% femma.py -c
