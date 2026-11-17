import { createApp } from "vue";
import App from "./App.vue";
import router from "@/router";
import { createPinia } from "pinia";
import { initErrorTracking } from "@/observability";
import "@/assets/css/tailwind.css";
import "vue-sonner/style.css";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "@/assets/css/map-icons.css";
import "@/assets/css/map.css";
import "@/assets/css/global.css";

const app = createApp(App);
initErrorTracking(app);
app.use(createPinia()).use(router).mount("#app");
