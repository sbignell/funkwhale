<template>
  <span :style="defaultAvatarStyle" class="ui avatar circular label">{{ actor.preferred_username[0]}}</span>
</template>

<script>
import {hashCode, intToRGB} from '@/utils/color'

export default {
  props: ['actor'],
  computed: {
    actorColor () {
      return intToRGB(hashCode(this.actor.full_username))
    },
    defaultAvatarStyle () {
      return {
        'background-color': `#${this.actorColor}`
      }
    }
  }
}
</script>
