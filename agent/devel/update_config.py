#!/usr/bin/env python3
"""Update agent configuration with name and connector."""
import sys
import re

def main():
    if len(sys.argv) != 5:
        print("Usage: update_config.py <connector> <name> <server_url> <config>")
        sys.exit(1)
    
    connector = sys.argv[1]
    name = sys.argv[2]
    server_url = sys.argv[3]
    config_file = sys.argv[4]
    
    with open(config_file) as f:
        content = f.read()
    
    content = re.sub(r'agent_id:.*', f'agent_id: {name}', content)
    content = re.sub(r'server_address:.*', f'server_address: {server_url}', content)
    content = re.sub(r'/tmp/testflinger/[^/]+/', f'/tmp/testflinger/{name}/', content)
    content = re.sub(r'^  - .*$', f'  - {name}', content, flags=re.MULTILINE)
    content = re.sub(r'provision_type:.*', f'provision_type: {connector}', content)
    
    with open(config_file, 'w') as f:
        f.write(content)

if __name__ == '__main__':
    main()
