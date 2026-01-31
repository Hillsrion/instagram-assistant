import subprocess
import sys
import platform

def open_folder_dialog(initial_dir=None):
    """
    Opens a native folder selection dialog on the host machine.
    Returns the selected absolute path or None if cancelled.
    """
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            # Use AppleScript for a native look
            script = """
            try
                set folderPath to POSIX path of (choose folder with prompt "Select Instagram Export Folder")
                return folderPath
            on error
                return ""
            end try
            """
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            path = result.stdout.strip()
            return path if path else None
            
        elif system == "Windows":
            # Use PowerShell for Windows (modern folder picker)
            ps_script = """
            Add-Type -AssemblyName System.Windows.Forms
            $f = New-Object System.Windows.Forms.FolderBrowserDialog
            $f.ShowDialog() | Out-Null
            $f.SelectedPath
            """
            result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True)
            path = result.stdout.strip()
            return path if path else None
            
        else: # Linux / Fallback
            # Try Zenity or Kdialog if available, otherwise try tkinter
            try:
                import tkinter
                from tkinter import filedialog
                root = tkinter.Tk()
                root.withdraw() # Hide main window
                root.attributes('-topmost', True) # Bring to front
                path = filedialog.askdirectory(title="Select Instagram Export Folder")
                root.destroy()
                return path if path else None
            except:
                return None
                
    except Exception as e:
        print(f"Error opening dialog: {e}")
        return None
