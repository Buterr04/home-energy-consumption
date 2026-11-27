import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { initializeEnergyStore } from './stores/energy'
import './styles/main.css'

initializeEnergyStore()

createApp(App).use(router).mount('#app')
