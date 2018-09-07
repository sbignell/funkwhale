  <template>
  <div>
    <div class="ui hidden clearing divider"></div>
    <!-- <div v-if="files.length > 0" class="ui indicating progress">
      <div class="bar"></div>
      <div class="label">
        {{ uploadedFilesCount }}/{{ files.length }} files uploaded,
        {{ processedFilesCount }}/{{ processableFiles }} files processed
      </div>
    </div> -->
    <div class="ui form">
      <div class="fields">
        <div class="ui four wide field">
          <label><translate>Import reference</translate></label>
          <input type="text" v-model="importReference" />
        </div>
      </div>

    </div>
    <p><translate>This reference will be used to group imported files together.</translate></p>
    <div class="ui top attached tabular menu">
      <a :class="['item', {active: currentTab === 'uploads'}]" @click="currentTab = 'uploads'">
        <translate>Uploading</translate>
        <div v-if="files.length === 0" class="ui label">
          0
        </div>
        <div v-else-if="files.length > uploadedFilesCount + erroredFilesCount" class="ui yellow label">
          {{ uploadedFilesCount + erroredFilesCount }}/{{ files.length }}
        </div>
        <div v-else :class="['ui', {'green': erroredFilesCount === 0}, {'red': erroredFilesCount > 0}, 'label']">
          {{ uploadedFilesCount + erroredFilesCount }}/{{ files.length }}
        </div>
      </a>
      <a :class="['item', {active: currentTab === 'processing'}]" @click="currentTab = 'processing'">
        <translate>Processing</translate>
        <div v-if="processableFiles === 0" class="ui label">
          0
        </div>
        <div v-else-if="processableFiles > processedFilesCount" class="ui yellow label">
          {{ processedFilesCount }}/{{ processableFiles }}
        </div>
        <div v-else :class="['ui', {'green': trackFiles.errored === 0}, {'red': trackFiles.errored > 0}, 'label']">
          {{ processedFilesCount }}/{{ processableFiles }}
        </div>
      </a>
    </div>
    <div :class="['ui', 'bottom', 'attached', 'segment', {hidden: currentTab != 'uploads'}]">
      <div class="ui container">
        <file-upload-widget
          :class="['ui', 'icon', 'basic', 'button']"
          :post-action="uploadUrl"
          :multiple="true"
          :data="uploadData"
          :drop="true"
          accept="audio/*"
          v-model="files"
          name="audio_file"
          :thread="1"
          @input-filter="inputFilter"
          @input-file="inputFile"
          ref="upload">
          <i class="upload icon"></i>
          <translate>Click to select files to upload or drag and drop files or directories</translate>
        </file-upload-widget>
      </div>

      <table v-if="files.length > 0" class="ui single line table">
        <thead>
          <tr>
            <th><translate>File name</translate></th>
            <th><translate>Size</translate></th>
            <th><translate>Status</translate></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(file, index) in sortedFiles" :key="file.id">
            <td :title="file.name">{{ file.name | truncate(60) }}</td>
            <td>{{ file.size | humanSize }}</td>
            <td>
              <span v-if="file.error" class="ui tooltip" :data-tooltip="labels.tooltips[file.error]">
                <span class="ui red icon label">
                  <i class="question circle outline icon" /> {{ file.error }}
                </span>
              </span>
              <span v-else-if="file.success" class="ui green label">
                <translate key="1">Uploaded</translate>
              </span>
              <span v-else-if="file.active" class="ui yellow label">
                <translate key="2">Uploading...</translate>
              </span>
              <template v-else>
                <span class="ui label"><translate key="3">Pending</translate></span>
                <button class="ui tiny basic red icon button" @click.prevent="$refs.upload.remove(file)"><i class="delete icon"></i></button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>

    </div>
    <div :class="['ui', 'bottom', 'attached', 'segment', {hidden: currentTab != 'processing'}]">
      <library-files-table
        :key="String(processTimestamp)"
        :filters="{import_reference: importReference}"
        :custom-objects="Object.values(trackFiles.objects)"></library-files-table>
    </div>
  </div>
</template>

<script>
import $ from 'jquery'
import axios from 'axios'
import logger from '@/logging'
import FileUploadWidget from './FileUploadWidget'
import LibraryFilesTable from '@/views/content/libraries/FilesTable'
import moment from 'moment'
import { WebSocketBridge } from 'django-channels'

