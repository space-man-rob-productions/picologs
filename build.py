import os
import sys
import pyinstaller_versionfile

# Get Redis URL from environment variable
redis_url = os.getenv('REDIS_URL')
print(f"Got Redis URL from environment: {redis_url}")

if not redis_url:
    print("Error: REDIS_URL not found in environment variables!")
    sys.exit(1)

# Ensure URL has the correct scheme
if not redis_url.startswith(('redis://', 'rediss://')):
    redis_url = 'redis://' + redis_url
    print(f"Added redis:// scheme to URL: {redis_url}")

# Read the original file
print("Reading sc_command.py...")
with open('sc_command.py', 'r') as f:
    content = f.read()

# Replace the placeholder with the actual Redis URL
print("Replacing placeholder with Redis URL...")
content = content.replace('"REPLACE_WITH_REDIS_URL"', f'"{redis_url}"')

# Write the modified content to a temporary file
print("Writing temporary build file...")
with open('sc_command_build.py', 'w') as f:
    f.write(content)

# Build the executable
print("Building executable...")
os.system('pyinstaller --onefile --name sc-command sc_command_build.py')

# Clean up the temporary file
print("Cleaning up...")
os.remove('sc_command_build.py')
print("Done!") 