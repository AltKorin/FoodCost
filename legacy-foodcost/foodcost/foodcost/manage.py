#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Wczytaj .env bez zewnętrznych zależności
env_file = Path(__file__).resolve().parent / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ.setdefault(key.strip(), val.strip())

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodcost_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django nie jest zainstalowane.") from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
