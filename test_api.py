#!/usr/bin/env python
import requests
import json

# Login as admin
response = requests.post("http://localhost:8000/auth/login", json={
    "username": "admin",
    "password": "admin123"
})

data = response.json()
print(f"Login status: {response.status_code}")

if response.status_code == 200:
    token = data.get("access_token")

    # Get captures
    response = requests.get(
        "http://localhost:8000/admin/captures",
        headers={"Authorization": f"Bearer {token}"}
    )

    captures = response.json()
    print(f"\nTotal captures returned: {len(captures) if isinstance(captures, list) else 'error'}")

    if isinstance(captures, list):
        approved = [c for c in captures if c.get("annoteur_approved")]
        print(f"Approved captures: {len(approved)}")

        if approved:
            print("\nFirst approved capture:")
            print(json.dumps(approved[0], indent=2, default=str))
        else:
            print("\nNo approved captures in response")
            print(f"Sample capture:")
            if captures:
                print(json.dumps(captures[0], indent=2, default=str))
    else:
        print(f"Error: {captures}")
else:
    print(f"Login failed: {data}")
