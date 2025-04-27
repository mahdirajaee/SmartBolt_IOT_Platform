#!/usr/bin/env python3

import socket
import os
import sys
import subprocess
import signal
import platform
import argparse
import time
import threading
import select

def check_port_in_use(port):
    """Check if a port is in use by attempting to bind to it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('', port))
            return False
        except socket.error:
            return True

def find_process_using_port(port):
    """Find the process ID using the specified port."""
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True)
            lines = output.decode().strip().split('\n')
            if lines:
                for line in lines:
                    if f":{port}" in line:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            return pid
        except subprocess.CalledProcessError:
            return None
    else:
        try:
            # For Linux/Mac
            cmd = f"lsof -i :{port} -t"
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            # lsof might return multiple PIDs - take the first one
            pids = output.split('\n')
            if pids and pids[0]:
                return pids[0]
        except subprocess.CalledProcessError:
            return None
    return None

def kill_process(pid):
    """Kill the process with the specified PID."""
    try:
        if platform.system() == "Windows":
            subprocess.check_call(f"taskkill /F /PID {pid}", shell=True)
        else:
            os.kill(int(pid), signal.SIGTERM)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False

def get_process_name(pid):
    """Get the name of the process with the specified PID."""
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output(f"tasklist /FI \"PID eq {pid}\"", shell=True)
            lines = output.decode().strip().split('\n')
            if len(lines) >= 2:
                return lines[2].split()[0]
        else:
            output = subprocess.check_output(f"ps -p {pid} -o comm=", shell=True)
            return output.decode().strip()
    except subprocess.CalledProcessError:
        return "Unknown"

def scan_ports(common_ports=None):
    """Scan ports and return information about each port."""
    if common_ports is None:
        common_ports = [8080, 8000, 8081, 8082, 8083, 8084, 8085, 8086, 8087, 8088, 8089, 8090, 3000, 5000, 9000, 
                       1883, 8883, 9001, 9883]
    
    results = []
    for port in common_ports:
        status = "In use" if check_port_in_use(port) else "Available"
        pid = find_process_using_port(port) if status == "In use" else ""
        process = get_process_name(pid) if pid else ""
        results.append({
            'port': port,
            'status': status,
            'pid': pid,
            'process': process
        })
    return results

def display_port_info(port_info, highlight_idx=None, auto_cycling=False):
    """Display formatted port information."""
    os.system('clear' if platform.system() != 'Windows' else 'cls')
    print("\n===== PORT FINDER =====")
    
    if auto_cycling:
        print("AUTO-CYCLING MODE: Press ENTER to kill highlighted process, any other key to stop cycling")
    
    print(f"{'#':<3} {'Port':<6} {'Status':<15} {'PID':<8} {'Process':<15}")
    print("-" * 50)
    
    for idx, info in enumerate(port_info):
        prefix = "→ " if idx == highlight_idx else "  "
        # Convert all values to strings to prevent formatting issues
        port = str(info['port'])
        status = str(info['status'])
        pid = str(info['pid']) if info['pid'] else ""
        process = str(info['process']) if info['process'] else ""
        print(f"{prefix}{idx+1:<2} {port:<6} {status:<15} {pid:<8} {process:<15}")
    
    print("\n" + "-" * 50)

def kill_highlighted_process(port_info, selected_idx):
    """Kill the currently highlighted process and return whether it was successful."""
    if selected_idx < len(port_info) and port_info[selected_idx]['pid']:
        pid = port_info[selected_idx]['pid']
        port = port_info[selected_idx]['port']
        process = port_info[selected_idx]['process']
        
        print(f"Killing process {process} (PID: {pid}) on port {port}...")
        return kill_process(pid)
    return False

def is_input_available():
    """Check if input is available."""
    if os.name == 'nt':  # Windows
        import msvcrt
        return msvcrt.kbhit()
    else:  # Unix/Linux/Mac
        import termios
        import fcntl
        
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)
        
        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
        
        try:
            return len(sys.stdin.read(1)) > 0
        except (IOError, TypeError):
            return False
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)

def get_key_press():
    """Get a key press in a non-blocking way."""
    if os.name == 'nt':  # Windows
        import msvcrt
        if msvcrt.kbhit():
            return msvcrt.getch().decode()
        return None
    else:  # Unix/Linux/Mac
        import termios
        import tty
        
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x03':  # Ctrl+C
                raise KeyboardInterrupt
            return ch
        except (termios.error, IOError):
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def interactive_menu():
    """Run the interactive port finder menu."""
    # Initial scan
    print("Scanning ports...")
    port_info = scan_ports()
    
    selected_idx = 0
    auto_cycling = False
    cycle_delay = 1.0  # Seconds between cycling
    
    while True:
        try:
            # Get only in-use ports for cycling
            in_use_ports = [i for i, info in enumerate(port_info) if info['status'] == 'In use' and info['pid']]
            
            # If in auto-cycling mode, update the selected index to the next in-use port
            if auto_cycling and in_use_ports:
                if selected_idx in in_use_ports:
                    current_pos = in_use_ports.index(selected_idx)
                    selected_idx = in_use_ports[(current_pos + 1) % len(in_use_ports)]
                else:
                    selected_idx = in_use_ports[0]
            
            display_port_info(port_info, selected_idx, auto_cycling)
            
            # If not in auto_cycling, show regular menu
            if not auto_cycling:
                print("\nCommands:")
                print("  [↑/↓] Navigate | [k] Kill process | [r] Refresh | [s] Scan custom port | [q] Quit")
                print("  [f] Find port by number | [a] Auto-cycle mode | [Enter] Kill highlighted process")
                
                # Get user input
                key = input("\nEnter command: ").lower()
                
                if key == 'q':
                    break
                elif key in ['up', 'w']:
                    selected_idx = (selected_idx - 1) % len(port_info)
                elif key in ['down', 's']:
                    selected_idx = (selected_idx + 1) % len(port_info)
                elif key == 'k' or key == '':  # 'k' or Enter key
                    if kill_highlighted_process(port_info, selected_idx):
                        print("Process successfully terminated.")
                        time.sleep(1)
                        # Refresh the port info
                        port_info = scan_ports()
                    else:
                        print("Failed to kill process or no process to kill.")
                        input("Press Enter to continue...")
                elif key == 'r':
                    print("Refreshing port information...")
                    port_info = scan_ports()
                elif key == 's':
                    try:
                        custom_port = int(input("Enter port number to scan: "))
                        custom_info = scan_ports([custom_port])
                        if custom_info and custom_info[0] not in port_info:
                            port_info.append(custom_info[0])
                            selected_idx = len(port_info) - 1
                    except ValueError:
                        print("Invalid port number.")
                        input("Press Enter to continue...")
                elif key == 'f':
                    try:
                        search_port = int(input("Enter port number to find: "))
                        found = False
                        for idx, info in enumerate(port_info):
                            if info['port'] == search_port:
                                selected_idx = idx
                                found = True
                                break
                        
                        if not found:
                            print(f"Port {search_port} not in the list. Scanning...")
                            custom_info = scan_ports([search_port])
                            if custom_info:
                                port_info.append(custom_info[0])
                                selected_idx = len(port_info) - 1
                    except ValueError:
                        print("Invalid port number.")
                        input("Press Enter to continue...")
                elif key == 'a':
                    # Only enter auto-cycling if there are in-use ports
                    if in_use_ports:
                        auto_cycling = True
                        selected_idx = in_use_ports[0]
                        try:
                            cycle_delay = float(input("Enter delay between cycles (seconds): ") or "1.0")
                        except ValueError:
                            cycle_delay = 1.0
                    else:
                        print("No in-use ports found for auto-cycling.")
                        input("Press Enter to continue...")
            else:
                # In auto_cycling mode
                # Wait for cycle_delay seconds or until a key is pressed
                print("\nAuto-cycling... Press ENTER to kill current process, any other key to exit")
                
                start_time = time.time()
                while (time.time() - start_time) < cycle_delay:
                    time.sleep(0.1)  # Small delay to prevent CPU hogging
                    
                    # Check for keypress
                    if is_input_available():
                        key = get_key_press()
                        if key in ['\r', '\n', '']:  # Enter key
                            if kill_highlighted_process(port_info, selected_idx):
                                print("Process successfully terminated.")
                                # Refresh port info after killing
                                port_info = scan_ports()
                                # Update in-use ports 
                                in_use_ports = [i for i, info in enumerate(port_info) if info['status'] == 'In use' and info['pid']]
                                if not in_use_ports:  # If no more processes, exit auto mode
                                    auto_cycling = False
                                    print("No more processes to cycle through.")
                                    input("Press Enter to continue...")
                                    break
                            break  
                        else:
                            # Any other key exits auto mode
                            auto_cycling = False
                            break
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            input("Press Enter to continue...")
            
            # If an error occurs in auto-cycling mode, exit that mode
            if auto_cycling:
                auto_cycling = False

def main():
    parser = argparse.ArgumentParser(description="Find and optionally kill processes using specific ports")
    parser.add_argument("port", type=int, nargs="?", help="The port to check")
    parser.add_argument("-k", "--kill", action="store_true", help="Kill the process using the port")
    parser.add_argument("-s", "--scan", action="store_true", help="Scan common ports for processes")
    parser.add_argument("-u", "--ui", action="store_true", help="Launch interactive UI mode")
    parser.add_argument("-a", "--auto", action="store_true", help="Launch in auto-cycling mode")
    
    args = parser.parse_args()

    # If no arguments are provided or UI flag is set, launch the interactive menu
    if len(sys.argv) == 1 or args.ui or args.auto:
        interactive_menu()
        return

    # Scan common ports
    if args.scan:
        port_info = scan_ports()
        print(f"{'Port':<6} {'Status':<15} {'PID':<8} {'Process':<15}")
        print("-" * 45)
        for info in port_info:
            print(f"{info['port']:<6} {info['status']:<15} {info['pid']:<8} {info['process']:<15}")
        return

    # Check specific port
    if args.port:
        port = args.port
        if check_port_in_use(port):
            pid = find_process_using_port(port)
            if pid:
                process = get_process_name(pid)
                print(f"Port {port} is in use by process {process} (PID: {pid})")
                
                if args.kill:
                    print(f"Killing process {pid}...")
                    if kill_process(pid):
                        print(f"Process {pid} successfully terminated.")
                    else:
                        print(f"Failed to kill process {pid}. You may need admin/root privileges.")
                else:
                    response = input("Do you want to kill this process? (y/n): ")
                    if response.lower() == 'y':
                        if kill_process(pid):
                            print(f"Process {pid} successfully terminated.")
                        else:
                            print(f"Failed to kill process {pid}. You may need admin/root privileges.")
            else:
                print(f"Port {port} is in use, but unable to identify the process.")
        else:
            print(f"Port {port} is not in use.")

if __name__ == "__main__":
    main() 