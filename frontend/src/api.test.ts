import {afterEach,expect,it,vi} from 'vitest'
import {apiUrl,request,safeLink} from './api'
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs()})
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

it('uses the local proxy when the public base is empty',()=>{
  vi.stubEnv('VITE_API_BASE_URL','')
  expect(apiUrl('/sessions')).toBe('/api/sessions')
})
it('uses a configured base for requests and saved-photo URLs',async()=>{
  vi.stubEnv('VITE_API_BASE_URL','https://backend.example.test///')
  const fetcher=vi.fn().mockResolvedValue(new Response('[]'))
  vi.stubGlobal('fetch',fetcher)
  await request('/sessions')
  expect(fetcher).toHaveBeenCalledWith('https://backend.example.test/sessions',expect.any(Object))
  expect(apiUrl('/sessions/one/images/two/file')).toBe('https://backend.example.test/sessions/one/images/two/file')
})


it.each([['3600','60 minutes'],['3299','55 minutes'],['60','1 minute']])('shows Retry-After %s without automatic retries',async(seconds,message)=>{
 const fetcher=vi.fn().mockResolvedValue(new Response('{}',{status:429,headers:{'Retry-After':seconds}}))
 vi.stubGlobal('fetch',fetcher)
 await expect(request('/sessions/case/troubleshooting/run',{method:'POST'})).rejects.toThrow(message)
 expect(fetcher).toHaveBeenCalledTimes(1)
})
it.each(['invalid','-1','999999'])('ignores invalid retry hint %s',async(value)=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}',{status:429,headers:{'Retry-After':value}})))
 await expect(request('/sessions')).rejects.toThrow('Please wait and retry.')
})
