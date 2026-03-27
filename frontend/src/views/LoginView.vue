<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <h1 class="login-title">IsotopeIQ Satellite</h1>
      <p v-if="error" class="error" style="margin-bottom:.75rem">{{ error }}</p>
      <label>
        Username
        <input v-model="username" autocomplete="username" required />
      </label>
      <label style="margin-top:.75rem">
        Password
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <button type="submit" :disabled="loading" style="margin-top:1.25rem;width:100%">
        {{ loading ? 'Signing in…' : 'Sign In' }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await axios.post('/api/token/', {
      username: username.value,
      password: password.value,
    })
    localStorage.setItem('access_token', data.access)
    localStorage.setItem('refresh_token', data.refresh)
    router.push('/')
  } catch {
    error.value = 'Invalid username or password.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
}
.login-card {
  background: #fff;
  border-radius: 8px;
  padding: 2rem;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 2px 8px rgba(0,0,0,.12);
}
.login-title {
  margin-bottom: 1.5rem;
  font-size: 1.4rem;
}
</style>
