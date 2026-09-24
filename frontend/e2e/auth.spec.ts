import {test,expect} from '@playwright/test'
import {mockAuth} from './auth-fixture'

test('sign in, named creation and logout use mocked Supabase',async({page})=>{
 await mockAuth(page,false)
 await page.route('**/api/sessions',r=>{
  expect(r.request().headers().authorization).toMatch(/^Bearer /)
  const body=r.request().postDataJSON();expect(body).toEqual({session_name:'Named investigation'})
  return r.fulfill({json:{session_id:'new-id',session_name:body.session_name,confirmed_equipment_id:null,confirmed_model:null,confirmation_status:'UNCONFIRMED',ranked_candidates:[],mismatch_warnings:[],raw_ocr_text:''}})
 })
 await page.goto('/');await page.getByLabel('Email').fill('technician@example.test');await page.getByLabel('Password').fill('test-password')
 await page.getByRole('button',{name:'Log in',exact:true}).click()
 await page.getByRole('button',{name:'Start new troubleshooting session'}).click()
 await page.getByLabel('Session name').fill('Named investigation');await page.getByRole('button',{name:'Start session',exact:true}).click()
 await expect(page.locator('.session-status')).toContainText('Named investigation')
 await page.getByRole('button',{name:'Log out'}).click();await expect(page.getByLabel('Email')).toBeVisible()
})

test('signup confirmation and login failure are clear',async({page})=>{
 await mockAuth(page,false);await page.goto('/')
 await page.getByRole('button',{name:'Create an account'}).click()
 await page.getByLabel('Email').fill('new@example.test');await page.getByLabel('Password').fill('test-password')
 await page.getByRole('button',{name:'Sign up',exact:true}).click()
 await expect(page.getByRole('status')).toContainText('Check your email')
 await page.getByRole('button',{name:'Already registered? Log in'}).click()
 await page.route('**/auth/v1/token**',r=>r.fulfill({status:400,json:{error_code:'invalid_credentials',msg:'Do not show internal details'}}))
 await page.getByLabel('Password').fill('wrong-password');await page.getByRole('button',{name:'Log in',exact:true}).click()
 await expect(page.getByRole('alert')).toContainText('Login failed')
 await expect(page.getByRole('alert')).not.toContainText('internal details')
})

test('public replay remains labeled and makes no backend/provider calls',async({page})=>{
 await mockAuth(page,false);let calls=0
 await page.route('**/api/**',r=>{calls++;return r.abort()})
 await page.goto('/?demo=true');await page.getByRole('button',{name:'ACS880 fault 5091',exact:true}).click()
 await expect(page.getByText('DEMO REPLAY · Not a fresh analysis')).toBeVisible()
 await expect(page.locator('.cause-title')).toBeVisible();expect(calls).toBe(0)
})
