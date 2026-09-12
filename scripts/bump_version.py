#!/usr/bin/env python3
import sys
import re
import argparse

def bump_version(path, bump_type):
    with open(path, 'r') as f:
        content = f.read()
        
    def repl(m):
        major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        else:
            patch += 1
            
        return f'version: {major}.{minor}.{patch}'
        
    new_content = re.sub(r'^version:\s*(\d+)\.(\d+)\.(\d+)', repl, content, flags=re.MULTILINE)
    
    with open(path, 'w') as f:
        f.write(new_content)
        print(f"Bumped {bump_type} version in {path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Bump semantic versions in YAML files.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--major', action='store_const', dest='bump_type', const='major', help='Bump major version')
    group.add_argument('--minor', action='store_const', dest='bump_type', const='minor', help='Bump minor version')
    group.add_argument('--patch', action='store_const', dest='bump_type', const='patch', help='Bump patch version')
    
    parser.add_argument('files', nargs='+', help='Paths to the YAML files to bump')
    
    parser.set_defaults(bump_type='patch')
    
    args = parser.parse_args()
    
    for path in args.files:
        bump_version(path, args.bump_type)
