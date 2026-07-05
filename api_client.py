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
    elif response and response.status_code == 403:
        # Check if it's a deactivation error
        try:
            detail = response.json().get("detail", "")
            if "deactivated" in detail.lower():
                return "account_deactivated"
        except:
            pass
        return "auth_error"
    elif response and response.status_code == 401:
        return "auth_error"
    elif response and response.status_code >= 500:
        return "server_error"
    else:
        return "unknown"

class APIClient:
    def __init__(self, api_url: str, api_key: str = None):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key  # For API key authentication
        self.access_token = None  # For session token
        self.role = None
        self.user_id = None
        self.username = None

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with API key and/or auth token"""
        headers = {"Content-Type": "application/json"}

        # Add API key if available
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        # Add auth token if logged in
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Login with username and password."""
        try:
            response = requests.post(
                f"{self.api_url}/auth/login",
                json={"username": username, "password": password},
                headers=self._get_headers(),
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
            response = requests.get(f"{self.api_url}/auth/health", headers=self._get_headers(), timeout=3)
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

    def get_switches(self, machine_id: str = None) -> Dict[str, Any]:
        """Get list of switches. Optionally filter by machine_id. Returns {"ok": bool, "data": list} or error dict."""
        try:
            url = f"{self.api_url}/switches/"
            params = {}
            if machine_id:
                params["machine_id"] = machine_id
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
        image_thresholded_path: str,
        zoom_level: float = None
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
                # Only send zoom when we actually have it, so old servers that
                # don't know the field simply ignore its absence.
                if zoom_level is not None:
                    data["zoom_level"] = zoom_level

                # For multipart uploads we must NOT force Content-Type:
                # application/json — requests sets the correct
                # "multipart/form-data; boundary=..." header itself. Keep only
                # the auth/API-key headers.
                upload_headers = {
                    k: v for k, v in self._get_headers().items()
                    if k.lower() != "content-type"
                }

                response = requests.post(
                    f"{self.api_url}/captures/upload",
                    data=data,
                    files=files,
                    headers=upload_headers,
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

    def get_capture_image(self, capture_id: str, kind: str = "original"):
        """Download a capture image from the server as raw bytes.

        kind = 'original' or 'thresholded'. Returns the image bytes on success,
        or None if it could not be fetched (caller can fall back to a local
        copy). This is what lets annoteur/admin machines see images that
        physically live on the server."""
        try:
            headers = {
                k: v for k, v in self._get_headers().items()
                if k.lower() != "content-type"
            }
            response = requests.get(
                f"{self.api_url}/captures/{capture_id}/image",
                params={"kind": kind},
                headers=headers,
                timeout=15,
            )
            if response.status_code == 200:
                return response.content
            return None
        except Exception:
            return None

    def get_capture_queue(self, annoteur_id: str) -> list:
        """Get captures assigned to this annoteur."""
        try:
            response = requests.get(
                f"{self.api_url}/captures/queue",
                params={"annoteur_id": annoteur_id},
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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

    def admin_get_switches(self, machine_id: str = None) -> Dict[str, Any]:
        """Get all switches, optionally filtered by machine_id."""
        try:
            params = {}
            if machine_id:
                params["machine_id"] = machine_id
            response = requests.get(
                f"{self.api_url}/admin/switches",
                params=params,
                headers=self._get_headers(),
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                error_type = classify_error(None, response)
                return {"ok": False, "error_type": error_type, "error": f"Failed to fetch switches", "details": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error_type": "server_down", "error": "Cannot connect to server", "details": str(e)}
        except requests.Timeout:
            return {"ok": False, "error_type": "server_down", "error": "Connection timeout", "details": "Server took too long to respond"}
        except Exception as e:
            return {"ok": False, "error_type": "unknown", "error": str(e), "details": str(e)}

    def admin_create_switch(self, machine_id: str, switch_name: str, expected_diameter_mm: float, tolerance_min: float, tolerance_max: float, cable_type: str) -> Dict[str, Any]:
        """Create a new switch for a specific machine."""
        try:
            data = {
                "machine_id": machine_id,
                "switch_name": switch_name,
                "expected_diameter_mm": expected_diameter_mm,
                "tolerance_min": tolerance_min,
                "tolerance_max": tolerance_max,
                "cable_type": cable_type
            }
            response = requests.post(
                f"{self.api_url}/admin/switches",
                json=data,
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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
                headers=self._get_headers(),
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

    def delete_notification(self, notification_id: str) -> Dict[str, Any]:
        """Delete a single notification by ID."""
        try:
            response = requests.delete(
                f"{self.api_url}/notifications/{notification_id}",
                headers=self._get_headers(),
                timeout=5
            )
            if response.status_code == 200:
                return {"ok": True}
            return {"ok": False, "error": response.text}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def submit_report(self, machine_name: str, title: str, description: str, category: str = "other") -> Dict[str, Any]:
        """Submit an issue report from the machine panel to the admin notifications."""
        try:
            response = requests.post(
                f"{self.api_url}/notifications/report",
                json={
                    "machine_name": machine_name,
                    "title": title,
                    "description": description,
                    "category": category,
                },
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return {"ok": True, "data": result}
                return {"ok": False, "error": result.get("error", "Failed to submit report")}
            return {"ok": False, "error": response.text}
        except requests.ConnectionError as e:
            return {"ok": False, "error": "Cannot connect to server", "details": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_model_update_notifications(self, download_link: str, models: str = "MESURE, STATE", notification_type: str = "info") -> Dict[str, Any]:
        """Send model update notifications to all active machines.

        Args:
            download_link: The download link for the model
            models: Description of models being updated
            notification_type: Type of notification (mesure-upload, state-upload, or info)
        """
        try:
            response = requests.post(
                f"{self.api_url}/notifications/send-models",
                json={
                    "download_link": download_link,
                    "models": models,
                    "notification_type": notification_type
                },
                headers=self._get_headers(),
                timeout=10
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json()}
            else:
                return {"ok": False, "error": response.json().get("error", "Failed to send notifications")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ==================== GENERIC HTTP METHODS ====================

    def get(self, path: str, params: Dict = None) -> Any:
        """Generic GET request."""
        try:
            url = f"{self.api_url}{path}" if path.startswith('/') else f"{self.api_url}/{path}"
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"GET error: {e}")
            return None

    def put(self, path: str, data: Dict) -> Any:
        """Generic PUT request.

        Raises RuntimeError on any non-2xx response (or network failure) so a
        caller can never mistake a server-side rejection for success. The
        exception message carries the server's error detail when available.
        Callers are expected to wrap this in try/except.
        """
        url = f"{self.api_url}{path}" if path.startswith('/') else f"{self.api_url}/{path}"
        try:
            response = requests.put(
                url,
                json=data,
                headers=self._get_headers(),
                timeout=5
            )
        except Exception as e:
            raise RuntimeError(f"Could not reach server: {e}")

        if response.status_code in [200, 201]:
            return response.json()

        # Non-2xx: surface the server's error detail instead of swallowing it.
        detail = None
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = (response.text or "").strip()
        raise RuntimeError(detail or f"HTTP {response.status_code}")
