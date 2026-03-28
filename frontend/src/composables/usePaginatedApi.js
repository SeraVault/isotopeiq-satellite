import { ref, computed, watch } from 'vue'
import api from '../api'

const PAGE_SIZE = 50

/**
 * Composable for server-side paginated + filtered API tables.
 *
 * @param {string} endpoint - API path, e.g. '/devices/'
 * @param {object} defaultFilters - reactive filter defaults
 * @returns { rows, loading, page, totalPages, totalCount, filters, fetch, goPage, resetFilters }
 */
export function usePaginatedApi(endpoint, defaultFilters = {}) {
  const rows        = ref([])
  const loading     = ref(false)
  const page        = ref(1)
  const totalCount  = ref(0)
  const totalPages  = computed(() => Math.max(1, Math.ceil(totalCount.value / PAGE_SIZE)))
  const filters     = ref({ ...defaultFilters })

  async function fetch() {
    loading.value = true
    try {
      const params = { page: page.value, page_size: PAGE_SIZE }
      for (const [k, v] of Object.entries(filters.value)) {
        if (v !== '' && v !== null && v !== undefined) params[k] = v
      }
      const { data } = await api.get(endpoint, { params })
      rows.value      = data.results ?? data
      totalCount.value = data.count  ?? rows.value.length
    } finally {
      loading.value = false
    }
  }

  function goPage(n) {
    page.value = n
    fetch()
  }

  function applyFilters() {
    page.value = 1
    fetch()
  }

  function resetFilters() {
    filters.value = { ...defaultFilters }
    page.value = 1
    fetch()
  }

  return { rows, loading, page, totalPages, totalCount, filters, fetch, goPage, applyFilters, resetFilters }
}
