import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import {liveConfigErrors} from './src/deploymentConfig.ts'
export default defineConfig(({command,mode})=>{
 if(command==='build'&&(process.env.VERCEL==='1'||process.env.FIELDTRACE_HOSTED_BUILD==='true')){
  const errors=liveConfigErrors(loadEnv(mode,process.cwd(),'VITE_'),true)
  if(errors.length)throw new Error('FieldTrace live deployment configuration failed:\n'+errors.join('\n')+'\nSet variables in the correct Vercel environment/branch scope and rebuild.')
 }
 return { plugins:[react()], server:{port:5173, strictPort:true,
  proxy:{'/api':{target:process.env.BACKEND_URL || 'http://127.0.0.1:8000',changeOrigin:true,timeout:0,proxyTimeout:0,rewrite:p=>p.replace(/^\/api/,'')}}},
  preview:{port:4173, proxy:{'/api':{target:process.env.BACKEND_URL || 'http://127.0.0.1:8000',changeOrigin:true,timeout:0,proxyTimeout:0,rewrite:p=>p.replace(/^\/api/,'')}}} }
})
