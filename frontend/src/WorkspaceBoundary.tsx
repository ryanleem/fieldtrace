import {Component,type ReactNode} from 'react'
import App from './App'
export class WorkspaceErrorBoundary extends Component<{children:ReactNode;operation?:'create'|'reopen';onRetry:()=>void;onBack:()=>void},{failed:boolean}>{
 state={failed:false}
 static getDerivedStateFromError(){return {failed:true}}
 render(){return this.state.failed?<main><section className="panel" role="alert"><h1>{this.props.operation==='create'?'We couldn’t start a new troubleshooting session.':'We couldn’t reopen this troubleshooting session.'}</h1><p>Your sign-in and saved sessions are retained. Retry, or choose another session.</p><button onClick={this.props.onRetry}>Retry</button><button onClick={this.props.onBack}>Back to My Sessions</button></section></main>:this.props.children}
}
export default class WorkspaceBoundary extends Component<{userId:string;demo?:boolean;account?:ReactNode},{revision:number;page:'workspace'|'history';operation:'create'|'reopen'}>{
 state:{revision:number;page:'workspace'|'history';operation:'create'|'reopen'}={revision:0,page:'workspace',operation:'reopen'}
 render(){return <WorkspaceErrorBoundary key={this.state.revision} operation={this.state.operation} onRetry={()=>this.setState(s=>({...s,revision:s.revision+1}))} onBack={()=>{sessionStorage.removeItem(`fieldtrace.session.${this.props.userId}`);this.setState(s=>({revision:s.revision+1,page:'history',operation:'reopen'}))}}><App {...this.props} initialPage={this.state.page} onSessionOperation={operation=>this.setState({operation})}/></WorkspaceErrorBoundary>}
}
