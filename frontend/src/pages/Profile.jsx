import React,{useState} from "react";
import {useNavigate} from "react-router-dom";
import {useAuth} from "../auth/AuthContext.jsx";
import {useTheme} from "../theme/ThemeContext.jsx";
export function Profile(){
 const navigate=useNavigate();const {user,updateProfile,logout}=useAuth();const {theme,toggleTheme}=useTheme();const [editing,setEditing]=useState(false);const [draft,setDraft]=useState({name:user?.name||"",email:user?.email||"",station:user?.station||""});const [saved,setSaved]=useState(false);
 function save(){updateProfile({name:draft.name.trim()||user.name,email:draft.email.trim()||user.email,station:draft.station.trim()||user.station});setEditing(false);setSaved(true);window.setTimeout(()=>setSaved(false),2200);}
 return <div className="page-stack">
  <section className="profile-hero panel"><div className="profile-avatar">{user?.name?.slice(0,2).toUpperCase()||"FO"}</div><div className="profile-hero-copy"><div className="panel-eyebrow">OFFICER PROFILE</div><h2>{user?.name||"Field Officer"}</h2><p>{user?.role||"Field Officer"} · {user?.id||"—"}</p></div><div className="profile-hero-actions">{saved&&<span className="saved-pill">✓ Profile saved</span>}<button className="secondary-button" type="button" onClick={()=>setEditing(v=>!v)}>{editing?"Cancel":"Edit profile"}</button></div></section>
  <section className="content-grid two-col"><div className="panel profile-details"><div className="panel-head"><div><div className="panel-eyebrow">IDENTITY</div><h2>Officer details</h2></div></div>
   {editing?<div className="profile-edit-form"><label><span>NAME</span><input value={draft.name} onChange={e=>setDraft({...draft,name:e.target.value})}/></label><label><span>EMAIL</span><input type="email" value={draft.email} onChange={e=>setDraft({...draft,email:e.target.value})}/></label><label><span>UNIT / STATION</span><input value={draft.station} onChange={e=>setDraft({...draft,station:e.target.value})}/></label><button className="primary-button" type="button" onClick={save}>Save profile</button></div>:<div className="profile-grid"><div><span>NAME</span><strong>{user?.name||"—"}</strong></div><div><span>OFFICER ID</span><strong>{user?.id||"—"}</strong></div><div><span>EMAIL</span><strong>{user?.email||"—"}</strong></div><div><span>ROLE</span><strong>{user?.role||"—"}</strong></div><div><span>UNIT</span><strong>{user?.station||"—"}</strong></div><div><span>SESSION</span><strong>Authenticated</strong></div></div>}
  </div><div className="panel profile-details"><div className="panel-head"><div><div className="panel-eyebrow">PREFERENCES</div><h2>Console settings</h2></div></div>
   <button className="preference-row" type="button" onClick={toggleTheme}><span><strong>{theme==="dark"?"Dark workspace":"Soft light workspace"}</strong><small>Low-glare interface theme</small></span><b>{theme==="dark"?"☾":"☀"}</b></button>
   <div className="role-card"><span>ACCESS ROLE</span><strong>{user?.role}</strong><small>{user?.role==="Field Officer"?"Capture, cases and evidence":user?.role==="Supervisor"?"Full operations and analytics":"Full platform access"}</small></div>
   <button className="signout-button" type="button" onClick={()=>{logout();navigate("/");}}>Sign out of field console</button>
  </div></section>
 </div>;
}
