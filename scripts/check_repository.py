"""Read-only heuristic scan of tracked and commit-eligible files; never prints values."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'provider/API token': re.compile(r'\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential in URL (review default/placeholder)': re.compile(r'[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/:]+:[^\s/@]+@'),
    'secret assignment (review default/fixture)': re.compile(r'''(?i)(?:api_key|api_secret|access_token|password|pgpassword)\s*["']?\s*[:=]\s*["'][^"'\r\n]{4,}["']'''),
    'private/signed URL (review)': re.compile(r'https?://[^\s"<>]+(?:[?&](?:token|key|sig|signature|X-Amz-Signature)=|\.internal\b|\.local\b)', re.I),
}

def main():
    result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT, check=True, capture_output=True)
    paths = sorted(set(result.stdout.decode().split('\0')) - {''})
    findings = []; large = []; total = 0
    for name in paths:
        path = ROOT / name
        if not path.is_file(): continue
        size = path.stat().st_size; total += size
        if size >= 50 * 1024 * 1024: large.append({'file': name, 'bytes': size})
        # Text source/config/artifacts only, not binary assets or dependencies.
        raw = path.read_bytes()
        if b'\0' in raw: continue
        try: contents = raw.decode('utf-8-sig')
        except UnicodeDecodeError: continue
        for number, line in enumerate(contents.splitlines(), 1):
            for label, rule in RULES.items():
                if rule.search(line): findings.append({'file': name, 'line': number, 'category': label})
    import json
    print(json.dumps({'candidate_files':len(paths), 'total_bytes':total,
                      'large_files_50MiB_or_more':large, 'review_findings':findings}, indent=2))

if __name__ == '__main__': main()
