import os
import re
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent

patterns = [
    (re.compile(r'(?i)(?:password|secret|passkey|auth_token)\s*[:=]\s*[\'"]?([^\s\'"]{4,})'), 'Credential assignment'),
    (re.compile(r'eyJhbGciOi[A-Za-z0-9_\-\.]+'), 'JWT token'),
    (re.compile(r'postgresql(?:\+[a-z0-9]+)?://[^@\s]+:[^@\s]+@[^\s]+'), 'Postgres URI with user:pass'),
    (re.compile(r'WATT_ADMIN_[A-Za-z0-9_]+'), 'Admin passkey literal'),
]

found = {}
for p in repo_root.rglob('*'):
    if not p.is_file():
        continue
    # Skip ignored dirs
    if any(part in p.parts for part in ['.venv', 'node_modules', '__pycache__', '.git', 'dist', 'postgres_data']):
        continue
    # Check text/doc/config extensions
    if p.suffix.lower() in ['.md', '.txt', '.json', '.yml', '.yaml', '.py', '.js', '.jsx', '.html', '.ini', '.sql']:
        try:
            content = p.read_text(encoding='utf-8', errors='ignore')
            for pat, desc in patterns:
                matches = pat.findall(content)
                if matches:
                    if str(p.relative_to(repo_root)) not in found:
                        found[str(p.relative_to(repo_root))] = []
                    found[str(p.relative_to(repo_root))].append((desc, len(matches), matches[:3]))
        except Exception as e:
            pass

print(f"Total files with pattern matches: {len(found)}")
for f_path, issues in sorted(found.items()):
    print(f"\n--- {f_path} ---")
    for desc, count, samples in issues:
        # Mask samples so we don't leak anything in output
        masked = [str(s)[:4] + '***' if len(str(s)) > 4 else '***' for s in samples]
        print(f"  {desc} ({count} occurrences): {masked}")
