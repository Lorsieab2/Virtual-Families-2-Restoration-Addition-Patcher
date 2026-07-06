using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class VF2PatcherLauncher
{
    private static string Quote(string value)
    {
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }

    private static bool TryStart(string exe, string args, string workDir)
    {
        try
        {
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = exe;
            info.Arguments = args;
            info.WorkingDirectory = workDir;
            info.UseShellExecute = false;
            Process.Start(info);
            return true;
        }
        catch
        {
            return false;
        }
    }

    [STAThread]
    private static int Main()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string manifest = Path.Combine(dir, "manifest.json");
        string gui = Path.Combine(dir, "offline_vf2_patcher_gui.py");
        if (!File.Exists(manifest))
        {
            MessageBox.Show("manifest.json was not found next to the patcher EXE.", "Virtual Families 2 Restoration/Addition Patcher");
            return 2;
        }
        if (!File.Exists(gui))
        {
            MessageBox.Show("offline_vf2_patcher_gui.py was not found next to the patcher EXE.", "Virtual Families 2 Restoration/Addition Patcher");
            return 2;
        }
        string args = "-3 " + Quote(gui) + " " + Quote(manifest);
        if (TryStart("pyw", args, dir) || TryStart("py", args, dir))
            return 0;
        args = Quote(gui) + " " + Quote(manifest);
        if (TryStart("pythonw", args, dir) || TryStart("python", args, dir))
            return 0;
        MessageBox.Show(
            "Python 3 was not found. Install Python 3 or run Launch_GUI.bat from this folder.",
            "Virtual Families 2 Restoration/Addition Patcher");
        return 1;
    }
}
