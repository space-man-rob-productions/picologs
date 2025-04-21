import os
import sys
import subprocess
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Redis URL from .env file
redis_url = os.getenv('REDIS_URL')
version = os.getenv('VERSION')
print(f"Got Redis URL from .env: {redis_url}")
print(f"Got Version from .env: {version}")

if not redis_url:
    print("Error: configure error")
    sys.exit(1)

# Ensure URL has the correct scheme
if not redis_url.startswith(('redis://', 'rediss://')):
    redis_url = 'redis://' + redis_url
    print(f"Added redis:// scheme to URL: {redis_url}")

# Get current git tag version
try:
    version = subprocess.check_output(['git', 'describe', '--tags', '--abbrev=0']).decode('utf-8').strip()
    if version.startswith('v'):
        version = version[1:]  # Remove 'v' prefix
    print(f"Building version: {version}")
except Exception as e:
    print(f"Error getting git tag version: {str(e)}")
    sys.exit(1)

# Read the original file
print("Reading sc_command.py...")
with open('sc_command.py', 'r') as f:
    content = f.read()

# Replace the placeholders with actual values
print("Replacing placeholders...")
content = content.replace('"REPLACE_WITH_REDIS_URL"', f'"{redis_url}"')
content = content.replace('"REPLACE_WITH_VERSION"', f'"{version}"')

# Write the modified content to a temporary file
print("Writing temporary build file...")
with open('sc_command_build.py', 'w') as f:
    f.write(content)

# Build the executable
print("Building executable...")
os.system(f'pyinstaller --onefile --name picologs-{version} sc_command_build.py')

# Clean up the temporary file
print("Cleaning up...")
os.remove('sc_command_build.py')
print("Done!") 