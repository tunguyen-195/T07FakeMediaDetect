import re

with open('templates/pdf.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix all split {{ res.confidence }} patterns
# Pattern: {{ followed by whitespace (including newlines) then res.confidence then whitespace then }}
content = re.sub(
    r'\{\{\s*res\.confidence\s*\}\}',
    '{{ res.confidence }}',
    content,
    flags=re.DOTALL
)

with open('templates/pdf.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed!')

# Verify
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'res.confidence' in line:
        print(f'Line {i+1}: {line.strip()[:80]}')
