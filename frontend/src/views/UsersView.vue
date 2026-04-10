<template>
  <div>
    <div class="d-flex align-center mb-5">
      <div class="text-h5 font-weight-bold">Users</div>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreate">Add User</v-btn>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-4">{{ error }}</v-alert>

    <v-card rounded="lg" elevation="1">
      <v-card-text class="pa-0">
        <v-data-table-server
          v-model:options="tableOptions"
          :headers="headers"
          :items="users"
          :items-length="total"
          :loading="loading"
          item-value="id"
          density="comfortable"
          @update:options="onTableOptions"
        >
          <template #item.auth_type="{ item }">
            <v-chip
              :color="item.auth_type === 'django' ? 'primary' : 'secondary'"
              size="small"
              variant="tonal"
            >
              {{ item.auth_type === 'django' ? 'Local' : 'SSO' }}
            </v-chip>
          </template>

          <template #item.is_active="{ item }">
            <v-icon :color="item.is_active ? 'success' : 'error'" size="18">
              {{ item.is_active ? 'mdi-check-circle' : 'mdi-close-circle' }}
            </v-icon>
          </template>

          <template #item.is_staff="{ item }">
            <v-icon v-if="item.is_staff" color="primary" size="18">mdi-shield-check</v-icon>
            <span v-else class="text-medium-emphasis">—</span>
          </template>

          <template #item.is_superuser="{ item }">
            <v-icon v-if="item.is_superuser" color="warning" size="18">mdi-shield-crown</v-icon>
            <span v-else class="text-medium-emphasis">—</span>
          </template>

          <template #item.last_login="{ item }">
            <span class="text-medium-emphasis text-caption">
              {{ item.last_login ? formatDate(item.last_login) : 'Never' }}
            </span>
          </template>

          <template #item.actions="{ item }">
            <v-btn icon="mdi-pencil" size="small" variant="text" @click="openEdit(item)" />
            <v-btn
              icon="mdi-delete"
              size="small"
              variant="text"
              color="error"
              :disabled="item.id === currentUserId"
              @click="confirmDelete(item)"
            />
          </template>
        </v-data-table-server>
      </v-card-text>
    </v-card>

    <!-- Add / Edit dialog -->
    <v-dialog v-model="dialog" max-width="520" persistent>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pt-4 px-4">
          {{ editing ? 'Edit User' : 'Add User' }}
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="dialog = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pt-4">
          <v-alert v-if="formError" type="error" variant="tonal" density="compact" class="mb-4">
            {{ formError }}
          </v-alert>

          <v-text-field
            v-model="form.username"
            label="Username"
            :disabled="!!editing"
            class="mb-2"
          />
          <v-row dense>
            <v-col cols="6">
              <v-text-field v-model="form.first_name" label="First Name" />
            </v-col>
            <v-col cols="6">
              <v-text-field v-model="form.last_name" label="Last Name" />
            </v-col>
          </v-row>
          <v-text-field v-model="form.email" label="Email" type="email" class="mb-2" />

          <!-- Password — only for local users -->
          <template v-if="!editing || editing.auth_type === 'django'">
            <v-text-field
              v-model="form.password"
              :label="editing ? 'New Password (leave blank to keep current)' : 'Password'"
              type="password"
              autocomplete="new-password"
              class="mb-2"
            />
          </template>
          <v-alert
            v-else
            type="info"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            Password is managed by the external SSO provider and cannot be changed here.
          </v-alert>

          <v-divider class="my-3" />
          <div class="text-caption text-medium-emphasis mb-2">Permissions</div>

          <div class="d-flex align-center justify-space-between py-1">
            <div>
              <div class="text-body-2">Active</div>
              <div class="text-caption text-medium-emphasis">
                User can log in. Disable instead of deleting to preserve audit history.
              </div>
            </div>
            <v-switch v-model="form.is_active" color="primary" hide-details density="compact" class="ml-4 flex-grow-0" />
          </div>

          <v-divider class="my-1" />

          <div class="d-flex align-center justify-space-between py-1">
            <div>
              <div class="text-body-2">Staff <span class="text-caption text-medium-emphasis">(Admin)</span></div>
              <div class="text-caption text-medium-emphasis">
                Can create, edit, and delete devices, scripts, policies, baselines, and users.
                Read-only users without this flag can view data and acknowledge drift.
              </div>
            </div>
            <v-switch v-model="form.is_staff" color="primary" hide-details density="compact" class="ml-4 flex-grow-0" />
          </div>

          <v-divider class="my-1" />

          <div class="d-flex align-center justify-space-between py-1">
            <div>
              <div class="text-body-2">Superuser</div>
              <div class="text-caption text-medium-emphasis">
                Bypasses all permission checks. Also grants access to the Django admin interface.
                Reserve for break-glass accounts only.
              </div>
            </div>
            <v-switch v-model="form.is_superuser" color="warning" hide-details density="compact" class="ml-4 flex-grow-0" />
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="px-4 py-3">
          <v-spacer />
          <v-btn variant="text" @click="dialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="saving" @click="save">
            {{ editing ? 'Save' : 'Create' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete confirmation -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card rounded="lg">
        <v-card-title class="pt-4 px-4">Delete User</v-card-title>
        <v-card-text>
          Are you sure you want to delete <strong>{{ deletingUser?.username }}</strong>?
          This cannot be undone.
        </v-card-text>
        <v-card-actions class="px-4 pb-3">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Cancel</v-btn>
          <v-btn color="error" :loading="deleting" @click="deleteUser">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const headers = [
  { title: 'Username', key: 'username', sortable: true },
  { title: 'Name', key: 'first_name', value: item => [item.first_name, item.last_name].filter(Boolean).join(' ') || '—' },
  { title: 'Email', key: 'email', value: item => item.email || '—' },
  { title: 'Type', key: 'auth_type', sortable: false },
  { title: 'Active', key: 'is_active', sortable: true },
  { title: 'Staff', key: 'is_staff', sortable: true },
  { title: 'Superuser', key: 'is_superuser', sortable: true },
  { title: 'Last Login', key: 'last_login', sortable: true },
  { title: '', key: 'actions', sortable: false, align: 'end' },
]

const tableOptions = ref({ page: 1, itemsPerPage: 20, sortBy: [] })
const total = ref(0)
const users = ref([])
const loading = ref(false)
const error = ref('')

const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const formError = ref('')
const form = ref(emptyForm())

const deleteDialog = ref(false)
const deletingUser = ref(null)
const deleting = ref(false)

const currentUserId = ref(null)

function emptyForm() {
  return {
    username: '',
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    is_active: true,
    is_staff: false,
    is_superuser: false,
  }
}

function formatDate(iso) {
  return new Date(iso).toLocaleString()
}

async function load(options = tableOptions.value) {
  loading.value = true
  error.value = ''
  try {
    const params = { page: options.page, page_size: options.itemsPerPage }
    if (options.sortBy?.length) {
      const { key, order } = options.sortBy[0]
      params.ordering = order === 'desc' ? `-${key}` : key
    }
    const { data } = await api.get('/users/', { params })
    users.value = data.results ?? data
    total.value = data.count ?? users.value.length
  } catch {
    error.value = 'Failed to load users.'
  } finally {
    loading.value = false
  }
}

function onTableOptions(options) {
  tableOptions.value = options
  load(options)
}

function openCreate() {
  editing.value = null
  form.value = emptyForm()
  formError.value = ''
  dialog.value = true
}

function openEdit(user) {
  editing.value = user
  form.value = {
    username: user.username,
    first_name: user.first_name,
    last_name: user.last_name,
    email: user.email,
    password: '',
    is_active: user.is_active,
    is_staff: user.is_staff,
    is_superuser: user.is_superuser,
  }
  formError.value = ''
  dialog.value = true
}

async function save() {
  saving.value = true
  formError.value = ''
  try {
    const payload = { ...form.value }
    if (!payload.password) delete payload.password

    if (editing.value) {
      await api.patch(`/users/${editing.value.id}/`, payload)
    } else {
      await api.post('/users/', payload)
    }
    dialog.value = false
    load()
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      formError.value = Object.entries(data)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
        .join(' | ')
    } else {
      formError.value = 'Save failed.'
    }
  } finally {
    saving.value = false
  }
}

function confirmDelete(user) {
  deletingUser.value = user
  deleteDialog.value = true
}

async function deleteUser() {
  deleting.value = true
  try {
    await api.delete(`/users/${deletingUser.value.id}/`)
    deleteDialog.value = false
    load()
  } catch {
    error.value = 'Delete failed.'
    deleteDialog.value = false
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  // Identify the logged-in user so we can disable self-delete.
  try {
    const { data } = await api.get('/users/?search=' + (localStorage.getItem('username') || ''))
    const me = (data.results ?? data).find(u => u.username === localStorage.getItem('username'))
    if (me) currentUserId.value = me.id
  } catch { /* ignore */ }
  load()
})
</script>
