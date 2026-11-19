' Lanzador silencioso de WALL-E - Centro de Comando.
' Abre la cabina sin ventana negra: usa el pythonw del .venv si existe.
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = base

venv_pyw = base & "\.venv\Scripts\pythonw.exe"
venv_py  = base & "\.venv\Scripts\python.exe"

If fso.FileExists(venv_pyw) Then
    shell.Run """" & venv_pyw & """ """ & base & "\launcher.py""", 0, False
ElseIf fso.FileExists(venv_py) Then
    shell.Run """" & venv_py & """ """ & base & "\launcher.py""", 0, False
Else
    On Error Resume Next
    shell.Run "pythonw.exe """ & base & "\launcher.py""", 0, False
    If Err.Number <> 0 Then
        Err.Clear
        shell.Run "python.exe """ & base & "\launcher.py""", 0, False
    End If
    On Error GoTo 0
End If
