import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Chat from './views/Chat.vue'
import Plans from './views/Plans.vue'
import Logs from './views/Logs.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.path !== from.path) return { top: 0 }
  },
  routes: [
    { path: '/', name: 'chat', component: Chat },
    { path: '/plans', name: 'plans', component: Plans },
    { path: '/logs', name: 'logs', component: Logs },
    { path: '/:rest(.*)', redirect: '/' },
  ],
})
createApp(App).use(router).mount('#app')
