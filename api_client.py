"""
HTTP client for communicating with the Bellmounth FastAPI backend.
"""

import requests
import json
from typing import Optional, Dict, Any
from pathlib import Path
import socket

def check_internet_connection() -> bool:
    """Check if machine has actual internet connection by reaching a public server."""
    try:
        # Try to reach Google's public DNS server via HTTP
        response = requests.get("http://8.8.8.8:53", timeout=3)
        return True
    except:
        try:
            # Try to reach a reliable public endpoint
            response = requests.get("http://1.1.1.1", timeout=3)
            return True
        except:
            try:
                # Last resort: try to connect to Google
                response = requests.head("https://www.google.com", timeout=3)
                return response.status_code < 500
            except:
                return False

def classify_error(exception, response=None):
    """Classify an error into standard types."""
    if isinstance(exception, requests.ConnectionError):
        return "server_down"
    elif isinstance(exception, requests.Timeout):
        return "server_down"
    elif response and response.status_code in [401, 403]:
        return "auth_error"
    elif response and response.status_code >= 500:
        return "server_error"
    else:
        return "unknown"

class APIClient:
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip('/')
        self.access_token = None
        self.role = None
        self.user_id = None
        self.username = None

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Login with username and password."""
        try:
            response = requests.post(
                f"{self.api_url}/auth/login",
                json={"username": username, "password": password},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.role = data.get("role")
                self.user_id = data.get("user_id")
                self.username = data.get("username")
                return data
            else:
                error_type = classify_error(None, response)
                return {
                    "error": response.json().get("detail", "Login failed"),
                    "error_type": error_type
                }
        except requests.ConnectionError as e:
            return {
                "error": "Cannot connect to API. Check API_URL in config.",
                "error_type": "server_down",
                "details": str(e)
            }
        except requests.Timeout:
            return {
                "error": "Connection timeout",
                "error_type": "server_down",
                "details": "Server took too long to respond"
            }
        except Exception as e:
            return {
                "error": f"Login error: {str(e)}",
                "error_type": "unknown",
                "details": str(e)
            }

    def health_check(self) -> Dict[str, Any]:
        """Check if API is running. Returns {"ok": bool, "error_type": str, "error": str}"""
        try:
            response = requests.get(f"{self.api_url}/auth/health", timeout=3)
            if response.status_code == 200:
                return {"ok": True}
            else:
                error_type = classify_error(None, response)
                return {
                    "ok": False,
                    "error_type": error_type,
                    "error": f"Server returned {response.status_code}",
                    "details": response.text
                }
        except requests.ConnectionError as e:
            return {
                "ok": False,
                "error_type": "server_down",
                "error": "Cannot connect to server",
                "details": str(e)
            }
        except requests.Timeout:
            return {
                "ok": False,
                "error_type": "server_down",
                "error": "Connection timeout",
                "details": "Server took too long to respond"
            }
        except Exception as e:
            return {
                "ok": False,
                "error_type": "unknown",
                "error": str(e),
                "details": str(e)
            }

    def get_switches(self) -> Dict[str, Any]:
        """Get list of all switches. Returns {"ok": bool, "data": list} or error dict."""
        try:
            response = requests.get(
                f"{self.api_url}/switches/",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {
                    "ok": False,
                    "error_type": error_type,
                    "error": f"Failed to fetch switches (HTTP {response.status_code})",
                    "details": response.text
                }
        except requests.ConnectionError as e:
            return {
                "ok": False,
                "error_type": "server_down",
                "error": "Cannot connect to server",
                "details": str(e)
            }
        except requests.Timeout:
            return {
                "ok": False,
                "error_type": "server_down",
                "error": "Connection timeout",
                "details": "Server took too long to respond"
            }
        except Exception as e:
            return {
                "ok": False,
                "error_type": "unknown",
                "error": str(e),
                "details": str(e)
            }

    def get_switch(self, switch_id: str) -> Optional[Dict]:
        """Get switch details by ID."""
        try:
            response = requests.get(
                f"{self.api_url}/switches/{switch_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching switch: {e}")
            return None

    def upload_capture(
        self,
        machine_id: str,
        switch_id: str,
        measured_value_mm: float,
        p1_x: int,
        p1_y: int,
        p2_x: int,
        p2_y: int,
        capture_method: str,
        measurement_status: str,
        delta_mm: float,
        image_original_path: str,
        image_thresholded_path: str
    ) -> Dict[str, Any]:
        """Upload a measurement capture."""
        try:
            with open(image_original_path, "rb") as f_orig, \
                 open(image_thresholded_path, "rb") as f_thresh:

                files = {
                    "image_original": f_orig,
                    "image_thresholded": f_thresh
                }
                data = {
                    "machine_id": machine_id,
                    "switch_id": switch_id,
                    "measured_value_mm": measured_value_mm,
                    "p1_x": p1_x,
                    "p1_y": p1_y,
                    "p2_x": p2_x,
                    "p2_y": p2_y,
                    "capture_method": capture_method,
                    "measurement_status": measurement_status,
                    "delta_mm": delta_mm
                }

                response = requests.post(
                    f"{self.api_url}/captures/upload",
                    data=data,
                    files=files,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    timeout=15
                )

                if response.status_code == 200:
                    return {"ok": True, "data": response.json()}
                else:
                    error_type = classify_error(None, response)
                    return {
                        "ok": False,
                        "error_type": error_type,
                        "error": response.json().get("detail", "Upload failed"),
                        "details": response.text
                    }

        except FileNotFoundError as e:
            return {
                "ok": False,
                "error_type": "unknown",
                "error": f"Image file not found",
                "details": str(e)
            }
        except requests.ConnectionError as e:
            return {
                "ok": False,
                "error_type": "server_down",
                "error": "Cannot connect to server",
                "details": str(e)
            }
        except requests.Timeout:
            return {
                "ok": False,
                "error_type": "server_down",
                "error": "Upload timeout",
                "details": "Server took too long to respond"
            }
        except Exception as e:
            return {
                "ok": False,
                "error_type": "unknown",
                "error": str(e),
                "details": str(e)
            }

    def get_capture_queue(self, annoteur_id: str) -> list:
        """Get captures assigned to this annoteur."""
        try:
            response = requests.get(
                f"{self.api_url}/captures/queue",
                params={"annoteur_id": annoteur_id},
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching capture queue: {e}")
            return []

    def approve_capture(self, capture_id: str) -> Dict[str, Any]:
        """Approve a capture."""
        try:
            response = requests.put(
                f"{self.api_url}/captures/{capture_id}/approve",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def reject_capture(self, capture_id: str, reason: str = None) -> Dict[str, Any]:
        """Reject a capture."""
        try:
            response = requests.put(
                f"{self.api_url}/captures/{capture_id}/reject",
                params={"reason": reason},
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def delete_capture(self, capture_id: str) -> Dict[str, Any]:
        """Delete a capture."""
        try:
            response = requests.delete(
                f"{self.api_url}/captures/{capture_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    # ==================== ADMIN METHODS ====================

    def admin_get_users(self, role: str = None) -> Dict[str, Any]:
        """Get all users, optionally filtered by role."""
        try:
            params = {}
            if role:
                params["role"] = role
            response = requests.get(
                f"{self.api_url}/admin/users",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": f"Failed to fetch users (HTTP {response.status_code})", "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_create_user(self, username: str, password: str, email: str, role: str) -> Dict[str, Any]:
        """Create a new user."""
        try:
            data = {"username": username, "password": password, "email": email, "role": role}
            response = requests.post(
                f"{self.api_url}/admin/users",
                json=data,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "User creation failed"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_update_user(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Update a user (partial update - only non-None fields)."""
        try:
            data = {k: v for k, v in kwargs.items() if v is not None}
            response = requests.put(
                f"{self.api_url}/admin/users/{user_id}",
                json=data,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "User update failed"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_delete_user(self, user_id: str) -> Dict[str, Any]:
        """Delete a user."""
        try:
            response = requests.delete(
                f"{self.api_url}/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": "Delete failed", "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_get_machines(self) -> Dict[str, Any]:
        """Get all machines."""
        try:
            response = requests.get(
                f"{self.api_url}/admin/machines",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": f"Failed to fetch machines", "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_create_machine(self, machine_name: str, password: str, location: str, firmware_version: str) -> Dict[str, Any]:
        """Create a new machine."""
        try:
            data = {"machine_name": machine_name, "password": password, "location": location, "firmware_version": firmware_version}
            response = requests.post(
                f"{self.api_url}/admin/machines",
                json=data,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "Machine creation failed"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_update_machine(self, machine_id: str, **kwargs) -> Dict[str, Any]:
        """Update a machine (partial update - only non-None fields)."""
        try:
            data = {k: v for k, v in kwargs.items() if v is not None}
            response = requests.put(
                f"{self.api_url}/admin/machines/{machine_id}",
                json=data,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "Machine update failed"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_delete_machine(self, machine_id: str) -> Dict[str, Any]:
        """Delete a machine."""
        try:
            response = requests.delete(
                f"{self.api_url}/admin/machines/{machine_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": "Delete failed", "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_create_switch(self, switch_name: str, expected_diameter_mm: float, tolerance_min: float, tolerance_max: float, cable_type: str) -> Dict[str, Any]:
        """Create a new switch."""
        try:
            data = {"switch_name": switch_name, "expected_diameter_mm": expected_diameter_mm, "tolerance_min": tolerance_min, "tolerance_max": tolerance_max, "cable_type": cable_type}
            response = requests.post(
                f"{self.api_url}/admin/switches",
                json=data,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "Switch creation failed"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_update_switch(self, switch_id: str, **kwargs) -> Dict[str, Any]:
        """Update a switch (partial update)."""
        try:
            data = {k: v for k, v in kwargs.items() if v is not None}
            response = requests.put(
                f"{self.api_url}/admin/switches/{switch_id}",
                json=data,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "Switch update failed"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_delete_switch(self, switch_id: str) -> Dict[str, Any]:
        """Delete a switch."""
        try:
            response = requests.delete(
                f"{self.api_url}/admin/switches/{switch_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": "Delete failed", "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_get_captures(self, status: str = None) -> Dict[str, Any]:
        """Get all captures, optionally filtered by status."""
        try:
            params = {}
            if status:
                params["status"] = status
            response = requests.get(
                f"{self.api_url}/admin/captures",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": f"Failed to fetch captures", "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_assign_capture(self, capture_id: str, annoteur_id: str) -> Dict[str, Any]:
        """Assign a capture to an annoteur."""
        try:
            data = {"annoteur_id": annoteur_id}
            response = requests.put(
                f"{self.api_url}/admin/captures/{capture_id}/assign",
                json=data,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "Assign failed"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_approve_capture(self, capture_id: str) -> Dict[str, Any]:
        """Approve a capture."""
        try:
            response = requests.put(
                f"{self.api_url}/admin/captures/{capture_id}/approve",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "Approve failed"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def get_notifications(self) -> Dict[str, Any]:
        """Get all notifications for current user."""
        try:
            response = requests.get(
                f"{self.api_url}/notifications/",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": response.json().get("detail", "Failed to fetch notifications"), "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}
