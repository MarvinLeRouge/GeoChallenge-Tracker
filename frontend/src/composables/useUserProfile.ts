import { ref, computed } from 'vue'
import api from '@/api/http'
import type { UserProfileOut, UserLocationIn, UserLocationOut } from '@/types/index'

export function useUserProfile() {
  const profile = ref<UserProfileOut | null>(null)
  const location = ref<UserLocationOut | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const saving = ref(false)
  const saveError = ref<string | null>(null)

  const loadProfile = async () => {
    loading.value = true
    error.value = null
    
    try {
      // Charger le profil ET la location séparément
      const [profileResponse, locationResponse] = await Promise.all([
        api.get('/my/profile'),
        api.get('/my/profile/location').catch(() => ({ data: null })) // Si pas de location, ne pas échouer
      ])
      
      profile.value = profileResponse.data
      
      // Mapper la location depuis l'endpoint dédié
      if (locationResponse.data && locationResponse.data.lat !== null && locationResponse.data.lon !== null) {
        location.value = locationResponse.data
      } else {
        location.value = null
      }
    } catch (err: unknown) {
      console.error('Error loading user profile:', err)
      const errorMessage = err && typeof err === 'object' && 'response' in err 
        ? (err as any).response?.data?.detail || 'Erreur lors du chargement du profil'
        : 'Erreur lors du chargement du profil'
      error.value = errorMessage
    } finally {
      loading.value = false
    }
  }

  const loadLocation = async () => {
    loading.value = true
    error.value = null
    
    try {
      const response = await api.get('/my/profile/location')
      location.value = response.data
    } catch (err: unknown) {
      console.error('Error loading user location:', err)
      const errorMessage = err && typeof err === 'object' && 'response' in err 
        ? (err as any).response?.data?.detail || 'Erreur lors du chargement de la localisation'
        : 'Erreur lors du chargement de la localisation'
      error.value = errorMessage
    } finally {
      loading.value = false
    }
  }

  const updateProfile = async (profileData: Partial<UserProfileOut>) => {
    saving.value = true
    saveError.value = null
    
    try {
      const response = await api.put('/my/profile', profileData)
      profile.value = response.data
      return response.data
    } catch (err: unknown) {
      console.error('Error updating user profile:', err)
      const errorMessage = err && typeof err === 'object' && 'response' in err 
        ? (err as any).response?.data?.detail || 'Erreur lors de la mise à jour du profil'
        : 'Erreur lors de la mise à jour du profil'
      saveError.value = errorMessage
      throw err
    } finally {
      saving.value = false
    }
  }

  const updateLocation = async (locationData: UserLocationIn) => {
    saving.value = true
    saveError.value = null
    
    try {
      await api.put('/my/profile/location', locationData)
      
      // PUT renvoie seulement un message de succès, donc on recharge toujours
      // les données complètes depuis GET /my/profile/location
      const refreshResponse = await api.get('/my/profile/location')
      location.value = refreshResponse.data
      
      // Mettre à jour le profil complet si il est chargé
      if (profile.value) {
        profile.value.location = location.value
      }
      return location.value
    } catch (err: unknown) {
      console.error('Error updating user location:', err)
      const errorMessage = err && typeof err === 'object' && 'response' in err 
        ? (err as any).response?.data?.detail || 'Erreur lors de la mise à jour de la localisation'
        : 'Erreur lors de la mise à jour de la localisation'
      saveError.value = errorMessage
      throw err
    } finally {
      saving.value = false
    }
  }

  // Computed properties utiles
  const hasLocation = computed(() => {
    return location.value && 
           location.value.lat !== null && 
           location.value.lon !== null
  })

  const locationString = computed(() => {
    if (!hasLocation.value || !location.value) return null
    // Utiliser le format coords du backend si disponible, sinon fallback sur les coordonnées brutes
    if (location.value.coords) {
      // Convertir "N43 06.628 E5 56.557" en "N 43° 06.628′ E 5° 56.557′"
      return location.value.coords
        .replace(/N(\d+)\s+(\d+\.\d+)/g, 'N $1° $2′')
        .replace(/E(\d+)\s+(\d+\.\d+)/g, 'E $1° $2′')
    }
    // Fallback sur coordonnées décimales
    return `${location.value.lat?.toFixed(6)}, ${location.value.lon?.toFixed(6)}`
  })

  return {
    // State
    profile,
    location,
    loading,
    error,
    saving,
    saveError,
    
    // Actions
    loadProfile,
    loadLocation,
    updateProfile,
    updateLocation,
    
    // Computed
    hasLocation,
    locationString
  }
}