import React, { createContext, useContext, useMemo, useState } from "react";
const USER_KEY = "drug_companion_auth_user";
const USERS_KEY = "drug_companion_users";
const DEFAULT_USERS = [
  { id:"FO-0017", name:"Field Officer", email:"officer@drugcompanion.local", role:"Field Officer", station:"Mobile Operations", password:"Field@123" },
  { id:"SUP-0001", name:"Operations Supervisor", email:"supervisor@drugcompanion.local", role:"Supervisor", station:"Operations Control", password:"Supervisor@123" },
  { id:"ADM-0001", name:"System Administrator", email:"admin@drugcompanion.local", role:"Administrator", station:"Platform Administration", password:"Admin@123" },
];
const AuthContext = createContext(null);
function loadUsers(){ try{const saved=JSON.parse(localStorage.getItem(USERS_KEY)||"null");if(Array.isArray(saved)&&saved.length)return saved;}catch{} localStorage.setItem(USERS_KEY,JSON.stringify(DEFAULT_USERS));return DEFAULT_USERS;}
function publicUser(user){const {password,...safe}=user;return safe;}
export function AuthProvider({children}){
 const [users,setUsers]=useState(loadUsers);
 const [user,setUser]=useState(()=>{try{return JSON.parse(localStorage.getItem(USER_KEY)||"null");}catch{return null;}});
 function persistUsers(next){setUsers(next);localStorage.setItem(USERS_KEY,JSON.stringify(next));}
 async function login(identifier,password){const value=identifier.trim().toLowerCase();const match=users.find(c=>c.email.toLowerCase()===value||c.id.toLowerCase()===value);if(!match||match.password!==password)throw new Error("Invalid officer ID/email or password.");const safe=publicUser(match);localStorage.setItem(USER_KEY,JSON.stringify(safe));setUser(safe);return safe;}
 async function signup({name,email,password,station}){const normalizedEmail=email.trim().toLowerCase();if(users.some(c=>c.email.toLowerCase()===normalizedEmail))throw new Error("An account with this email already exists.");const nextUser={id:"FO-"+String(Date.now()).slice(-4),name:name.trim(),email:normalizedEmail,role:"Field Officer",station:station.trim()||"Mobile Operations",password};persistUsers([...users,nextUser]);const safe=publicUser(nextUser);localStorage.setItem(USER_KEY,JSON.stringify(safe));setUser(safe);return safe;}
 function updateProfile(patch){if(!user)return;const next={...user,...patch};persistUsers(users.map(c=>c.id===user.id?{...c,...patch}:c));localStorage.setItem(USER_KEY,JSON.stringify(next));setUser(next);}
 function logout(){localStorage.removeItem(USER_KEY);setUser(null);}
 const value=useMemo(()=>({user,users,login,signup,updateProfile,logout}),[user,users]);return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth(){const context=useContext(AuthContext);if(!context)throw new Error("useAuth must be used inside AuthProvider");return context;}
export const demoOfficer=DEFAULT_USERS[0];
export const rolePermissions={
 "Field Officer":{capture:true,cases:true,evidence:true,analytics:false,administration:false},
 Supervisor:{capture:true,cases:true,evidence:true,analytics:true,administration:false},
 Administrator:{capture:true,cases:true,evidence:true,analytics:true,administration:true},
};
