import {defineConfig} from '@playwright/test'
export default defineConfig({testDir:'e2e',timeout:60000,fullyParallel:false,workers:1,
 use:{baseURL:'http://127.0.0.1:5175',headless:true,viewport:{width:1440,height:1050},
  launchOptions:{executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'},
  screenshot:'only-on-failure',trace:'retain-on-failure'},
 webServer:{command:'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5175 --strictPort',env:{VITE_SUPABASE_URL:'https://auth-fixture.supabase.co',VITE_SUPABASE_ANON_KEY:'public-test-key',VITE_API_BASE_URL:'',VITE_DEMO_MODE:'false'},url:'http://127.0.0.1:5175',reuseExistingServer:false,timeout:30000}})
