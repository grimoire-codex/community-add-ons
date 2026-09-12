#!/usr/bin/env python3
import sys
import re

def bump_patch_version(path):
    with open(path, 'r') as f:
        content = f.read()
        
    def repl(m):
        major, minor, patch = m.groups()
        return f'version: {major}.{minor}.{int(patch)+1}'
        
    new_content = re.sub(r'version:\s*(\d+)\.(\d+)\.(\d+)', repl, content)
    
    with open(path, 'w') as f:
        f.write(new_content)
        print(f"Bumped patch version in {path}")

if __name__ == '__main__':
    for path in sys.argv[1:]:
        bump_patch_version(path)
