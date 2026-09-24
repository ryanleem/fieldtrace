import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import AuthShell from './AuthShell'

const mocks=vi.hoisted(()=>({getSession:vi.fn(),signInWithPassword:vi.fn(),signUp:vi.fn(),signOut:vi.fn(),onAuthStateChange:vi.fn()}))
vi.mock('./auth',()=>({supabase:{auth:mocks}}))
vi.mock('./App',()=>({default:({account}:{account:React.ReactNode})=><div>Saved workspace{account}</div>}))
const session={access_token:'test-only',user:{id:'user-a',email:'a@example.test'}}
beforeEach(()=>{
 vi.clearAllMocks();sessionStorage.clear()
 mocks.getSession.mockResolvedValue({data:{session:null},error:null})
 mocks.onAuthStateChange.mockReturnValue({data:{subscription:{unsubscribe:vi.fn()}}})
})
afterEach(cleanup)
async function credentials(){
 await screen.findByLabelText('Email');fireEvent.change(screen.getByLabelText('Email'),{target:{value:'a@example.test'}})
 fireEvent.change(screen.getByLabelText('Password'),{target:{value:'test-password'}})
}
it('restores authentication before mounting user workspace',async()=>{
 mocks.getSession.mockResolvedValue({data:{session},error:null});render(<AuthShell/>)
 expect(screen.getByRole('status').textContent).toContain('Restoring')
 expect(await screen.findByText('Saved workspace')).toBeTruthy()
})
it('logs in through Supabase and never submits passwords to the application API',async()=>{
 mocks.signInWithPassword.mockResolvedValue({data:{session},error:null});render(<AuthShell/>);await credentials()
 fireEvent.click(screen.getByRole('button',{name:'Log in'}))
 await screen.findByText('Saved workspace');expect(mocks.signInWithPassword).toHaveBeenCalledWith({email:'a@example.test',password:'test-password'})
})
it('signup explains email confirmation when no session is issued',async()=>{
 mocks.signUp.mockResolvedValue({data:{session:null},error:null});render(<AuthShell/>);await credentials()
 fireEvent.click(screen.getByRole('button',{name:'Create an account'}));fireEvent.click(screen.getByRole('button',{name:'Sign up'}))
 await screen.findByText('Check your email to confirm your account, then log in.')
 expect(mocks.signUp).toHaveBeenCalledOnce()
})
it('auth errors do not expose raw provider details',async()=>{
 mocks.signInWithPassword.mockResolvedValue({data:{session:null},error:{message:'sensitive debug detail'}})
 render(<AuthShell/>);await credentials();fireEvent.click(screen.getByRole('button',{name:'Log in'}))
 const alert=await screen.findByRole('alert');expect(alert.textContent).toContain('Login failed');expect(alert.textContent).not.toContain('sensitive')
})
it('logout clears account-specific active session and unmounts data',async()=>{
 mocks.getSession.mockResolvedValue({data:{session},error:null});mocks.signOut.mockResolvedValue({error:null})
 sessionStorage.setItem('fieldtrace.session.user-a','old-case');render(<AuthShell/>);await screen.findByText('Saved workspace')
 fireEvent.click(screen.getByRole('button',{name:'Log out'}));await screen.findByLabelText('Email')
 expect(sessionStorage.getItem('fieldtrace.session.user-a')).toBeNull();expect(screen.queryByText('Saved workspace')).toBeNull()
})
it('auth event replacing an account takes priority over stale restore',async()=>{
 let callback:Function=()=>{};let resolve:Function=()=>{}
 mocks.onAuthStateChange.mockImplementation((cb)=>{callback=cb;return {data:{subscription:{unsubscribe:vi.fn()}}}})
 mocks.getSession.mockReturnValue(new Promise(r=>{resolve=r}));render(<AuthShell/>)
 callback('SIGNED_IN',session);resolve({data:{session:null},error:null})
 await waitFor(()=>expect(screen.queryByText('Saved workspace')).toBeTruthy())
})
