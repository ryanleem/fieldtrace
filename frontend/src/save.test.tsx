import {act,cleanup,renderHook} from '@testing-library/react'
import {beforeEach,afterEach,expect,it,vi} from 'vitest'
import useSessionSave,{type Draft} from './useSessionSave'
const mocks=vi.hoisted(()=>({request:vi.fn()}))
vi.mock('./api',()=>({request:mocks.request,json:(body:unknown)=>({method:'POST',body:JSON.stringify(body)})}))
const empty:Draft={model:'',symptom:'',followup:'',entry_type:'answer',measurement:{name:'temperature',value:'',unit:'C',location:''}}
beforeEach(()=>{vi.useFakeTimers();mocks.request.mockReset();mocks.request.mockResolvedValue({})})
afterEach(()=>{cleanup();vi.useRealTimers()})
function setup(id='a'){
 const hook=renderHook(({id,draft})=>useSessionSave(id,draft,false),{initialProps:{id,draft:empty}})
 act(()=>hook.result.current.hydrate(id,empty));return hook
}
it('debounces edits, sends only latest draft, and never uploads or analyzes',async()=>{
 const h=setup();h.rerender({id:'a',draft:{...empty,symptom:'Fault'}})
 await act(async()=>{await vi.advanceTimersByTimeAsync(700)})
 expect(mocks.request).not.toHaveBeenCalled()
 h.rerender({id:'a',draft:{...empty,symptom:'Fault 5091'}})
 await act(async()=>{await vi.advanceTimersByTimeAsync(850)})
 expect(mocks.request).toHaveBeenCalledTimes(1)
 expect(mocks.request.mock.calls[0][0]).toBe('/sessions/a/draft')
 expect(JSON.parse(mocks.request.mock.calls[0][1].body).symptom).toBe('Fault 5091')
 expect(h.result.current.status).toBe('Saved')
})
it('manual save is immediate, serializes duplicate clicks and retains edits made during saving',async()=>{
 let release!:()=>void;mocks.request.mockImplementationOnce(()=>new Promise<void>(r=>{release=r}))
 const h=setup();h.rerender({id:'a',draft:{...empty,model:'ACS880'}})
 let one!:Promise<boolean>,two!:Promise<boolean>
 act(()=>{one=h.result.current.save();two=h.result.current.save()})
 expect(h.result.current.saving).toBe(true);expect(mocks.request).toHaveBeenCalledTimes(1)
 h.rerender({id:'a',draft:{...empty,model:'ACS880-01'}})
 await act(async()=>{release();await Promise.all([one,two])})
 expect(mocks.request).toHaveBeenCalledTimes(2)
 expect(h.result.current.status).toBe('Saved')
})
it('failure preserves dirty draft and retry succeeds',async()=>{
 mocks.request.mockRejectedValueOnce(new Error('network'))
 const h=setup();h.rerender({id:'a',draft:{...empty,symptom:'keep me'}})
 await act(async()=>{await h.result.current.save()})
 expect(h.result.current.status).toBe('Save failed')
 await act(async()=>{await h.result.current.save()})
 expect(JSON.parse(mocks.request.mock.calls[1][1].body).symptom).toBe('keep me')
 expect(h.result.current.status).toBe('Saved')
})
it('does not save without a session or after unmount/logout',async()=>{
 const h=setup('');h.rerender({id:'',draft:{...empty,symptom:'no case'}})
 await act(async()=>{await vi.advanceTimersByTimeAsync(1000);await h.result.current.save()})
 expect(mocks.request).not.toHaveBeenCalled();h.unmount()
 const next=setup();next.rerender({id:'a',draft:{...empty,symptom:'unsaved'}});next.unmount()
 await act(async()=>{await vi.advanceTimersByTimeAsync(1000)})
 expect(mocks.request).not.toHaveBeenCalled()
})
it('session switch cannot redirect an outstanding write or apply its saved status to another case',async()=>{
 let release!:()=>void;mocks.request.mockImplementationOnce(()=>new Promise<void>(r=>{release=r}))
 const h=setup();h.rerender({id:'a',draft:{...empty,symptom:'A'}})
 let pending!:Promise<boolean>;act(()=>{pending=h.result.current.save()})
 h.rerender({id:'b',draft:empty});act(()=>h.result.current.hydrate('b',empty))
 await act(async()=>{release();await pending;await vi.advanceTimersByTimeAsync(1000)})
 expect(mocks.request).toHaveBeenCalledTimes(1)
 expect(mocks.request.mock.calls[0][0]).toBe('/sessions/a/draft')
})
