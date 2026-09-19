"""Build a scanned source-only release snapshot, never a copy of private Git history.

No network access; findings contain paths/rule names, never matched secret values.
Only tracked, reviewed text files are eligible. Original authority PDFs stay private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {'.py', '.md', '.json', '.toml', '.txt', '.html', '.css', '.js',
                 '.mjs', '.sh', '.ps1', '.yml', '.yaml', '.svg', '.example'}
SPECIAL_NAMES = {'.gitignore', '.gitattributes', '.gitkeep', 'LICENSE', 'NOTICE'}
PRIVATE_ROOTS = ('.codex/', 'docs/official/', 'data/', 'datasets/', 'runs/', 'checkpoints/')
RULES = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'access_token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16})\b'),
    'signed_url': re.compile(r'https?://[^\s<>"\']+[?&](?:X-Amz-Signature|X-Goog-Signature|sig|signature|access_token)=[^\s<>"\']+', re.I),
    'credential_url': re.compile(r'(?:https?|ssh)://[^\s/:]+:[^\s/@]+@[^\s]+', re.I),
    'private_url': re.compile(r'https?://(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|[\w.-]+\.(?:internal|local))(?=[:/\s]|$)', re.I),
    'literal_credential': re.compile(r'''(?im)^\s*["']?(?:password|passwd|api_key|secret_key|access_token)["']?\s*[:=]\s*["']([^"'\r\n]{8,})["']\s*[,;]?\s*$'''),
}


def findings(text):
    found = []
    for rule, pattern in RULES.items():
        for match in pattern.finditer(text):
            if rule == 'literal_credential' and any(marker in match.group(1).lower()
                    for marker in ('<', 'placeholder', 'example', 'test-only', '${')):
                continue
            found.append({'rule': rule, 'line': text.count('\n', 0, match.start()) + 1})
    return found


def eligible(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or any(name.startswith(x) for x in PRIVATE_ROOTS):
        return False
    if p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'):
        return False
    return p.suffix in TEXT_SUFFIXES or p.name in SPECIAL_NAMES


def audit(root=ROOT):
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    files, excluded, issues = {}, [], []
    for name in filter(None, names):
        path = root / name
        if not eligible(name):
            excluded.append(name)
            continue
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            issues.append({'path': name, 'rule': 'missing_or_nonregular_source'})
            continue
        try:
            data = path.read_bytes()
            text = data.decode('utf-8-sig')
        except (OSError, UnicodeError):
            issues.append({'path': name, 'rule': 'unreadable_text'})
            continue
        issues.extend(dict(path=name, **item) for item in findings(text))
        files[name] = hashlib.sha256(data).hexdigest()
    return {'status': 'PASS' if not issues else 'FAIL', 'source_git_sha':
            subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
            'source_clean': not bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root)),
            'scope': 'tracked release-eligible working-tree text; not historical Git objects or excluded authority material',
            'files': files, 'excluded': excluded, 'findings': issues,
            'limitations': ['Pattern scan cannot prove absence of every secret or establish asset rights.',
                           'Private development history contains excluded authority material; never publish it.',
                           'No raw audio/model artifacts or third-party authority PDFs are in this source export.']}


def export_snapshot(report, output, root=ROOT):
    if report['status'] != 'PASS' or not report['source_clean']:
        raise ValueError('release export requires a clean, scanned commit')
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(root.resolve()):
        raise ValueError('choose a new output archive outside the source repository')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, digest in report['files'].items():
            data = (root / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('source changed after audit')
            archive.writestr(name, data)
        archive.writestr('RELEASE_AUDIT.json', json.dumps(report, indent=2) + '\n')
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            assert name != '.git' and not name.startswith('.git/')
            assert name == 'RELEASE_AUDIT.json' or eligible(name)
            assert not findings(archive.read(name).decode('utf-8-sig')), name
    return {'archive': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}


def self_test():
    assert findings('https://' + 'user:secret@host.example/path')[0]['rule'] == 'credential_url'
    assert findings('https://host.example/object?X-Amz-' + 'Signature=abcdef')[0]['rule'] == 'signed_url'
    assert findings('https://' + '192.168.1.9/private')[0]['rule'] == 'private_url'
    assert findings('password = ' + '"not-an-actual-password"')[0]['rule'] == 'literal_credential'
    assert not findings('password = "<supplied-locally>"')
    assert eligible('models/bundle/manifest.json') and eligible('apps/ui/app.js')
    for name in ('../escape.py', '.env', '.env.local', 'docs/official/source.pdf',
                 'data/recording.wav', 'models/weights.pt', '.codex/config.toml'):
        assert not eligible(name), name
    with tempfile.TemporaryDirectory() as directory:
        try:
            export_snapshot({'status':'FAIL', 'source_clean':True}, Path(directory)/'fail.zip')
        except ValueError:
            pass
        else:
            raise AssertionError('unsafe export permitted')
    print('release audit self-tests: PASS')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--export', type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
    report = audit()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('status','source_git_sha','source_clean','findings')}))
    if args.export:
        print(json.dumps(export_snapshot(report, args.export)))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
