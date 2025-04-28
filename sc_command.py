from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import os
import json
import datetime
import sys
import redis
import webbrowser
from dotenv import load_dotenv
from win32com.client import Dispatch
import tkinter as tk
from tkinter import filedialog
import winreg

def find_star_citizen_path():
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for root, path in reg_paths:
        try:
            with winreg.OpenKey(root, path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if "Star Citizen" in name or "Roberts Space Industries" in name:
                                    try:
                                        install_path, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                        return install_path
                                    except (FileNotFoundError, OSError):
                                        try:
                                            uninstall_str, _ = winreg.QueryValueEx(subkey, "UninstallString")
                                            return os.path.dirname(uninstall_str)  # Extract directory from uninstall string
                                        except (FileNotFoundError, OSError):
                                            return "Install path not found, but app is installed."
                            except (FileNotFoundError, OSError):
                                continue
                    except (FileNotFoundError, OSError):
                        continue
        except (FileNotFoundError, OSError):
            continue
    
    # Check common installation paths if registry search fails
    common_paths = [
        r"C:\Program Files\Roberts Space Industries",
        r"C:\Program Files (x86)\Roberts Space Industries"
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
            
    return "Star Citizen not found in registry or common locations."


# Load environment variables from .env file if it exists
load_dotenv()

VERSION = "alpha-0.0.23"

# Debug flag for testing file selection dialog
DEBUG_FORCE_FILE_SELECT = False  # Set to True to force file selection dialog

# Get the AppData path for configuration
APP_DATA_PATH = os.path.join(os.getenv('APPDATA'), f'picologs-{VERSION}')
CONFIG_FILE = os.path.join(APP_DATA_PATH, 'config.json')

# Redis URL - This will be replaced during build process
# For development, it will use the environment variable
REDIS_URL = os.getenv('REDIS_URL', "REPLACE_WITH_REDIS_URL")

def load_or_create_config():
    # Create AppData directory if it doesn't exist
    if not os.path.exists(APP_DATA_PATH):
        os.makedirs(APP_DATA_PATH)
    
    # Load existing config if it exists
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Ensure auto_launch is set to true if it exists
                if 'auto_launch' in config:
                    config['auto_launch'] = True
                return config
        except:
            pass
    
    # Default config
    return {
        'game_log_path': '',
        'auto_launch': True,
        'sc_path': ''  # Add Star Citizen path to default config
    }

# C:\Program Files\Roberts Space Industries\RSI Launcher

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def prompt_for_config():
    config = load_or_create_config()
    
    # Get Star Citizen installation path
    sc_path = find_star_citizen_path()
    if sc_path == "Star Citizen not found in registry or common locations.":
        print("\nCould not automatically find Star Citizen installation.")
        print("Common installation paths:")
        print("1. C:\\Program Files\\Roberts Space Industries")
        print("2. C:\\Program Files (x86)\\Roberts Space Industries")
        print("\nPlease enter the full path to your Star Citizen installation:")
        sc_path = input("Path: ").strip()
        if not os.path.exists(sc_path):
            print("\nError: The specified path does not exist!")
            sys.exit(1)
    
    # Store the path in config
    config['sc_path'] = sc_path
    save_config(config)
    
    # Only prompt for version if not already configured
    if not config.get('game_log_path') or not os.path.exists(config.get('game_log_path')) or DEBUG_FORCE_FILE_SELECT:
        # Prompt for LIVE/PTU selection
        print("\nSelect Star Citizen version:")
        print("1. LIVE (default)")
        print("2. PTU")
        version_choice = input("Enter choice (1 or 2): ").strip()
        
        # Default to LIVE if no input
        version = "LIVE" if not version_choice or version_choice == "1" else "PTU"
        game_log_path = os.path.join(sc_path, f"StarCitizen\\{version}\\Game.log")
        
        if os.path.exists(game_log_path) and not DEBUG_FORCE_FILE_SELECT:
            config['game_log_path'] = game_log_path
            config['version'] = version
            save_config(config)  # Save the config after updating it
        else:
            if DEBUG_FORCE_FILE_SELECT:
                print("\nDebug mode: Forcing file selection dialog...")
            else:
                print(f"\nCould not find Game.log at {game_log_path}")
            print("Please select the Game.log file manually...")
            game_log_path = select_game_log_file()
            config['game_log_path'] = game_log_path
            config['version'] = version
            save_config(config)

        print("\nWould you like to automatically launch Picologs and RSI Launcher on Windows startup?")
        print("1. Yes (default)")
        print("2. No")
        auto_launch = input("Enter choice (1 or 2): ").strip()
        
        # Default to Yes if no input
        if auto_launch and auto_launch == "1":
            try:
                # Get current directory for pico.exe
                current_exe = os.path.join(os.getcwd(), f"picologs-{VERSION}.exe")                
                # Create dist directory if it doesn't exist
                dist_dir = os.path.join(os.getcwd(), "dist")
                os.makedirs(dist_dir, exist_ok=True)
                
                if not os.path.exists(current_exe):
                    print(f"Warning: Source executable not found at {current_exe}")
                    print("Please build the executable first using PyInstaller")
                    config['auto_launch'] = False
                    save_config(config)
                    return config
                                
                # Use the stored path from config
                sc_path = config['sc_path']
                launcher_path = os.path.join(sc_path, "RSI Launcher\\RSI Launcher.exe")
                
                # Create AppData directory for pico.exe
                appdata_path = os.path.join(os.getenv('APPDATA'), 'picologs')
                os.makedirs(appdata_path, exist_ok=True)
                target_exe = os.path.join(appdata_path, f"picologs-{VERSION}.exe")
                
                # Copy current exe to AppData
                import shutil
                try:
                    shutil.copy2(current_exe, target_exe)
                except Exception as e:
                    print(f"Error copying executable: {str(e)}")
                    config['auto_launch'] = False
                    save_config(config)
                    return config
                
                # Create a batch file in the user's AppData
                batch_content = f'@echo off\nstart "" "{target_exe}"\nstart "" "{launcher_path}" "%1"'
                batch_path = os.path.join(appdata_path, 'launch_pico.bat')
                with open(batch_path, 'w') as f:
                    f.write(batch_content)
                
                # Get icon paths - use stored path from config
                sc_path = config['sc_path']
                launcher_path = os.path.join(sc_path, "RSI Launcher\\RSI Launcher.exe")
                
                # Use the current executable as the icon source
                icon_path = os.path.join(os.getcwd(), f"picologs-{VERSION}.exe")
                if not os.path.exists(icon_path):
                    # Fall back to the target exe if source not found
                    icon_path = target_exe
                
                # Create shortcuts in both Desktop locations
                desktop_paths = [
                    os.path.join(os.path.expanduser('~'), 'Desktop'),  # Regular Desktop
                    os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')  # OneDrive Desktop
                ]
                
                shortcuts_created = 0
                for desktop_path in desktop_paths:
                    if not os.path.exists(desktop_path):
                        continue
                        
                    shortcut_path = os.path.join(desktop_path, 'Picologs.lnk')
                    
                    # Remove existing shortcut if it exists
                    if os.path.exists(shortcut_path):
                        try:
                            os.remove(shortcut_path)
                            print(f"Removed existing shortcut at: {shortcut_path}")
                        except Exception as e:
                            print(f"Error removing existing shortcut: {str(e)}")
                            continue
                    
                    try:
                        shell = Dispatch('WScript.Shell')
                        shortcut = shell.CreateShortCut(shortcut_path)
                        shortcut.Targetpath = batch_path
                        shortcut.WorkingDirectory = os.path.dirname(batch_path)
                        shortcut.IconLocation = icon_path
                        shortcut.save()
                        
                        if os.path.exists(shortcut_path):
                            shortcuts_created += 1
                        else:
                            print(f"Failed to create shortcut at: {shortcut_path}")
                            
                    except Exception as e:
                        print(f"Error creating shortcut: {str(e)}")
                        continue
                
                if shortcuts_created == 0:
                    print("Failed to create shortcuts in any location")
                    config['auto_launch'] = False
                    save_config(config)
                    return config
                
                # Save the version in config
                config['version'] = VERSION
                config['auto_launch'] = True
                save_config(config)

            except Exception as e:
                print(f"Error configuring auto-launch: {str(e)}")
                import traceback
                traceback.print_exc()
                config['auto_launch'] = True  # Keep auto_launch as true even if there's an error
                save_config(config)
        else:
            config['auto_launch'] = False
            save_config(config)

    else:
        # If config exists, use it
        print(f"Game.log: {config['game_log_path']}")
        print(f"Version: {config.get('version', 'LIVE')}")
    
    return config

# Ensure URL has the correct scheme
if not REDIS_URL.startswith(('redis://', 'rediss://')):
    REDIS_URL = 'redis://' + REDIS_URL

try:
    r = redis.Redis.from_url(REDIS_URL)
    # Test the connection
    r.ping()
except Exception as e:
    print(f"Error connecting")
    sys.exit(1)

class FileWatcher(FileSystemEventHandler):
    def __init__(self, file_path):
        self.file_path = file_path
        self.player_name = self.get_player_name()
        self.last_position = self.get_file_size()
        self.last_change_time = 0  # Initialize last change time    
        self.events = []  # Keep this as we still use it for tracking
        
    def get_file_size(self):
        try:
            return os.path.getsize(self.file_path)
        except:
            return 0
            
    def load_existing_events(self):
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    data = json.load(f)
                    # If file exists but is from a different player, start fresh
                    if data.get("player") != self.player_name:
                        return []
                    return data.get("events", [])
            except:
                pass
        return []
               
        
    def save_event(self, event_type, details, metadata=None, timestamp=None):
        if timestamp is None:
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            
        event = {
            "timestamp": timestamp,
            "player": self.player_name,
            "type": event_type,
            "details": details,
            "metadata": metadata
        }
        
        try:        
            # Push to REDIS JSON list
            if not r.exists("events"):
                r.json().set("events", "$", [])
            r.json().arrappend("events", "$", event)
                
        except Exception as e:
            print(f"Error saving event: {str(e)}")
            
    def check_file(self):
        try:
            current_size = os.path.getsize(self.file_path)
            if current_size < self.last_position:
                # print(f"File was truncated, resetting position from {self.last_position} to 0")
                self.last_position = 0
                
            # Update last change time when we detect new content
            self.last_change_time = time.time()
                
            # print(f"Reading file from position {self.last_position} to {current_size}")
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()
                
                # print(f"Found {len(new_lines)} new lines to process")
                for line in new_lines:
                    
                    # Check for system quit
                    if "<SystemQuit>" in line:
                        self.save_event("quit", {
                            "status": "offline",
                            "player": self.player_name
                        }, metadata={"line": line})
                        
                    # Check for player connection
                    if "<Expect Incoming Connection>" in line:
                        try:
                            nickname = line.split('nickname="')[1].split('"')[0]
                            session = line.split('session=')[1].split(' ')[0]
                            player_geid = line.split('playerGEID=')[1].split(' ')[0]
                            # Use nickname as the player name
                            self.player_name = nickname
                            self.save_event("connection", {
                                "session": session,
                                "player_geid": player_geid
                            }, metadata={"line": line})
                        except:
                            print("Failed to parse connection event")
                    
                    # Check for location updates
                    if f"Player[{self.player_name}]" in line and "Location[" in line:
                        location = line[line.find("Location["):].split("]")[0] + "]"
                        self.save_event("location", {"location": location}, metadata={"line": line})
                    
                    # Check for deaths
                    if "<Actor Death>" in line and self.player_name in line:
                        try:
                            victim = line.split("'")[1]
                            killer = line.split("killed by '")[1].split("'")[0]
                            damage_type = line.split("damage type '")[1].split("'")[0]
                            
                            if self.player_name == victim:
                                if victim == killer:
                                    self.save_event("death", {"type": "self", "cause": damage_type}, metadata={"line": line})
                                else:
                                    self.save_event("death", {"type": "killed", "killer": killer, "cause": damage_type}, metadata={"line": line})
                            elif self.player_name == killer:
                                self.save_event("kill", {"victim": victim, "cause": damage_type}, metadata={"line": line})
                        except:
                            self.save_event("death", {"type": "unknown"}, metadata={"line": line})

                     # Check for all deaths
                    if "<Actor Death>" in line:
                        try:
                            victim = line.split("'")[1]
                            killer = line.split("killed by '")[1].split("'")[0]
                            damage_type = line.split("damage type '")[1].split("'")[0]
                            
                            if self.player_name == victim:
                                if victim == killer:
                                    self.save_event("nearby_death", {"type": "self", "cause": damage_type}, metadata={"line": line})
                                else:
                                    self.save_event("nearby_death", {"type": "killed", "killer": killer, "cause": damage_type}, metadata={"line": line})
                            elif self.player_name == killer:
                                self.save_event("nearby_kill", {"victim": victim, "cause": damage_type}, metadata={"line": line})
                        except:
                            self.save_event("nearby_death", {"type": "unknown"}, metadata={"line": line})

                    # Check for ship entry
                    if "Entity [" in line and f"m_ownerGEID[{self.player_name}]" in line and "OnEntityEnterZone" in line:
                        try:
                            ship_type = line.split("Entity [")[1].split("]")[0]
                            ship_id = ship_type.split("_")[-1]
                            if ship_type.startswith(("AEGS", "ARGO", "ANVL", "CRUS", "DRAK", "MISC", "RSI", "ORIG", "MIRA")) and "_" in ship_type:
                                timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                                ship_data = {
                                    "id": ship_id,
                                    "name": ship_type,
                                    "owner": self.player_name,
                                    "captain": self.player_name,
                                    "timestamp": timestamp
                                }
                                if not r.exists("fleet"):
                                    r.json().set("fleet", "$", [])
                                r.json().arrappend("fleet", "$", ship_data)
                        except:
                            print("Failed to parse ship entry event")
                            

                    #<Vehicle Destruction> CVehicle::OnAdvanceDestroyLevel: Vehicle 'ORIG_m50_1725883130384'
                    if "<Vehicle Destruction>" in line and "Vehicle '" in line:
                        try:
                            ship_type = line.split("Vehicle '")[1].split("'")[0]
                            ship_id = ship_type.split("_")[-1]
                            self.save_event("ship_destroyed", {"ship": ship_id}, metadata={"line": line})
                            r.json().delete('fleet', f"$[?(@.id == \"{ship_id}\")]")
                        except:
                            print("Failed to parse ship destruction event")
                            
        except Exception as e:
            print(f"Error reading file: {str(e)}")

    def get_player_name(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as file:
                for line in file:
                    if "<AccountLoginCharacterStatus_Character>" in line and "name " in line:
                        # Extract name from the line
                        name = line.split("name ")[1].split(" -")[0]
                        return name
            print("Error: Could not find player name in log file!")
            sys.exit(1)  # Exit program if no name found
        except Exception as e:
            print(f"Error getting player name: {str(e)}")
            sys.exit(1)  # Exit program on error

def select_game_log_file():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Load config to get stored path
    config = load_or_create_config()
    initial_dir = config.get('sc_path', find_star_citizen_path())
    if initial_dir == "Star Citizen not found in registry or common locations.":
        initial_dir = None
    
    # Show file dialog
    file_path = filedialog.askopenfilename(
        title="Select Star Citizen Game.log",
        initialdir=initial_dir,
        filetypes=[("Log files", "*.log"), ("All files", "*.*")]
    )
    
    if not file_path:
        print("\nNo file selected. Exiting...")
        sys.exit(1)
        
    return file_path

def main():
    print("\nPicologs - Star Citizen Event Tracker")
    print("=" * 40)
    print("Current version: " + VERSION)
    
    # Check if this is first run
    config = load_or_create_config()
    
    # Continue with normal operation
    config = prompt_for_config()
    try:    
        watcher = FileWatcher(config['game_log_path'])
        print("\nTracking events for player:")
        print(f">>> {watcher.player_name} <<<")
        webbrowser.open(f'https://picologs.com?player={watcher.player_name}&version={VERSION}')
        print("\nPress Ctrl+C to stop...")
        
        while True:
            try:
                watcher.check_file()
                time.sleep(30)  # Reduced from 5 to 30 seconds
            except redis.RedisError as e:
                print(f"Redis Error during check: {str(e)}")
                time.sleep(30)  # Wait longer on Redis error
            except Exception as e:
                print(f"Error during check: {str(e)}")
                time.sleep(10)
                
    except KeyboardInterrupt:
        print(f"\nFile watching stopped.")
 
if __name__ == "__main__":
    main()
