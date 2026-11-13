' InfoFilter launcher - double click to run, no console window.
' Prefers the packaged single-file exe; falls back to local Python.
' ASCII only on purpose: .vbs files are read as ANSI by Windows Script Host.

Option Explicit
Dim sh, fso, dirPath, exePath, f

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dirPath = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dirPath

' 1) use the packaged exe if present
exePath = ""
For Each f In fso.GetFolder(dirPath).Files
  If LCase(fso.GetExtensionName(f.Name)) = "exe" Then
    exePath = f.Path
  End If
Next

If exePath <> "" Then
  sh.Run """" & exePath & """", 0, False
  WScript.Quit 0
End If

' 2) fall back to source mode with a windowless interpreter
On Error Resume Next
sh.Run "pyw app.py", 0, False
If Err.Number <> 0 Then
  Err.Clear
  sh.Run "pythonw app.py", 0, False
End If
If Err.Number <> 0 Then
  MsgBox "Python not found, and there is no packaged .exe in this folder." & vbCrLf & vbCrLf & _
         "Install Python 3.9+ and check 'Add python.exe to PATH'," & vbCrLf & _
         "or just double-click the .exe file.", 48, "InfoFilter"
End If
On Error Goto 0