export default {
  props: ['library', 'defaultImportReference'],
  components: {
    FileUploadWidget,
    LibraryFilesTable
  },
  data () {
    let importReference = this.defaultImportReference || moment().format()
    this.$router.replace({query: {import: importReference}})
    return {
      files: [],
      currentTab: 'uploads',
      uploadUrl: '/api/v1/track-files/',
      importReference,
      trackFiles: {
        pending: 0,
        finished: 0,
        skipped: 0,
        errored: 0,
        objects: {},
      },
      bridge: null,
      processTimestamp: new Date()
    }
  },
  created () {
    this.openWebsocket()
    this.fetchStatus()
  },
  destroyed () {
    this.disconnect()
  },

  methods: {
    inputFilter (newFile, oldFile, prevent) {
      if (newFile && !oldFile) {
        let extension = newFile.name.split('.').pop()
        if (['ogg', 'mp3', 'flac'].indexOf(extension) < 0) {
          prevent()
        }
      }
    },
    inputFile (newFile, oldFile) {
      this.$refs.upload.active = true
    },
    fetchStatus () {
      let self = this
      let statuses = ['pending', 'errored', 'skipped', 'finished']
      statuses.forEach((status) => {
        axios.get('track-files/', {params: {import_reference: self.importReference, import_status: status, page_size: 1}}).then((response) => {
          self.trackFiles[status] = response.data.count
        })
      })
    },
    updateProgressBar () {
      $(this.$el).find('.progress').progress({
        total: this.files.length * 2,
        value: this.uploadedFilesCount + this.finishedJobs
      })
    },
    disconnect () {
      if (!this.bridge) {
        return
      }
      this.bridge.socket.close(1000, 'goodbye', {keepClosed: true})
    },
    openWebsocket () {
      this.disconnect()
      let self = this
      let token = this.$store.state.auth.token
      const bridge = new WebSocketBridge()
      this.bridge = bridge
      let url = this.$store.getters['instance/absoluteUrl'](`api/v1/activity?token=${token}`)
      url = url.replace('http://', 'ws://')
      url = url.replace('https://', 'wss://')
      bridge.connect(url)
      bridge.listen(function (event) {
        self.handleEvent(event)
      })
      bridge.socket.addEventListener('open', function () {
        console.log('Connected to WebSocket')
      })
    },
    handleEvent (event) {
      console.log('Received event', event.type, event)
      let self = this
      if (event.type === 'import.status_updated') {
        if (event.track_file.import_reference != self.importReference) {
          return
        }
        this.$nextTick(() => {
          self.trackFiles[event.old_status] -= 1
          self.trackFiles[event.new_status] += 1
          self.trackFiles.objects[event.track_file.uuid] = event.track_file
          self.triggerReload()
        })
      }
    },
    triggerReload: _.throttle(function () {
      this.processTimestamp = new Date()
    }, 10000, {'leading': true})
  },
  computed: {
    labels () {
      let denied = this.$gettext('Upload refused, ensure the file is not too big and you have not reached your quota')
      let server = this.$gettext('Impossible to upload this file, ensure it is not too big')
      let network = this.$gettext('A network error occured while uploading this file')
      let timeout = this.$gettext('Upload timeout, please try again')
      return {
        tooltips: {
          denied,
          server,
          network,
          timeout
        }
      }
    },
    uploadedFilesCount () {
      return this.files.filter((f) => {
        return f.success
      }).length
    },
    uploadingFilesCount () {
      return this.files.filter((f) => {
        return !f.success && !f.error
      }).length
    },
    erroredFilesCount () {
      return this.files.filter((f) => {
        return f.error
      }).length
    },
    processableFiles () {
      return this.trackFiles.pending + this.trackFiles.skipped + this.trackFiles.errored + this.trackFiles.finished + this.uploadedFilesCount
    },
    processedFilesCount () {
      return this.trackFiles.skipped + this.trackFiles.errored + this.trackFiles.finished
    },
    uploadData: function () {
      return {
        'library': this.library.uuid,
        'import_reference': this.importReference,
      }
    },
    sortedFiles () {
      // return errored files on top
      return this.files.sort((f) => {
        if (f.errored) {
          return -5
        }
        if (f.success) {
          return 5
        }
        return 0
      })
    }
  },
  watch: {
    uploadedFilesCount () {
      this.updateProgressBar()
    },
    finishedJobs () {
      this.updateProgressBar()
    },
    importReference: _.debounce(function () {
      this.$router.replace({query: {import: this.importReference}})
    }, 500)
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
.file-uploads.ui.button {
  display: block;
  padding: 2em 1em;
  width: 100%;
  box-shadow: none;
  border-style: dashed !important;
  border: 3px solid rgba(50, 50, 50, 0.5);
  font-size: 1.5em;
}
.segment.hidden {
  display: none;
}
</style>