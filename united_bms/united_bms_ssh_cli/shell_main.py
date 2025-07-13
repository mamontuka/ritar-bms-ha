#!/usr/bin/env python3
import sys
import os
import yaml
import subprocess
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter

CONFIG_PATH = '/home/debug/debug_config.yaml'
CUSTOM_PATH = '/home/debug/custom'
USER_VISIBLE_PATH = '/config/united_bms'  # Path mapped to Home Assistant's host config

class Colors:
    RESET = '\033[0m'
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'

def print_help():
    print(f"""{Colors.CYAN}
United BMS Shell - Available commands:

  password                     - Change debug user password
  
  config debug                 - Configure debugger connection
  config print                 - List custom override files
  config edit <filename>       - Edit custom override file
  
  read <slave> <block> <count> - Run BMS CLI register(s) read command 
  
  help, ?                      - Show this help
  exit                         - Exit the shell
{Colors.RESET}""")

def load_config():
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            try:
                return yaml.safe_load(f)
            except Exception:
                print(f"{Colors.YELLOW}Warning: Config file corrupted. Reconfiguring.{Colors.RESET}")
                return None
    return None

def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        yaml.safe_dump(cfg, f)

def prompt_config():
    session = PromptSession()
    print(f"{Colors.CYAN}Configuring BMS debugger connection. Press Enter to accept defaults.{Colors.RESET}")

    conn_type = session.prompt("Connection type (tcp/serial) [tcp]: ").strip().lower()
    if conn_type not in ('tcp', 'serial'):
        conn_type = 'tcp'

    if conn_type == 'tcp':
        conn_address = session.prompt("TCP address (ip:port) [192.168.0.100:50500]: ").strip()
        if not conn_address:
            conn_address = '192.168.0.100:50500'
    else:
        conn_address = session.prompt("Serial port [/dev/ttyUSB0]: ").strip()
        if not conn_address:
            conn_address = '/dev/ttyUSB0'

    while True:
        slave_count = session.prompt("Number of batteries (slave count) [1]: ").strip()
        if not slave_count:
            slave_count = '1'
        if slave_count.isdigit() and int(slave_count) > 0:
            slave_count = int(slave_count)
            break
        else:
            print(f"{Colors.RED}Please enter a positive integer.{Colors.RESET}")

    config = {
        'connection_type': conn_type,
        'connection_address': conn_address,
        'slave_count': slave_count,
        'register_map': 'default'
    }

    container_map = '/home/debug/register_map.yaml'
    target_map = os.path.join(USER_VISIBLE_PATH, 'register_map.yaml')

    try:
        subprocess.run(['sudo', 'mkdir', '-p', USER_VISIBLE_PATH], check=True)
        if not os.path.exists(target_map):
            subprocess.run(['sudo', 'cp', container_map, target_map], check=True)
            print(f"{Colors.GREEN}register_map.yaml copied to {USER_VISIBLE_PATH}{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}Failed to prepare {USER_VISIBLE_PATH} or copy map: {e}{Colors.RESET}")

    save_config(config)
    print(f"{Colors.GREEN}BMS debugger connection saved.{Colors.RESET}")
    return config

def run_read_command(config, args):
    if len(args) < 3:
        print(f"{Colors.YELLOW}Usage: read <slave> <block> <count>{Colors.RESET}")
        return

    slave, read_block, count = args[:3]

    if slave.lower() == 'print':
        print(f"{Colors.YELLOW}Usage: read <slave> <block> <count>{Colors.RESET}")
        return

    cli_args = ['debug']
    if config['connection_type'] == 'tcp':
        cli_args += ['--tcp', config['connection_address']]
    else:
        cli_args += ['--serial', config['connection_address']]

    cli_args += ['--slave', slave, '--read', read_block, '--count', count]

    print(f"{Colors.GREEN}Running: {' '.join(cli_args)}{Colors.RESET}")
    subprocess.run(['python3', '/united_bms_core/cli.py'] + cli_args[1:])

