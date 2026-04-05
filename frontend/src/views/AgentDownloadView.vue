<template>
  <v-container max-width="700" class="py-8">
    <div class="text-h5 font-weight-bold mb-1">Download Agent</div>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Download the installer bundle for your OS. The bundle includes the agent binary
      and the installer script — extract and run.
    </p>
    <v-alert type="info" variant="tonal" density="compact" class="mb-6 text-body-2">
      <div class="font-weight-medium mb-1">Agents are optional</div>
      IsotopeIQ can collect from devices using SSH or WinRM scripts without installing anything.
      However, remote connectivity is often unreliable in practice — especially on Windows, where
      WinRM is disabled by default and enabling it typically requires opening firewall ports,
      relaxing execution policies, and sometimes disabling security controls. SSH on Windows is
      available but requires the OpenSSH service to be running and reachable.
      The agent avoids all of this: install it once and the satellite pulls from it directly over
      a plain HTTP connection on a port you control.
    </v-alert>

    <v-card rounded="lg">
      <v-card-text>
        <v-tabs v-model="os" density="compact" class="mb-5">
          <v-tab value="windows">Windows</v-tab>
          <v-tab value="linux">Linux</v-tab>
          <v-tab value="macos">macOS</v-tab>
        </v-tabs>

        <v-window v-model="os">
          <!-- Windows -->
          <v-window-item value="windows">
            <v-btn block color="primary" variant="tonal" prepend-icon="mdi-folder-zip"
              :loading="downloading" @click="download('windows')">
              Download isotopeiq-agent-windows.zip
            </v-btn>
            <p class="text-body-2 text-medium-emphasis mt-4 mb-1">
              Extract the ZIP, then run from an elevated command prompt:
            </p>
            <v-text-field model-value="windows_install.bat" readonly variant="outlined"
              density="compact" style="font-family:monospace"
              append-inner-icon="mdi-content-copy"
              @click:append-inner="copy('windows_install.bat')" />
            <p class="text-body-2 text-medium-emphasis mt-2 mb-0">
              The installer registers the agent as a Windows Scheduled Task running as SYSTEM,
              opens the firewall port, and starts the agent immediately.
            </p>
          </v-window-item>

          <!-- Linux -->
          <v-window-item value="linux">
            <v-btn block color="primary" variant="tonal" prepend-icon="mdi-folder-zip"
              :loading="downloading" @click="download('linux')">
              Download isotopeiq-agent-linux.zip
            </v-btn>
            <p class="text-body-2 text-medium-emphasis mt-4 mb-1">
              Extract the ZIP, then run as root:
            </p>
            <v-text-field model-value="sudo bash linux_install.sh" readonly variant="outlined"
              density="compact" style="font-family:monospace"
              append-inner-icon="mdi-content-copy"
              @click:append-inner="copy('sudo bash linux_install.sh')" />
            <p class="text-body-2 text-medium-emphasis mt-2 mb-0">
              The installer registers the agent as a systemd service and starts it immediately.
              Supports amd64 and i686.
            </p>
          </v-window-item>

          <!-- macOS -->
          <v-window-item value="macos">
            <v-btn block color="primary" variant="tonal" prepend-icon="mdi-folder-zip"
              :loading="downloading" @click="download('macos')">
              Download isotopeiq-agent-macos.zip
            </v-btn>
            <p class="text-body-2 text-medium-emphasis mt-4 mb-1">
              Extract the ZIP, then run as root:
            </p>
            <v-text-field model-value="sudo bash macos_install.sh" readonly variant="outlined"
              density="compact" style="font-family:monospace"
              append-inner-icon="mdi-content-copy"
              @click:append-inner="copy('sudo bash macos_install.sh')" />
            <p class="text-body-2 text-medium-emphasis mt-2 mb-0">
              The installer registers the agent as a launchd daemon and starts it immediately.
            </p>
          </v-window-item>
        </v-window>

        <v-divider class="my-5" />

        <v-expansion-panels variant="accordion">
          <v-expansion-panel title="Air-gapped devices">
            <v-expansion-panel-text>
              <p class="text-body-2 mb-3">
                If the device cannot reach this server, you can still collect a baseline manually
                and import it through the UI.
              </p>
              <ol class="text-body-2 pl-4 mb-3" style="line-height:2">
                <li>Copy the appropriate collector binary to the device (no installer needed).</li>
                <li>Run it without <code>--serve</code> to print the baseline JSON to stdout:</li>
              </ol>
              <v-text-field v-for="(cmd, label) in airgapCommands" :key="label"
                :label="label" :model-value="cmd" readonly variant="outlined" density="compact"
                style="font-family:monospace" class="mb-2"
                append-inner-icon="mdi-content-copy"
                @click:append-inner="copy(cmd)" />
              <ol class="text-body-2 pl-4 mb-3" style="line-height:2" start="3">
                <li>Save the output to a <code>.json</code> file and transfer it to a machine that can reach this server.</li>
                <li>In the <strong>Devices</strong> list, click <strong>Import</strong> on the target device and upload the file.</li>
              </ol>
              <p class="text-body-2 text-medium-emphasis mb-0">
                The import runs the same drift detection and baseline rules as a normal collection.
              </p>
            </v-expansion-panel-text>
          </v-expansion-panel>

        </v-expansion-panels>
      </v-card-text>
    </v-card>

    <v-snackbar v-model="snack.show" :color="snack.ok ? 'success' : 'error'" timeout="3000">
      {{ snack.text }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const os          = ref('windows')

const airgapCommands = {
  'Windows':        'windows_collector.exe > baseline.json',
  'Linux (amd64)':  './linux_collector_amd64 > baseline.json',
  'Linux (i686)':   './linux_collector_i686 > baseline.json',
  'macOS':          './macos_collector > baseline.json',
}
const downloading = ref(false)
const snack       = ref({ show: false, ok: true, text: '' })

function showSnack(ok, text) {
  snack.value = { show: true, ok, text }
}

function copy(text) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text)
  } else {
    const el = document.createElement('textarea')
    el.value = text
    Object.assign(el.style, { position: 'fixed', opacity: '0' })
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
  showSnack(true, 'Copied.')
}

async function download(osName) {
  downloading.value = true
  try {
    const { data } = await api.get('/devices/agent-bundle/', {
      params: { os: osName },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = `isotopeiq-agent-${osName}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch {
    showSnack(false, 'Download failed.')
  } finally {
    downloading.value = false
  }
}
</script>
