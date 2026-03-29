import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'

import App from './App.vue'
import router from './router'

const vuetify = createVuetify({
  components,
  directives,
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: { mdi },
  },
  theme: {
    defaultTheme: 'isotopeiq',
    themes: {
      isotopeiq: {
        dark: false,
        colors: {
          primary:    '#0288d1',
          secondary:  '#16213e',
          background: '#f0f2f5',
          surface:    '#ffffff',
          error:      '#fc8181',
          success:    '#28a745',
          warning:    '#ffc107',
          info:       '#17a2b8',
        },
      },
    },
  },
  defaults: {
    VBtn: { variant: 'elevated', size: 'small' },
    VTextField: { variant: 'outlined', density: 'compact', hideDetails: 'auto' },
    VSelect: { variant: 'outlined', density: 'compact', hideDetails: 'auto' },
    VTextarea: { variant: 'outlined', density: 'compact', hideDetails: 'auto' },
    VDataTable: { density: 'compact' },
  },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(vuetify)
app.mount('#app')
