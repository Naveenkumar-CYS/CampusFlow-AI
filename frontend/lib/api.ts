// Central API client. Every network call in the app goes through
// `apiFetch` — do not add a second fetch utility elsewhere.

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("access_token")
      : null;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });
  } catch {
    // Network failure (backend unreachable, CORS, offline, etc.) — distinct
    // from an HTTP error status, but callers just need a message either way.
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }

  if (!response.ok) {
    let message = "";
    try {
      const body = await response.json();
      message = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    } catch {
      message = await response.text().catch(() => "");
    }
    throw new ApiError(response.status, message || `Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}
