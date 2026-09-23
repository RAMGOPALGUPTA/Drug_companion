import React, {useEffect, useState} from 'react';
import {NavigationContainer} from '@react-navigation/native';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {MaterialCommunityIcons} from '@expo/vector-icons';
import {View, Text, ActivityIndicator} from 'react-native';
import LoginScreen from './src/screens/LoginScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import TestCaptureScreen from './src/screens/TestCaptureScreen';
import ResultReviewScreen from './src/screens/ResultReviewScreen';
import RecordsScreen from './src/screens/RecordsScreen';
import StorageService from './src/services/StorageService';
import {AuthProvider, useAuth} from './src/store/authContext';

const Stack=createNativeStackNavigator(); const Tabs=createBottomTabNavigator();
const theme={dark:true,colors:{background:'#07111f',card:'#0d1b2a',text:'#f8fafc',border:'#203047',primary:'#ff6b35',notification:'#ff6b35'}};
function MainTabs(){return <Tabs.Navigator screenOptions={({route})=>({headerShown:false,tabBarStyle:{height:66,paddingBottom:8,backgroundColor:'#0d1b2a',borderTopColor:'#203047'},tabBarActiveTintColor:'#ff6b35',tabBarInactiveTintColor:'#8190a5',tabBarIcon:({color,size})=><MaterialCommunityIcons name={route.name==='Dashboard'?'view-dashboard-outline':route.name==='Capture'?'camera-outline':'file-document-multiple-outline'} color={color} size={size}/>})}><Tabs.Screen name="Dashboard" component={DashboardScreen}/><Tabs.Screen name="Capture" component={TestCaptureScreen}/><Tabs.Screen name="Records" component={RecordsScreen}/></Tabs.Navigator>}
function Root(){const {loggedIn}=useAuth(); if(loggedIn===null)return <View style={{flex:1,backgroundColor:'#07111f',justifyContent:'center'}}><ActivityIndicator color="#ff6b35" size="large"/></View>; return <NavigationContainer theme={theme}><Stack.Navigator screenOptions={{headerShown:false}}>{!loggedIn?<Stack.Screen name="Login" component={LoginScreen}/>:<><Stack.Screen name="Main" component={MainTabs}/><Stack.Screen name="Result" component={ResultReviewScreen} options={{presentation:'modal'}}/></>}</Stack.Navigator></NavigationContainer>}
export default function App(){const[ready,setReady]=useState(false);useEffect(()=>{StorageService.init().finally(()=>setReady(true))},[]);if(!ready)return <View style={{flex:1,backgroundColor:'#07111f',justifyContent:'center'}}><ActivityIndicator color="#ff6b35" size="large"/><Text style={{color:'#94a3b8',textAlign:'center',marginTop:12}}>Preparing secure local storage…</Text></View>;return <AuthProvider><Root/></AuthProvider>}
