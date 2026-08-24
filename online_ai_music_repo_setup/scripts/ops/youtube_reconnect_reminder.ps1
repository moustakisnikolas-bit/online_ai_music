# AION -- YouTube reconnect reminder.
#
# Runs every 7 days via Windows Task Scheduler. Shows a real popup with a
# "Reconnect YouTube Now" button carrying the actual live OAuth
# authorization URL (fetched fresh from the local API each time, since
# the URL includes a one-time state token). Stays silent once the upload
# backlog is empty -- see queue_remaining_count.py.
#
# Why this exists: the app's Google OAuth consent screen is in Testing
# mode, which hard-expires refresh tokens after 7 days regardless of use
# (see scripts/ops/README.md). Moving it to Production removes the need
# for this reminder entirely.

$ErrorActionPreference = "Stop"
$repoRoot = "C:\online-music-creation\online_ai_music\online_ai_music_repo_setup"
$python = "$repoRoot\.venv-windows\Scripts\python.exe"

# Skip entirely once nothing is left to upload -- "until I upload all the
# songs" per the original request. -1 (unknown, e.g. DB unreachable)
# still shows the reminder rather than risk silently going stale.
$remaining = -1
try {
    $output = & $python "$repoRoot\scripts\ops\queue_remaining_count.py" 2>$null
    $remaining = [int]($output | Select-Object -Last 1)
} catch {
    $remaining = -1
}

if ($remaining -eq 0) {
    exit 0
}

# Fetch a fresh real authorization URL -- it embeds a single-use state
# token, so a stale cached URL wouldn't reliably work.
$authUrl = $null
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/v1/publishing/youtube/authorize" -TimeoutSec 5
    $authUrl = $resp.authorization_url
} catch {
    $authUrl = $null
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "AION -- YouTube reconnect reminder"
$form.Size = New-Object System.Drawing.Size(440, 190)
$form.StartPosition = "CenterScreen"
$form.TopMost = $true
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$label = New-Object System.Windows.Forms.Label
if ($remaining -ge 0) {
    $queueText = "$remaining song(s) still waiting to upload."
} else {
    $queueText = "Couldn't check the queue -- make sure AION's API server is running."
}
$label.Text = "It's been 7 days since the last YouTube reconnect.`nThe connection may have expired.`n`n$queueText"
$label.SetBounds(15, 15, 400, 65)
$form.Controls.Add($label)

$reconnectButton = New-Object System.Windows.Forms.Button
$reconnectButton.Text = "Reconnect YouTube Now"
$reconnectButton.SetBounds(15, 95, 190, 35)
$reconnectButton.Add_Click({
    if ($authUrl) {
        Start-Process $authUrl
    } else {
        Start-Process "http://127.0.0.1:8010/"
    }
    $form.Close()
})
$form.Controls.Add($reconnectButton)

$dismissButton = New-Object System.Windows.Forms.Button
$dismissButton.Text = "Remind me in 7 days"
$dismissButton.SetBounds(220, 95, 170, 35)
$dismissButton.Add_Click({ $form.Close() })
$form.Controls.Add($dismissButton)

$form.Add_Shown({ $form.Activate() })
[void]$form.ShowDialog()
