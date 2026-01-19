<template>
  <div class="max-w-4xl mx-auto">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900 mb-2">Mon profil</h1>
      <p class="text-gray-600">Gérez vos informations personnelles et votre localisation</p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      <span class="ml-2 text-gray-600">Chargement du profil...</span>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <div class="flex">
        <ExclamationTriangleIcon class="h-5 w-5 text-red-400 mt-0.5" />
        <div class="ml-3">
          <h3 class="text-sm font-medium text-red-800">Erreur de chargement</h3>
          <p class="text-sm text-red-700 mt-1">{{ error }}</p>
          <button 
            @click="loadProfile" 
            class="mt-2 text-sm text-red-800 underline hover:text-red-900"
          >
            Réessayer
          </button>
        </div>
      </div>
    </div>

    <!-- Profile content -->
    <div v-else-if="profile" class="space-y-6">
      <!-- Informations personnelles -->
      <div class="bg-white rounded-lg border border-gray-200 p-6">
        <h3 class="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <UserCircleIcon class="h-5 w-5 mr-2 text-gray-600" />
          Informations personnelles
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-500 mb-1">
              Nom d'utilisateur
            </label>
            <p class="text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded">{{ profile.username }}</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-500 mb-1">
              Adresse e-mail
            </label>
            <p class="text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded">{{ profile.email }}</p>
          </div>
        </div>
      </div>

      <!-- Localisation -->
      <div class="bg-white rounded-lg border border-gray-200 p-6">
        <h3 class="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <MapPinIcon class="h-5 w-5 mr-2 text-gray-600" />
          Ma localisation
        </h3>
        
        <!-- Message d'information -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <div class="flex">
            <InformationCircleIcon class="h-5 w-5 text-blue-400 mt-0.5" />
            <div class="ml-3">
              <p class="text-sm text-blue-700">
                Votre localisation sert de point de référence pour les calculs de distance dans vos challenges.
                Elle reste privée et n'est visible que par vous.
              </p>
            </div>
          </div>
        </div>

        <!-- Localisation actuelle -->
        <div v-if="hasLocation" class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div class="flex items-center">
            <CheckCircleIcon class="h-5 w-5 text-green-400 mr-2" />
            <div>
              <p class="text-sm font-medium text-green-800">Localisation configurée</p>
              <p class="text-sm text-green-600">{{ locationString }}</p>
            </div>
          </div>
        </div>

        <div v-else class="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div class="flex items-center">
            <ExclamationTriangleIcon class="h-5 w-5 text-yellow-400 mr-2" />
            <div>
              <p class="text-sm font-medium text-yellow-800">Aucune localisation configurée</p>
              <p class="text-sm text-yellow-600">Définissez votre position pour améliorer vos challenges</p>
            </div>
          </div>
        </div>

        <!-- Formulaire de localisation -->
        <form @submit.prevent="handleLocationSubmit" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label for="latitude" class="block text-sm font-medium text-gray-700 mb-1">
                Latitude *
              </label>
              <input
                id="latitude"
                v-model="locationForm.lat"
                type="number"
                step="any"
                min="-90"
                max="90"
                placeholder="Ex: 46.603354"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                :class="{ 'border-red-300': locationFormErrors.lat }"
              />
              <p v-if="locationFormErrors.lat" class="mt-1 text-sm text-red-600">
                {{ locationFormErrors.lat }}
              </p>
            </div>
            <div>
              <label for="longitude" class="block text-sm font-medium text-gray-700 mb-1">
                Longitude *
              </label>
              <input
                id="longitude"
                v-model="locationForm.lon"
                type="number"
                step="any"
                min="-180"
                max="180"
                placeholder="Ex: 1.888334"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                :class="{ 'border-red-300': locationFormErrors.lon }"
              />
              <p v-if="locationFormErrors.lon" class="mt-1 text-sm text-red-600">
                {{ locationFormErrors.lon }}
              </p>
            </div>
          </div>

          <!-- Boutons d'action -->
          <div class="flex items-center space-x-3">
            <button
              type="submit"
              :disabled="saving"
              class="flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="saving" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
              {{ saving ? 'Sauvegarde...' : 'Sauvegarder' }}
            </button>
            
            <button
              type="button"
              @click="getCurrentLocation"
              :disabled="gettingLocation"
              class="flex items-center px-4 py-2 bg-gray-600 text-white text-sm font-medium rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span v-if="gettingLocation" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></span>
              <LocateFixed v-else class="h-4 w-4 mr-2" />
              {{ gettingLocation ? 'Localisation...' : 'Ma position actuelle' }}
            </button>

            <button
              v-if="hasLocation"
              type="button"
              @click="clearLocation"
              class="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500"
            >
              Supprimer
            </button>
          </div>

          <!-- Erreur de sauvegarde -->
          <div v-if="saveError" class="bg-red-50 border border-red-200 rounded-lg p-3">
            <div class="flex">
              <ExclamationTriangleIcon class="h-4 w-4 text-red-400 mt-0.5" />
              <p class="ml-2 text-sm text-red-700">{{ saveError }}</p>
            </div>
          </div>

          <!-- Message de succès -->
          <div v-if="showSuccessMessage" class="bg-green-50 border border-green-200 rounded-lg p-3">
            <div class="flex">
              <CheckCircleIcon class="h-4 w-4 text-green-400 mt-0.5" />
              <p class="ml-2 text-sm text-green-700">Localisation mise à jour avec succès !</p>
            </div>
          </div>
        </form>

        <!-- Aide -->
        <div class="mt-6 text-xs text-gray-500">
          <p><strong>Formats acceptés :</strong> Degrés décimaux (DD). Exemples :</p>
          <ul class="mt-1 ml-4 space-y-1">
            <li>• Paris : 48.8566, 2.3522</li>
            <li>• Toulouse : 43.6047, 1.4442</li>
            <li>• Lyon : 45.7640, 4.8357</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { useUserProfile } from '@/composables/useUserProfile'
