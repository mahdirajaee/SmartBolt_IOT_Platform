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
import json
import concurrent.futures
import re
from datetime import datetime

def check_port_in_use(port):
    try:
        # First try the socket binding approach
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            if result == 0:  # Port is open
                return True
                
        # Double-check with a different method
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                s.close()
                return False  # Port is free
            except socket.error:
                return True  # Port is in use
    except Exception:
        # If any errors occur during port checking, attempt system-specific check
        if platform.system() == "Windows":
            try:
                output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True)
                return bool(output.strip())  # If output exists, port is in use
            except subprocess.CalledProcessError:
                return False
        else:  # macOS / Linux
            try:
                output = subprocess.check_output(f"lsof -i :{port}", shell=True)
                return bool(output.strip())  # If output exists, port is in use
            except subprocess.CalledProcessError:
                return False

def find_process_using_port(port):
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
    elif platform.system() == "Darwin":  # macOS
        try:
            # Try first with lsof
            cmd = f"lsof -i :{port} -t"
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            pids = output.split('\n')
            if pids and pids[0]:
                return pids[0]
        except subprocess.CalledProcessError:
            try:
                # Try with netstat if lsof fails
                cmd = f"netstat -anv | grep {port} | grep LISTEN"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
                if output:
                    lines = output.strip().split('\n')
                    for line in lines:
                        parts = line.split()
                        if len(parts) > 8:  # netstat output has PID in the 9th column on macOS
                            return parts[8]
            except subprocess.CalledProcessError:
                return None
    else:  # Linux
        try:
            # Try lsof
            cmd = f"lsof -i :{port} -t"
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            pids = output.split('\n')
            if pids and pids[0]:
                return pids[0]
        except subprocess.CalledProcessError:
            try:
                # Try netstat if lsof fails
                cmd = f"netstat -tulpn | grep :{port}"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
                if output:
                    for line in output.strip().split('\n'):
                        if f":{port}" in line:
                            # Extract PID from the last column which looks like "PID/Program"
                            pid_part = line.strip().split()[-1].split('/')[-2]
                            return pid_part
            except subprocess.CalledProcessError:
                return None
    return None

def kill_process(pid):
    try:
        pid = int(pid)
        if platform.system() == "Windows":
            subprocess.check_call(f"taskkill /F /PID {pid}", shell=True)
        elif platform.system() == "Darwin":  # macOS
            try:
                # First try SIGTERM
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)  # Give it a moment to terminate
                
                # Check if process still exists
                try:
                    os.kill(pid, 0)  # This will raise OSError if process is gone
                    # Process still exists, use SIGKILL
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass  # Process already terminated
            except Exception as e:
                # If direct kill fails, try sudo
                print(f"Direct kill failed: {e}. Trying with sudo...")
                try:
                    subprocess.check_call(['sudo', 'kill', '-9', str(pid)])
                except subprocess.CalledProcessError:
                    return False
        else:  # Linux and others
            # Try SIGTERM first, then SIGKILL if needed
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
                os.kill(pid, 0)  # Check if process exists
                os.kill(pid, signal.SIGKILL)  # Still exists, use SIGKILL
            except OSError:
                pass  # Process already terminated
        return True
    except Exception as e:
        print(f"Error killing process: {e}")
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

SMARTBOLT_PORTS = {
    'Resource Catalog': 8080,
    'Time Series DB Connector': 8081,
    'Analytics Microservice': 8082,
    'Control Center': 8083,
    'Web Dashboard': 8084,
    'Telegram Bot': 8085,
    'Account Manager': 8088,
    'MQTT Broker': 1883,
    'InfluxDB': 8086,
    'Raspberry Pi Connector': 8089
}

DEFAULT_COMMON_PORTS = [8080, 8000, 8081, 8082, 8083, 8084, 8085, 8086, 8087, 8088, 8089, 8090, 
                     3000, 4000, 5000, 5001, 5002, 5003, 5004, 5005, 5010, 5011, 9000, 
                     1883, 8883, 9001, 9883, 8006, 8008, 5009]

def scan_single_port(port):
    status = "In use" if check_port_in_use(port) else "Available"
    pid = find_process_using_port(port) if status == "In use" else ""
    process = get_process_name(pid) if pid else ""
    
    service_name = ""
    for name, p in SMARTBOLT_PORTS.items():
        if p == port:
            service_name = name
            break
            
    return {
        'port': port,
        'status': status,
        'pid': pid,
        'process': process,
        'service': service_name
    }

