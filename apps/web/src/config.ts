// Configuration for UAR Web Application
export const config = {
  // API endpoint configuration
  api: {
    // Default to current origin for development, can be overridden by environment
    baseUrl: (() => {
      // Check if we're in a browser environment
      if (typeof window !== 'undefined') {
        return import.meta.env.VITE_API_BASE_URL || window.location.origin
      }
      // For Node.js/testing environment
      return 'http://localhost:8000'
    })(),
    streamEndpoint: '/api/uar/stream',
    runsEndpoint: '/api/uar/runs'
  }
}

// Helper function to construct full API URLs
export const getApiUrl = (endpoint: string) => {
  const baseUrl = config.api.baseUrl.endsWith('/') ? config.api.baseUrl.slice(0, -1) : config.api.baseUrl
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  return `${baseUrl}${cleanEndpoint}`
}
