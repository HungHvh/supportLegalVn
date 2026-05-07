export function getApiBaseUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (baseUrl && baseUrl.length > 0) {
    return baseUrl.replace(/\/$/, "");
  }

  if (process.env.NODE_ENV === "production") {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is required in production");
  }

  return "http://localhost:8000";
}

export function buildApiUrl(path: string) {
  return new URL(path, getApiBaseUrl()).toString();
}