def scan_ports(common_ports=None, use_threading=True):
    if common_ports is None:
        common_ports = DEFAULT_COMMON_PORTS
    
    if use_threading and len(common_ports) > 1:
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, len(common_ports))) as executor:
            future_to_port = {executor.submit(scan_single_port, port): port for port in common_ports}
            for future in concurrent.futures.as_completed(future_to_port):
                results.append(future.result())
        
        return sorted(results, key=lambda x: x['port'])
    else:
        results = []
        for port in common_ports:
            results.append(scan_single_port(port))
        return results

def get_color_code(text):
    COLORS = {
        "In use": "\033[91m",      # Red
        "Available": "\033[92m",   # Green
        "MessageBroker": "\033[94m",  # Blue
        "MS_": "\033[95m",            # Purple
        "RESET": "\033[0m"
    }
    
    for key, color in COLORS.items():
        if key in text:
            return color
    return ""

def colorize(text):
    color_code = get_color_code(text)
    reset = "\033[0m" if color_code else ""
    return f"{color_code}{text}{reset}"

def display_port_info(port_info, highlight_idx=None, auto_cycling=False, filter_text=""):
    os.system('clear' if platform.system() != 'Windows' else 'cls')
    print("\n===== SMARTBOLT PORT FINDER =====")
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Time: {current_time} | System: {platform.system()} {platform.release()}")
    
    if auto_cycling:
        print("\nAUTO-CYCLING MODE: Press ENTER to kill highlighted process, any other key to stop cycling")
    
    if filter_text:
        print(f"\nFilter: '{filter_text}'")
        
    filtered_info = port_info
    if filter_text:
        filtered_info = []
        for info in port_info:
            match_string = f"{info['port']} {info['status']} {info['pid']} {info['process']} {info['service']}"
            if filter_text.lower() in match_string.lower():
                filtered_info.append(info)
    
    # Count stats
    used_count = sum(1 for info in filtered_info if info['status'] == "In use")
    total_count = len(filtered_info)
    smartbolt_count = sum(1 for info in filtered_info if info['service'])
    
    print(f"\nShowing {total_count} ports ({used_count} in use, {total_count - used_count} available, {smartbolt_count} SmartBolt services)")
    
    print(f"\n{'#':<3} {'Port':<6} {'Status':<15} {'PID':<8} {'Process':<20} {'Service':<20}")
    print("-" * 75)
    
    for idx, info in enumerate(filtered_info):
        prefix = "→ " if idx == highlight_idx else "  "
        port = str(info['port'])
        status = colorize(str(info['status']))
        pid = str(info['pid']) if info['pid'] else ""
        process = str(info['process']) if info['process'] else ""
        service = colorize(str(info['service'])) if info['service'] else ""
        
        print(f"{prefix}{idx+1:<2} {port:<6} {status:<15} {pid:<8} {process:<20} {service:<20}")
    
    print("\n" + "-" * 75)

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

