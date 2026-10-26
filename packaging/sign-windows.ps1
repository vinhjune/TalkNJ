param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath
)

$ErrorActionPreference = 'Stop'
$FilePath = (Resolve-Path -LiteralPath $FilePath).ProviderPath

# Get-AuthenticodeSignature maps an untrusted root to the generic UnknownError.
# Read WinVerifyTrust's exact result instead of accepting every UnknownError or
# installing a self-signed certificate into the user's trusted root store.
if (-not ('TalkNJ.Authenticode' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace TalkNJ {
    public static class Authenticode {
        public const uint UntrustedRoot = 0x800B0109;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct FileInfo {
            public uint Size;
            [MarshalAs(UnmanagedType.LPWStr)] public string Path;
            public IntPtr File;
            public IntPtr KnownSubject;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct TrustData {
            public uint Size;
            public IntPtr PolicyCallbackData;
            public IntPtr SIPClientData;
            public uint UIChoice;
            public uint RevocationChecks;
            public uint UnionChoice;
            public IntPtr FileInfo;
            public uint StateAction;
            public IntPtr StateData;
            public IntPtr URLReference;
            public uint ProviderFlags;
            public uint UIContext;
            public IntPtr SignatureSettings;
        }

        [DllImport("wintrust.dll", ExactSpelling = true)]
        private static extern uint WinVerifyTrust(IntPtr window, ref Guid action, ref TrustData data);

        public static uint Verify(string path) {
            var file = new FileInfo { Size = (uint)Marshal.SizeOf(typeof(FileInfo)), Path = path };
            IntPtr pointer = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(FileInfo)));
            try {
                Marshal.StructureToPtr(file, pointer, false);
                var data = new TrustData {
                    Size = (uint)Marshal.SizeOf(typeof(TrustData)),
                    UIChoice = 2,         // WTD_UI_NONE
                    UnionChoice = 1,      // WTD_CHOICE_FILE
                    FileInfo = pointer,
                    ProviderFlags = 0x1000 // WTD_CACHE_ONLY_URL_RETRIEVAL; no network requests
                };
                var action = new Guid("00AAC56B-CD44-11D0-8CC2-00C04FC295EE");
                return WinVerifyTrust(new IntPtr(-1), ref action, ref data);
            } finally {
                Marshal.DestroyStructure(pointer, typeof(FileInfo));
                Marshal.FreeHGlobal(pointer);
            }
        }
    }
}
'@
}

$subject = 'CN=TalkNJ'
$friendlyName = 'TalkNJ self-signed code signing'
$now = Get-Date
$certificate = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
    Where-Object {
        $_.Subject -eq $subject -and $_.Issuer -eq $subject -and
        $_.FriendlyName -eq $friendlyName -and $_.HasPrivateKey -and
        $_.NotBefore -le $now -and $_.NotAfter -gt $now.AddDays(1)
    } |
    Sort-Object NotAfter -Descending | Select-Object -First 1

if (-not $certificate) {
    $certificate = New-SelfSignedCertificate -Type CodeSigningCert -Subject $subject `
        -FriendlyName $friendlyName -CertStoreLocation Cert:\CurrentUser\My `
        -HashAlgorithm SHA256 -KeyAlgorithm RSA -KeyLength 3072 `
        -KeyExportPolicy NonExportable -NotAfter $now.AddYears(3)
    Write-Host "Created self-signed code-signing certificate: $($certificate.Thumbprint)"
}

$signature = Set-AuthenticodeSignature -LiteralPath $FilePath `
    -Certificate $certificate -HashAlgorithm SHA256
$verification = [TalkNJ.Authenticode]::Verify($FilePath)
if ($verification -ne 0 -and $verification -ne [TalkNJ.Authenticode]::UntrustedRoot) {
    throw ('Authenticode verification failed for {0}: 0x{1:X8}' -f $FilePath, $verification)
}
$verified = Get-AuthenticodeSignature -LiteralPath $FilePath
if (-not $signature.SignerCertificate -or -not $verified.SignerCertificate -or
    $verified.SignerCertificate.Thumbprint -ne $certificate.Thumbprint) {
    throw "The executable was not signed by the selected TalkNJ certificate: $FilePath"
}

$publicCertificate = Join-Path (Split-Path -Parent $FilePath) 'TalkNJ-signing.cer'
Export-Certificate -Cert $certificate -FilePath $publicCertificate -Type CERT -Force | Out-Null
Write-Host "Signed: $FilePath"
Write-Host "Certificate: $($certificate.Subject), thumbprint $($certificate.Thumbprint), expires $($certificate.NotAfter.ToString('yyyy-MM-dd'))"
if ($verification -eq [TalkNJ.Authenticode]::UntrustedRoot) {
    Write-Host 'Signature integrity verified; the self-signed publisher is not trusted by Windows.'
} else {
    Write-Host 'Signature integrity and Windows certificate trust verified.'
}
Write-Host "Public certificate (no private key): $publicCertificate"
