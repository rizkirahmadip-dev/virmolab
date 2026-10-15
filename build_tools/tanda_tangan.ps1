<#
Tanda tangan Authenticode untuk berkas rilis VirmoLab (VirmoLab.exe, VirmoLab-cli.exe, installer, uninstaller).
Dipanggil build_tools\rilis.py dan oleh Inno Setup (SignTool) lewat rilis.py. Rahasia TIDAK pernah ditulis di
repositori: sertifikat dipilih lewat variabel lingkungan sesi build.

  VIRMOLAB_TANDA_PFX    berkas .pfx/.p12 (sertifikat + kunci privat), atau
  VIRMOLAB_TANDA_SHA1   sidik jari sertifikat di Cert:\CurrentUser\My (kartu pintar / Certum SimplySign)
  VIRMOLAB_TANDA_SANDI  sandi .pfx (opsional)
  VIRMOLAB_TANDA_TSA    server cap waktu RFC 3161 (bawaan http://timestamp.digicert.com)

Cap waktu wajib: tanpanya tanda tangan ikut kedaluwarsa bersama sertifikatnya.
Keluar dengan kode 2 bila tidak ada sertifikat yang diatur, 1 bila penandatanganan gagal.
#>
param([Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Berkas)
$ErrorActionPreference = 'Stop'

$pfx = $env:VIRMOLAB_TANDA_PFX
$sidik = $env:VIRMOLAB_TANDA_SHA1
$sandi = $env:VIRMOLAB_TANDA_SANDI
$tsa = if ($env:VIRMOLAB_TANDA_TSA) { $env:VIRMOLAB_TANDA_TSA } else { 'http://timestamp.digicert.com' }
if (-not $pfx -and -not $sidik) {
    Write-Output 'TANPA_SERTIFIKAT: VIRMOLAB_TANDA_PFX atau VIRMOLAB_TANDA_SHA1 belum diatur.'
    exit 2
}
if ($pfx -and -not (Test-Path -LiteralPath $pfx)) {
    Write-Output "GAGAL: berkas sertifikat tidak ada: $pfx"
    exit 1
}

# signtool dari Windows SDK bila ada (versi terbaru, x64); bila tidak, cmdlet bawaan PowerShell.
$signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
    Sort-Object { [version]($_.Directory.Parent.Name) } -Descending | Select-Object -First 1

foreach ($f in $Berkas) {
    $f = $f.Trim('"')
    if (-not (Test-Path -LiteralPath $f)) { Write-Output "GAGAL: berkas tidak ada: $f"; exit 1 }
    if ($signtool) {
        $arg = @('sign', '/fd', 'sha256', '/tr', $tsa, '/td', 'sha256', '/d', 'VirmoLab',
                 '/du', 'https://github.com/virmolab/virmolab')
        if ($pfx) { $arg += @('/f', $pfx); if ($sandi) { $arg += @('/p', $sandi) } }
        else { $arg += @('/sha1', $sidik) }
        # Cap waktu kadang gagal sesaat (server sibuk); diulang sebelum menyerah.
        $ok = $false
        foreach ($coba in 1..3) {
            & $signtool.FullName @arg $f | Out-Host
            if ($LASTEXITCODE -eq 0) { $ok = $true; break }
            Start-Sleep -Seconds (5 * $coba)
        }
        if (-not $ok) { Write-Output "GAGAL: signtool tidak dapat menandatangani $f"; exit 1 }
    } else {
        if ($pfx) {
            $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($pfx, $sandi)
        } else {
            $cert = Get-Item "Cert:\CurrentUser\My\$sidik"
        }
        $r = Set-AuthenticodeSignature -FilePath $f -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $tsa
        if (-not $r.SignerCertificate) { Write-Output "GAGAL: $f ($($r.StatusMessage))"; exit 1 }
    }
    $s = Get-AuthenticodeSignature -LiteralPath $f
    if (-not $s.SignerCertificate) { Write-Output "GAGAL: tanda tangan tidak terbaca pada $f"; exit 1 }
    $cap = if ($s.TimeStamperCertificate) { 'bercap waktu' } else { 'TANPA cap waktu' }
    Write-Output ("DITANDATANGANI {0} | {1} | {2} | status Windows: {3}" -f
                  (Split-Path $f -Leaf), $s.SignerCertificate.Subject, $cap, $s.Status)
    if (-not $s.TimeStamperCertificate) { Write-Output "GAGAL: cap waktu tidak ada pada $f"; exit 1 }
}
exit 0
