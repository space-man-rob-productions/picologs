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

# Load environment variables from .env file if it exists
load_dotenv()

# Get the AppData path for configuration
APP_DATA_PATH = os.path.join(os.getenv('APPDATA'), 'SC-Command')
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
                return json.load(f)
        except:
            pass
    
    # Default config
    return {
        'game_log_path': ''
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def prompt_for_config():
    config = load_or_create_config()
    
    # Prompt for Game.log location if not set or invalid
    default_path = r"C:\Program Files\Roberts Space Industries\StarCitizen\LIVE\Game.log"
    while not os.path.exists(config.get('game_log_path', '')):
        print("\nPlease enter the full path to your Game.log file:")
        print(f"(Default: {default_path})")
        print("Press Enter to use default path")
        
        path = input("> ").strip()
        if not path and os.path.exists(default_path):
            path = default_path
        
        if path and os.path.exists(path):
            config['game_log_path'] = path
            save_config(config)  # Save the config after updating it
            break
        else:
            print("\nError: File not found at specified path!")
    
    return config

# Initialize configuration
config = prompt_for_config()

# Ensure URL has the correct scheme
if not REDIS_URL.startswith(('redis://', 'rediss://')):
    REDIS_URL = 'redis://' + REDIS_URL

try:
    r = redis.Redis.from_url(REDIS_URL)
    # Test the connection
    r.ping()
except Exception as e:
    print(f"Error connecting to Redis: {str(e)}")
    print("Please ensure REDIS_URL is set in your environment or .env file")
    sys.exit(1)

class FileWatcher(FileSystemEventHandler):
    def __init__(self, file_path):
        self.file_path = file_path
        self.player_name = self.get_player_name()
        self.last_position = self.get_file_size()
        print(f"Detected player name: {self.player_name}")
    
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
            # Convert event to JSON string
            event_json = json.dumps(event)
            
            # Push to REDIS JSON list
            if not r.exists("events"):
                r.json().set("events", "$", [])
            r.json().arrappend("events", "$", event)
                
        except Exception as e:
            print(f"Error saving event: {str(e)}")
        
    def send_heartbeat(self):
        try:
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            r.hset("sc_player_heartbeats", self.player_name, timestamp)
        except Exception as e:
            print(f"Error sending heartbeat: {str(e)}")

    def send_player_claim(self):
        try:
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            r.hset("player_claims", f"{self.player_name}", json.dumps(timestamp))
        except Exception as e:
            print(f"Error sending player claim: {str(e)}")
            
    def check_file(self):
        self.send_heartbeat()
            
        try:
            current_size = os.path.getsize(self.file_path)
            if current_size < self.last_position:
                # print(f"File was truncated, resetting position from {self.last_position} to 0")
                self.last_position = 0
                
            if current_size == self.last_position:
                return
                
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

def main():
    print("\nSC Command - Star Citizen Event Tracker")
    print("=" * 40)
    
    config = prompt_for_config()
    print(f"\nConfiguration loaded:")
    print(f"Game.log: {config['game_log_path']}")    
    try:
        watcher = FileWatcher(config['game_log_path'])
        print("\nTracking events for player:")
        print(f">>> {watcher.player_name} <<<")
        watcher.send_player_claim()
        webbrowser.open(f'https://sc-command-web.vercel.app?player={watcher.player_name}')
        print("\nPress Ctrl+C to stop...")
        
        while True:
            try:
                watcher.check_file()  # This now includes heartbeat check
                time.sleep(5)
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
