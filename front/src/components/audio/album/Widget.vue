<template>
  <div class="wrapper">
    <h3 class="ui header">
      <slot name="title"></slot>
    </h3>
    <i @click="fetchData(previousPage)" :disabled="!previousPage" :class="['ui', {disabled: !previousPage}, 'circular', 'medium', 'angle left', 'icon']">
    </i>
    <i @click="fetchData(nextPage)" :disabled="!nextPage" :class="['ui', {disabled: !nextPage}, 'circular', 'medium', 'angle right', 'icon']">
    </i>
    <div class="ui hidden divider"></div>
    <div class="ui five cards">
      <div v-if="isLoading" class="ui inverted active dimmer">
        <div class="ui loader"></div>
      </div>
      <div class="card" v-for="album in albums" :key="album.id">
        <div :class="['ui', 'image', 'with-overlay', {'default-cover': !album.cover.original}]" :style="getImageStyle(album)">
          <play-button class="play-overlay" :icon-only="true" :is-playable="album.is_playable" :button-classes="['ui', 'circular', 'large', 'orange', 'icon', 'button']" :album="album.id"></play-button>
        </div>
        <div class="content">
          <router-link :title="album.title" :to="{name: 'library.albums.detail', params: {id: album.id}}">
            {{ album.title|truncate(25) }}
          </router-link>
          <div class="description">
            <span>
              <router-link :title="album.artist.name" class="discrete link" :to="{name: 'library.artists.detail', params: {id: album.artist.id}}">
                {{ album.artist.name|truncate(23) }}
              </router-link>
            </span>
          </div>
        </div>
        <div class="extra content">
          <human-date class="left floated" :date="album.creation_date"></human-date>
          <play-button class="right floated basic icon" :dropdown-only="true" :is-playable="album.is_playable" :dropdown-icon-classes="['ellipsis', 'horizontal', 'large', 'grey']" :album="album.id"></play-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import _ from 'lodash'
import axios from 'axios'
import PlayButton from '@/components/audio/PlayButton'

export default {
  props: {
    filters: {type: Object, required: true}
  },
  components: {
    PlayButton
  },
  data () {
    return {
      albums: [],
      limit: 12,
      isLoading: false,
      errors: null,
      previousPage: null,
      nextPage: null
    }
  },
  created () {
    this.fetchData('albums/')
  },
  methods: {
    fetchData (url) {
      if (!url) {
        return
      }
      this.isLoading = true
      let self = this
      let params = _.clone(this.filters)
      params.page_size = this.limit
      params.offset = this.offset
      axios.get(url, {params: params}).then((response) => {
        self.previousPage = response.data.previous
        self.nextPage = response.data.next
        self.isLoading = false
        self.albums = response.data.results
      }, error => {
        self.isLoading = false
        self.errors = error.backendErrors
      })
    },
    updateOffset (increment) {
      if (increment) {
        this.offset += this.limit
      } else {
        this.offset = Math.max(this.offset - this.limit, 0)
      }
    },
    getImageStyle (album) {
      let url = '../../../assets/audio/default-cover.png'

      if (album.cover.original) {
        url = this.$store.getters['instance/absoluteUrl'](album.cover.medium_square_crop)
      } else {
        return {}
      }
      return {
        'background-image': `url("${url}")`
      }
    }
  },
  watch: {
    offset () {
      this.fetchData()
    }
  }
}
</script>
<style scoped lang="scss">
@import '../../../style/vendor/media';

.default-cover {
  background-image: url('../../../assets/audio/default-cover.png') !important;
}

.wrapper {
  width: 100%;
}
.ui.cards {
  justify-content: flex-start;
}
.ui.five.cards > .card {
  width: 15em;
}
.with-overlay {
  background-size: cover !important;
  background-position: center !important;
  height: 15em;
  width: 15em;
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
}
</style>
<style>
.ui.cards .ui.button {
  margin-right: 0px;
}
</style>
