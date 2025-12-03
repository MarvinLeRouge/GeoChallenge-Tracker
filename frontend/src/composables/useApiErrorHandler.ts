// src/composables/useApiErrorHandler.ts
import { ref } from 'vue';
import { isAxiosError, type AxiosError } from 'axios';

export interface ApiError {
  status?: number;
  message: string;
  detail?: string;
}

export function useApiErrorHandler() {
  const error = ref<string>('');

  const handleApiError = (e: unknown): ApiError => {
    let apiError: ApiError = { message: 'Erreur inconnue' };

    if (isAxiosError(e)) {
      const axiosError = e as AxiosError;
      
      if (axiosError.response) {
        // HTTP error with response
        const status = axiosError.response.status;
        const detail = (axiosError.response.data as { detail?: string } | undefined)?.detail;

        apiError = {
          status,
          message: detail || `Erreur ${status}`,
          detail
        };
      } else if (axiosError.request) {
        // Network error
        apiError = {
          message: 'Erreur réseau - impossible de contacter le serveur'
        };
      } else {
        // Request config error
        apiError = {
          message: axiosError.message || 'Erreur de configuration de la requête'
        };
      }
    } else {
      // Non-Axios error
      apiError = {
        message: (e as Error)?.message || 'Erreur inconnue'
      };
    }

    // Store error message for UI display
    error.value = apiError.detail || apiError.message;

    return apiError;
  };

  const clearError = () => {
    error.value = '';
  };

  return {
    error,
    handleApiError,
    clearError
  };
}