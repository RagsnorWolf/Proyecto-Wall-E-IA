' Lanzador silencioso de WALL-E · Centro de Comando
' Abre la cabina sin ventana negra y sin consola visible.
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = base

' Buscar pythonw o python
pythonw = "pythonw.exe"
python = "python.exe"

On Error Resume Next
shell.Run pythonw & " """ & base & "\launcher.py""", 0, False
If Err.Number <> 0 Then
    Err.Clear
    shell.Run python & " """ & base & "\launcher.py""", 0, False
End If
On Error GoTo 0
