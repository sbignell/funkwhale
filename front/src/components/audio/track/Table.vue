<template>
  <table class="ui compact very basic fixed single line unstackable table">
    <thead>
      <tr>
        <th></th>
        <th></th>
        <th colspan="6"><translate>Title</translate></th>
        <th colspan="4"><translate>Artist</translate></th>
        <th colspan="4"><translate>Album</translate></th>
        <th colspan="4"><translate>Duration</translate></th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      <track-row
        :display-position="displayPosition"
        :track="track"
        :artist="artist"
        :key="index + '-' + track.id"
        v-for="(track, index) in tracks"></track-row>
    </tbody>
  </table>
</template>

<script>
import backend from '@/audio/backend'

import TrackRow from '@/components/audio/track/Row'
import Modal from '@/components/semantic/Modal'

export default {
  props: {
    tracks: {type: Array, required: true},
    artist: {type: Object, required: false},
    displayPosition: {type: Boolean, default: false}
  },
  components: {
    Modal,
    TrackRow
  },
  data () {
    return {
      backend: backend
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>

tr:not(:hover) .favorite-icon:not(.favorited) {
  display: none;
}
pre {
  overflow-x: scroll;
}
</style>
