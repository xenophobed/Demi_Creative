import axios, { AxiosError, AxiosInstance } from 'axios'
import type { ErrorResponse } from '@/types/api'

// API base configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// Create Axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60s timeout for story generation
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Can add auth token here
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error: AxiosError<ErrorResponse>) => {
    // Unified error handling
    if (error.response) {
      const errorData = error.response.data
      console.error('API Error:', errorData)

      // Handle different status codes
      switch (error.response.status) {
        case 400:
          // Bad request
          break
        case 413:
          // File too large
          break
        case 500:
          // Server error
          break
      }
    } else if (error.request) {
      // Network error
      console.error('Network Error:', error.message)
    }

    return Promise.reject(error)
  }
)

export default apiClient

// Utility function: get error message
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ErrorResponse>
    if (axiosError.response?.data?.message) {
      return axiosError.response.data.message
    }
    if (axiosError.message) {
      return axiosError.message
    }
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'An unknown error occurred, please try again later'
}
