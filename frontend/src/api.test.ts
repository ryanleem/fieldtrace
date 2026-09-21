import {afterEach,expect,it,vi} from 'vitest'
import {request,safeLink} from './api'
afterEach(()=>vi.unstubAllGlobals())
it('only permits HTTP manual links, never executable URLs',()=>{
  expect(safeLink('javascript:alert(1)')).toBeUndefined();expect(safeLink('data:text/html,hi')).toBeUndefined()
  expect(safeLink('https://library.abb.com/manual.pdf#page=525')).toContain('#page=525')
})
it('keeps rate limits distinct from provider success',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}',{status:429})))
  await expect(request('/sessions')).rejects.toThrow('rate limit')
})
it('does not expose backend failure details as an answer',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{"detail":"internal traceback"}',{status:500})))
  await expect(request('/sessions')).rejects.toThrow('temporarily unavailable')
})
it('turns a timeout into an explicit refresh-before-retry instruction',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new DOMException('timeout','AbortError')))
  await expect(request('/sessions')).rejects.toThrow('may still be running')
})