def save_config(config, filename="port_config.json"):
    try:
        with open(filename, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return False

def load_config(filename="port_config.json"):
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading configuration: {e}")
    return None

def interactive_menu():
    print("Scanning ports...")
    port_info = scan_ports()
    
    selected_idx = 0
    auto_cycling = False
    cycle_delay = 1.0
    filter_text = ""
    custom_scan_mode = False
    last_scan_time = datetime.now()
    
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
            
            display_port_info(port_info, selected_idx, auto_cycling, filter_text)
            
            # Show scan time info
            scan_age = (datetime.now() - last_scan_time).seconds
            print(f"Last scan: {scan_age} seconds ago")
            
            # If not in auto_cycling, show regular menu
            if not auto_cycling:
                print("\nCommands:")
                print("  [↑/↓] Navigate | [k] Kill process | [r] Refresh | [s] Custom scan | [q] Quit")
                print("  [f] Filter results | [a] Auto-cycle | [Enter] Kill process | [b] Batch scan")
                if custom_scan_mode:
                    print("  [m] SmartBolt ports | [c] Common ports")
                print("  [p] Save configuration | [l] Load configuration | [x] Kill all SmartBolt ports")
                
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
                        custom_scan_mode = True
                        custom_ports_input = input("Enter port number(s) to scan (comma separated): ")
                        custom_ports = [int(p.strip()) for p in custom_ports_input.split(',') if p.strip()]
                        
                        if custom_ports:
                            print(f"Scanning {len(custom_ports)} custom ports...")
                            custom_info = scan_ports(custom_ports)
                            port_info = custom_info
                            selected_idx = 0 if port_info else 0
                            last_scan_time = datetime.now()
                    except ValueError:
                        print("Invalid port number(s). Use comma to separate multiple ports.")
                        input("Press Enter to continue...")
                elif key == 'f':
                    filter_text = input("Enter filter text (port, status, service, etc.): ")
                
                elif key == 'b':
                    try:
                        start_port = int(input("Enter start port: ") or "8000")
                        end_port = int(input("Enter end port: ") or "9000")
                        
                        if start_port > end_port or end_port - start_port > 1000:
                            print("Invalid range or too large (max 1000 ports).")
                            input("Press Enter to continue...")
                        else:
                            print(f"Batch scanning ports {start_port}-{end_port}...")
                            custom_scan_mode = True
                            port_range = range(start_port, end_port + 1)
                            port_info = scan_ports(list(port_range))
                            selected_idx = 0
                            last_scan_time = datetime.now()
                    except ValueError:
                        print("Invalid port numbers.")
                        input("Press Enter to continue...")
                        
                elif key == 'm':
                    print("Scanning SmartBolt ports...")
                    port_info = scan_ports(list(SMARTBOLT_PORTS.values()))
                    selected_idx = 0
                    custom_scan_mode = True
                    last_scan_time = datetime.now()
                    
                elif key == 'c':
                    print("Scanning common ports...")
                    port_info = scan_ports()
                    selected_idx = 0
                    custom_scan_mode = False
                    last_scan_time = datetime.now()
                    
                elif key == 'p':
                    config = {
                        'last_scan': [info['port'] for info in port_info],
                        'custom_ports': [info['port'] for info in port_info if info['port'] not in DEFAULT_COMMON_PORTS]
                    }
                    if save_config(config):
                        print("Configuration saved successfully.")
                    else:
                        print("Failed to save configuration.")
                    input("Press Enter to continue...")
                    
                elif key == 'l':
                    config = load_config()
                    if config and 'last_scan' in config:
                        print("Loading saved port configuration...")
                        port_info = scan_ports(config['last_scan'])
                        selected_idx = 0
                        custom_scan_mode = True
                        last_scan_time = datetime.now()
                    else:
                        print("No configuration found or invalid configuration.")
                        input("Press Enter to continue...")
                        
                elif key == 'x':
                    active_ports = []
                    for name, port in SMARTBOLT_PORTS.items():
                        if check_port_in_use(port):
                            active_ports.append((name, port))
                    
                    if not active_ports:
                        print("No active SmartBolt services found")
                        input("Press Enter to continue...")
                    else:
                        print(f"Found {len(active_ports)} active SmartBolt services:")
                        for name, port in active_ports:
                            pid = find_process_using_port(port)
                            process = get_process_name(pid) if pid else "Unknown"
                            print(f"  - {name} on port {port} (PID: {pid}, Process: {process})")
                        
                        confirm = input("\nDo you want to kill all these services? (y/n): ")
                        if confirm.lower() == 'y':
                            for name, port in active_ports:
                                print(f"Killing {name} on port {port}...")
                                if kill_port(port, force=True):
                                    print(f"  Success!")
                                else:
                                    print(f"  Failed!")
                            
                            # Refresh the port info
                            port_info = scan_ports()
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

def find_python_process_by_port(port):
    try:
        if platform.system() == "Darwin":  # macOS
            # Get all Python processes
            cmd = "ps aux | grep python"
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            lines = output.split('\n')
            
            # Get process using the port
            port_cmd = f"lsof -i :{port}"
            try:
                port_output = subprocess.check_output(port_cmd, shell=True).decode().strip()
                if not port_output:
                    return None
                
                # Extract PID from lsof output
                lsof_lines = port_output.split('\n')[1:]  # Skip header
                if not lsof_lines:
                    return None
                    
                pid = lsof_lines[0].split()[1]
                return pid
            except subprocess.CalledProcessError:
                return None
    except Exception as e:
        print(f"Error finding Python process: {e}")
        return None

def force_kill_processes_on_port(port):
    try:
        # Attempt multiple methods to ensure the port is freed
        if platform.system() == "Darwin":  # macOS
            # First identify if a Python process is using this port
            pid = find_python_process_by_port(port)
            if pid:
                print(f"Found Python process with PID {pid} on port {port}")
                # Kill the specific Python process
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    print(f"Killed process {pid}")
                except Exception as e:
                    print(f"Failed direct kill: {e}")
            
            # Now use more system-level commands to ensure port is free
            try:
                # This will kill ANY process using the port
                cmd = f"lsof -ti :{port} | xargs kill -9"
                subprocess.run(cmd, shell=True, stderr=subprocess.PIPE)
                print(f"Executed force kill on port {port}")
                return True
            except Exception as e:
                print(f"Kill attempt failed: {e}")
                return False
        elif platform.system() == "Windows":
            # Windows command to find and kill process on port
            cmd1 = f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{port} ^| findstr LISTENING\') do @taskkill /F /PID %a'
            subprocess.run(cmd1, shell=True)
            return True
        else:  # Linux
            cmd = f"fuser -k {port}/tcp"
            subprocess.run(cmd, shell=True)
            return True
    except Exception as e:
        print(f"Force kill failed: {e}")
        return False

def kill_port(port, force=False):
    if not check_port_in_use(port):
        print(f"Port {port} is not in use.")
        return True
    
    # Try to find the process
    pid = find_process_using_port(port)
    
    if pid:
        try:
            process_name = get_process_name(pid)
            print(f"Found process {process_name} (PID: {pid}) using port {port}")
        except:
            process_name = "Unknown"
            print(f"Found process with PID: {pid} using port {port}")
        
        if not force:
            confirm = input(f"Kill this process? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled.")
                return False
        
        # Try normal kill first
        try:
            if platform.system() == "Windows":
                subprocess.check_call(f"taskkill /F /PID {pid}", shell=True)
            else:
                os.kill(int(pid), signal.SIGTERM)
            
            # Give it a moment
            time.sleep(0.5)
            if not check_port_in_use(port):
                print(f"Successfully killed process on port {port}")
                return True
        except Exception as e:
            print(f"Standard kill failed: {e}")
    else:
        print(f"Couldn't identify the specific process on port {port}, will try force methods")
        if not force:
            confirm = input(f"Attempt force kill on port {port}? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled.")
                return False
    
    # If we get here, normal kill failed or we couldn't find PID - use force methods
    print(f"Attempting force kill methods on port {port}...")
    if force_kill_processes_on_port(port):
        time.sleep(0.5)  # Brief pause
        if not check_port_in_use(port):
            print(f"Successfully force-killed process on port {port}")
            return True
        else:
            print(f"Warning: Port {port} still appears to be in use after kill attempts")
            print("The process might need more time to fully terminate.")
            return False
    else:
        print(f"Failed to kill process on port {port}")
        return False

def kill_service(service_name, force=False):
    if service_name not in SMARTBOLT_PORTS:
        print(f"Unknown SmartBolt service: {service_name}")
        return False
        
    port = SMARTBOLT_PORTS[service_name]
    print(f"Service {service_name} uses port {port}")
    return kill_port(port, force)
    
def kill_all_ports(ports, force=False):
    success_count = 0
    fail_count = 0
    
    for port in ports:
        print(f"\nAttempting to kill port {port}...")
        if kill_port(port, force):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\nKill operation completed: {success_count} succeeded, {fail_count} failed")
    return success_count, fail_count

def main():
    parser = argparse.ArgumentParser(description="Find and optionally kill processes using specific ports")
    parser.add_argument("port", type=int, nargs="?", help="The port to check")
    parser.add_argument("-k", "--kill", action="store_true", help="Kill the process using the port")
    parser.add_argument("-kf", "--kill-force", action="store_true", help="Kill the process without confirmation")
    parser.add_argument("-kp", "--kill-port", type=int, help="Kill the process on specified port")
    parser.add_argument("-ks", "--kill-service", type=str, help="Kill a SmartBolt service by name")
    parser.add_argument("-kr", "--kill-range", type=str, help="Kill processes in port range (format: start-end)")
    parser.add_argument("-ka", "--kill-all", action="store_true", help="Kill all SmartBolt services")
    parser.add_argument("-s", "--scan", action="store_true", help="Scan common ports for processes")
    parser.add_argument("-u", "--ui", action="store_true", help="Launch interactive UI mode")
    parser.add_argument("-a", "--auto", action="store_true", help="Launch in auto-cycling mode")
    parser.add_argument("-b", "--smartbolt", action="store_true", help="Check SmartBolt platform ports")
    parser.add_argument("-r", "--range", type=str, help="Scan port range (format: start-end)")
    
    args = parser.parse_args()

    # If no arguments are provided or UI flag is set, launch the interactive menu
    if len(sys.argv) == 1 or args.ui or args.auto:
        interactive_menu()
        return
        
    # Check SmartBolt ports
    if args.smartbolt:
        smartbolt_ports = list(SMARTBOLT_PORTS.values())
        port_info = scan_ports(smartbolt_ports)
        print("SmartBolt Platform Port Status:")
        print(f"{'Service':<25} {'Port':<6} {'Status':<15} {'PID':<8} {'Process':<15}")
        print("-" * 70)
        
        for port in sorted(smartbolt_ports):
            service_name = next((name for name, p in SMARTBOLT_PORTS.items() if p == port), "")
            info = next((i for i in port_info if i['port'] == port), None)
            
            if info:
                status = info['status']
                pid = info['pid'] if info['pid'] else ""
                process = info['process'] if info['process'] else ""
                print(f"{service_name:<25} {port:<6} {status:<15} {pid:<8} {process:<15}")
        return

    # Scan port range
    if args.range:
        try:
            start, end = map(int, args.range.split('-'))
            if start > end or end - start > 1000:
                print("Invalid range or too large (max 1000 ports)")
                return
                
            port_range = list(range(start, end + 1))
            port_info = scan_ports(port_range)
            
            print(f"Port Range Scan ({start}-{end}):")
            print(f"{'Port':<6} {'Status':<15} {'PID':<8} {'Process':<15}")
            print("-" * 45)
            
            for info in port_info:
                if info['status'] == "In use":  # Only show in-use ports
                    print(f"{info['port']:<6} {info['status']:<15} {info['pid']:<8} {info['process']:<15}")
            return
        except ValueError:
            print("Invalid range format. Use start-end (e.g., 8000-9000)")
            return

    # Scan common ports
    if args.scan:
        port_info = scan_ports()
        print(f"{'Port':<6} {'Status':<15} {'PID':<8} {'Process':<15}")
        print("-" * 45)
        for info in port_info:
            print(f"{info['port']:<6} {info['status']:<15} {info['pid']:<8} {info['process']:<15}")
        return

    # Kill port directly
    if args.kill_port:
        kill_port(args.kill_port, args.kill_force)
        return
        
    # Kill service by name
    if args.kill_service:
        kill_service(args.kill_service, args.kill_force)
        return
        
    # Kill port range
    if args.kill_range:
        try:
            start, end = map(int, args.kill_range.split('-'))
            if start > end or end - start > 1000:
                print("Invalid range or too large (max 1000 ports)")
                return
                
            ports_to_kill = []
            for port in range(start, end + 1):
                if check_port_in_use(port):
                    ports_to_kill.append(port)
                    
            if not ports_to_kill:
                print(f"No active ports found in range {start}-{end}")
                return
                
            print(f"Found {len(ports_to_kill)} active ports in range {start}-{end}")
            kill_all_ports(ports_to_kill, args.kill_force)
            
        except ValueError:
            print("Invalid range format. Use start-end (e.g., 8000-9000)")
        return
        
    # Kill all SmartBolt services
    if args.kill_all:
        active_ports = []
        for port in SMARTBOLT_PORTS.values():
            if check_port_in_use(port):
                active_ports.append(port)
                
        if not active_ports:
            print("No active SmartBolt services found")
            return
            
        print(f"Found {len(active_ports)} active SmartBolt services")
        kill_all_ports(active_ports, args.kill_force)
        return
    
    # Check specific port
    if args.port:
        port = args.port
        if check_port_in_use(port):
            pid = find_process_using_port(port)
            if pid:
                process = get_process_name(pid)
                print(f"Port {port} is in use by process {process} (PID: {pid})")
                
                if args.kill or args.kill_force:
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