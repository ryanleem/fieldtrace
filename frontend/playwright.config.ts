import {defineConfig} from '@playwright/test'
export default defineConfig({testDir:'e2e',timeout:60000,fullyParallel:false,workers:1,
 use:{baseURL:'http://127.0.0.1:5173',headless:true,viewport:{width:1440,height:1050},
  launchOptions:{executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'},
  screenshot:'only-on-failure',trace:'retain-on-failure'},
 webServer:{command:'npm run dev',url:'http://127.0.0.1:5173',reuseExistingServer:true,timeout:30000}})