def list_override_files():
    if not os.path.isdir(CUSTOM_PATH):
        print(f"{Colors.YELLOW}No files found in {USER_VISIBLE_PATH}{Colors.RESET}")
        return

    files = [
        f for f in os.listdir(CUSTOM_PATH)
        if os.path.isfile(os.path.join(CUSTOM_PATH, f)) and f.endswith(('.py', '.yaml', '.yml'))
    ]

    if not files:
        print(f"{Colors.YELLOW}No .py or .yaml override files found in {USER_VISIBLE_PATH}{Colors.RESET}")
    else:
        print(f"{Colors.GREEN}Available override files in {USER_VISIBLE_PATH}:{Colors.RESET}")
        for f in files:
            print("  ", f)

def edit_override_file(filename):
    filepath = os.path.join(CUSTOM_PATH, filename)
    if not os.path.isfile(filepath):
        print(f"{Colors.RED}File not found or not a file: {filename}{Colors.RESET}")
        return
    if not filename.endswith(('.py', '.yaml', '.yml')):
        print(f"{Colors.RED}Editing of this file type is not allowed: {filename}{Colors.RESET}")
        return
    try:
        subprocess.run(['sudo', 'nano', filepath])
    except Exception as e:
        print(f"{Colors.RED}Failed to edit file: {e}{Colors.RESET}")

def change_debug_password():
    session = PromptSession()
    print(f"{Colors.CYAN}Change debug user password{Colors.RESET}")
    while True:
        pwd1 = session.prompt("Enter new password: ", is_password=True)
        pwd2 = session.prompt("Confirm new password: ", is_password=True)
        if pwd1 != pwd2:
            print(f"{Colors.RED}Passwords do not match. Try again.{Colors.RESET}")
        elif not pwd1:
            print(f"{Colors.RED}Password cannot be empty. Try again.{Colors.RESET}")
        else:
            break
    try:
        subprocess.run(['sudo', 'chpasswd'], input=f"debug:{pwd1}".encode(), check=True)
        print(f"{Colors.GREEN}Password changed successfully.{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}Failed to change password: {e}{Colors.RESET}")

def main():
    config = load_config()
    session = PromptSession()
    completer = NestedCompleter.from_nested_dict({
        'help': None,
        '?': None,
        'exit': None,
        'password': None,
        'read': None,
        'config': {
            'debug': None,
            'print': None,
            'edit': {
                f: None for f in os.listdir(CUSTOM_PATH)
                if f.endswith(('.py', '.yaml', '.yml'))
            } if os.path.isdir(CUSTOM_PATH) else {}
        }
    })

    print_help()

    while True:
        try:
            line = session.prompt('united-bms> ', completer=completer).strip()
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd in ('help', '?'):
                print_help()
            elif cmd == 'exit':
                print("Bye!")
                sys.exit(0)
            elif cmd == 'password':
                change_debug_password()
            elif cmd == 'config':
                if not args:
                    print(f"{Colors.YELLOW}Usage: config debug|print|edit <file>{Colors.RESET}")
                    continue
                subcmd = args[0].lower()
                if subcmd == 'debug':
                    config = prompt_config()
                elif subcmd == 'print':
                    list_override_files()
                elif subcmd == 'edit':
                    if len(args) < 2:
                        print("Usage: config edit <filename>")
                    else:
                        edit_override_file(args[1])
                else:
                    print(f"{Colors.RED}Unknown config option: {subcmd}{Colors.RESET}")
            elif cmd == 'read':
                if not config:
                    print(f"{Colors.YELLOW}Debugger connection not configured yet. Please configure now.{Colors.RESET}")
                    config = prompt_config()
                run_read_command(config, args)
            else:
                print(f"{Colors.RED}Unknown command: {cmd}{Colors.RESET}")

        except KeyboardInterrupt:
            print(f"{Colors.YELLOW}\n[Cancelled] Press Ctrl+D or type 'exit' to quit.{Colors.RESET}")
            continue
        except EOFError:
            print("\nExiting shell.")
            break
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.RESET}")

if __name__ == "__main__":
    main()
