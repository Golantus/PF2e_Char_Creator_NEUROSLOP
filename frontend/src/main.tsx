import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './style.css';
class Boundary extends React.Component<{children:React.ReactNode},{error:string}>{state={error:''};static getDerivedStateFromError(e:Error){return{error:e.message};}render(){return this.state.error?<main style={{padding:40}}><h1>Не удалось открыть интерфейс</h1><p>{this.state.error}</p><p>Перезагрузите страницу. Персонажи остаются в локальной базе.</p><button onClick={()=>location.reload()}>Перезагрузить</button></main>:this.props.children;}}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><Boundary><App/></Boundary></React.StrictMode>);
