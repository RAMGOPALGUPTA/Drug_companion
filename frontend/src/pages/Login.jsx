import React,{useState} from "react";
import {useAuth,demoOfficer} from "../auth/AuthContext.jsx";
export function Login(){
 const {login,signup}=useAuth();const [mode,setMode]=useState("signin");const [identifier,setIdentifier]=useState("");const [password,setPassword]=useState("");const [form,setForm]=useState({name:"",email:"",station:""});const [busy,setBusy]=useState(false);const [error,setError]=useState("");
 async function submit(event){event.preventDefault();setError("");setBusy(true);try{if(mode==="signin")await login(identifier,password);else{if(password.length<8)throw new Error("Use a password with at least 8 characters.");await signup({...form,password});}}catch(e){setError(e.message||"Unable to continue.");}finally{setBusy(false);}}
 return <main className="auth-screen"><section className="auth-card">
  <div className="auth-brand"><div className="auth-mark">DC</div><div><strong>Drug Companion</strong><span>FIELD INTELLIGENCE CONSOLE</span></div></div>
  <div className="auth-copy"><div className="panel-eyebrow">SECURE OFFICER ACCESS</div><h1>{mode==="signin"?"Sign in to your field console.":"Create your field account."}</h1><p>{mode==="signin"?"Access field analysis, case records, evidence integrity, and operational analytics.":"New accounts are provisioned as Field Officers. Supervisor and Administrator roles are controlled by platform administrators."}</p></div>
  <div className="auth-tabs"><button type="button" className={mode==="signin"?"active":""} onClick={()=>{setMode("signin");setError("");}}>Sign in</button><button type="button" className={mode==="signup"?"active":""} onClick={()=>{setMode("signup");setError("");}}>Sign up</button></div>
  <form className="auth-form" onSubmit={submit}>
   {mode==="signup"&&<><label><span>FULL NAME</span><input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="Officer name" required/></label><label><span>EMAIL</span><input type="email" autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="officer@example.com" required/></label><label><span>UNIT / STATION</span><input value={form.station} onChange={e=>setForm({...form,station:e.target.value})} placeholder="Mobile Operations"/></label></>}
   {mode==="signin"&&<label><span>OFFICER ID OR EMAIL</span><input autoComplete="username" value={identifier} onChange={e=>setIdentifier(e.target.value)} placeholder="FO-0017 or officer@example.com" required/></label>}
   <label><span>PASSWORD</span><input type="password" autoComplete={mode==="signin"?"current-password":"new-password"} value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter password" required/></label>
   {error&&<div className="auth-error">{error}</div>}<button className="auth-submit" type="submit" disabled={busy}>{busy?"Please wait…":mode==="signin"?"Sign in to console →":"Create field account →"}</button>
  </form>
  {mode==="signin"&&<button className="demo-access" type="button" onClick={()=>{setIdentifier(demoOfficer.email);setPassword("Field@123");setError("");}}>Use prototype officer access</button>}
  <div className="auth-notice">Prototype identity storage is local to this browser. Production deployment should connect this interface to server-side identity, secure sessions, MFA, and role-based access control.</div>
 </section></main>;
}