import {
  UserCircleIcon,
  MapPinIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon
} from '@heroicons/vue/24/outline'
import { LocateFixed } from 'lucide-vue-next'
import type { UserLocationIn } from '@/types/index'

const { 
  profile, 
  location, 
  loading, 
  error, 
  saving, 
  saveError, 
  loadProfile, 
  updateLocation, 
  hasLocation, 
  locationString 
} = useUserProfile()

// Formulaire de localisation
const locationForm = reactive({
  lat: null as number | null,
  lon: null as number | null
})

const locationFormErrors = reactive({
  lat: '',
  lon: ''
})

const gettingLocation = ref(false)
const showSuccessMessage = ref(false)

// Validation du formulaire
function validateLocationForm(): boolean {
  locationFormErrors.lat = ''
  locationFormErrors.lon = ''
  
  let isValid = true
  
  if (locationForm.lat === null || locationForm.lat === undefined) {
    locationFormErrors.lat = 'La latitude est obligatoire'
    isValid = false
  } else if (locationForm.lat < -90 || locationForm.lat > 90) {
    locationFormErrors.lat = 'La latitude doit être entre -90 et 90'
    isValid = false
  }
  
  if (locationForm.lon === null || locationForm.lon === undefined) {
    locationFormErrors.lon = 'La longitude est obligatoire'
    isValid = false
  } else if (locationForm.lon < -180 || locationForm.lon > 180) {
    locationFormErrors.lon = 'La longitude doit être entre -180 et 180'
    isValid = false
  }
  
  return isValid
}

// Soumission du formulaire
async function handleLocationSubmit() {
  if (!validateLocationForm()) return
  
  const locationData: UserLocationIn = {
    lat: locationForm.lat,
    lon: locationForm.lon
  }
  
  try {
    await updateLocation(locationData)
    showSuccessMessage.value = true
    setTimeout(() => {
      showSuccessMessage.value = false
    }, 3000)
  } catch (err) {
    // Erreur gérée par le composable
  }
}

// Géolocalisation
function getCurrentLocation() {
  if (!navigator.geolocation) {
    alert('La géolocalisation n\'est pas supportée par votre navigateur')
    return
  }
  
  gettingLocation.value = true
  
  navigator.geolocation.getCurrentPosition(
    (position) => {
      locationForm.lat = Math.round(position.coords.latitude * 1000000) / 1000000
      locationForm.lon = Math.round(position.coords.longitude * 1000000) / 1000000
      gettingLocation.value = false
    },
    (err) => {
      console.error('Erreur de géolocalisation:', err)
      alert('Impossible d\'obtenir votre position. Vérifiez les autorisations de votre navigateur.')
      gettingLocation.value = false
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0
    }
  )
}

// Supprimer la localisation
async function clearLocation() {
  if (!confirm('Êtes-vous sûr de vouloir supprimer votre localisation ?')) return
  
  const locationData: UserLocationIn = {
    lat: null,
    lon: null
  }
  
  try {
    await updateLocation(locationData)
    locationForm.lat = null
    locationForm.lon = null
    showSuccessMessage.value = true
    setTimeout(() => {
      showSuccessMessage.value = false
    }, 3000)
  } catch (err) {
    // Erreur gérée par le composable
  }
}

// Initialisation
function initializeForm() {
  if (location.value) {
    locationForm.lat = location.value.lat
    locationForm.lon = location.value.lon
  }
}

onMounted(async () => {
  await loadProfile()
  initializeForm()
})
</script>