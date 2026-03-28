<template>
  <v-main style="background: #f0f2f5">
    <v-container fluid class="fill-height">
      <v-row justify="center" align="center" class="fill-height">
        <v-col cols="12" sm="5" md="4" lg="3">
          <v-card elevation="2" rounded="lg" class="pa-6">
            <div class="text-center mb-6">
              <v-icon color="primary" size="40">mdi-hexagon-outline</v-icon>
              <div class="text-h6 font-weight-bold mt-2">IsotopeIQ Satellite</div>
            </div>

            <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-4">
              {{ error }}
            </v-alert>

            <v-form @submit.prevent="submit">
              <v-text-field
                v-model="username"
                label="Username"
                prepend-inner-icon="mdi-account-outline"
                autocomplete="username"
                class="mb-3"
              />
              <v-text-field
                v-model="password"
                label="Password"
                type="password"
                prepend-inner-icon="mdi-lock-outline"
                autocomplete="current-password"
                class="mb-4"
              />
              <v-btn
                type="submit"
                color="primary"
                block
                size="large"
                :loading="loading"
              >
                Sign In
              </v-btn>
            </v-form>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </v-main>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { setTokens } from '../api'

const router   = useRouter()
const username = ref('')
const password = ref('')
const loading  = ref(false)
const error    = ref('')

async function submit() {
  error.value   = ''
  loading.value = true
  try {
    const { data } = await axios.post('/api/token/', {
      username: username.value,
      password: password.value,
    })
    setTokens(data.access, data.refresh, username.value)
    router.push('/')
  } catch {
    error.value = 'Invalid username or password.'
  } finally {
    loading.value = false
  }
}
</script>
