<script setup>
defineProps({ name: { type: String, required: true } })

const paths = {
  sparkle: 'M12 2l1.9 5.1L19 9l-5.1 1.9L12 16l-1.9-5.1L5 9l5.1-1.9L12 2zM20 14v6m-3-3h6M4 14v4m-2-2h4',
  home: 'm3 10 9-7 9 7v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-9zM9 20v-7h6v7',
  clipboard: 'M9 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-3M9 2h6v5H9zM8 12h8m-8 4h6',
  wallet: 'M3 7V6a2 2 0 0 1 2-2h13v4M3 7v12a1 1 0 0 0 1 1h15a2 2 0 0 0 2-2V9a1 1 0 0 0-1-1H5a2 2 0 0 1-2-1zm18 5h-5a2 2 0 0 0 0 4h5',
  calendar: 'M8 2v4m8-4v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z',
  pin: 'M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0zM15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0z',
  search: 'M16 16l4 4M18 11a7 7 0 1 1-14 0 7 7 0 0 1 14 0z',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  down: 'M12 5v14m-6-6 6 6 6-6',
  send: 'm22 2-7 20-4-9-9-4 20-7zM22 2 11 13',
  check: 'm5 12 4 4L19 6',
  warning: 'M12 8v5m0 3v.01M12 3l10 18H2L12 3z',
  cross: 'm6 6 12 12M18 6 6 18',
  repeat: 'M3 12a9 9 0 1 1 3 6.7M3 12V6m0 6h6',
}
</script>

<template>
  <svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path :d="paths[name]" />
  </svg>
</template>
